"""What every engine shares.

An engine differs from another engine in exactly one place: where the words and
the work come from during a shift. Everything else — the company registry, the
durable brain, the read models, the vault, the workspace, the share gate, the
kill switch — is the same product behaviour, and it lives here once.

No ``openhands.*`` imports in this module, ever. The stub engine imports it and
the stub must stay importable (and testable) without the SDK installed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
import secrets
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from werkhaus.brain.layout import CompanyPaths
from werkhaus.brain.store import BrainStore
from werkhaus.contract.engine import Engine
from werkhaus.contract.errors import (
    ArtifactNotFound,
    BudgetExceeded,
    CompanyHalted,
    CompanyNotFound,
    NotFound,
    OutOfShifts,
    ShiftAlreadyRunning,
    ShiftNotFound,
    ValidationFailed,
    WerkhausError,
)
from werkhaus.contract.events import ShiftEvent
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import (
    Artifact,
    ArtifactId,
    ArtifactKind,
    AttentionRequest,
    Budget,
    Charter,
    CharterPatch,
    Company,
    CompanyId,
    CompanyStatus,
    Decision,
    LedgerEntry,
    Objection,
    PublicSnapshot,
    Role,
    RoleStatus,
    ShareLink,
    ShareOptions,
    Shift,
    ShiftId,
    ShiftStatus,
    Task,
    TaskStatus,
    VaultItem,
    WorkspaceFile,
)
from werkhaus.contract.plan import Allowance, build_allowance, current_plan
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.roster import ROSTER, display_name
from werkhaus.share.snapshot import build_snapshot

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


def cents(amount: Decimal) -> Decimal:
    """Money is money. Dividing a budget across activities produces things like
    6.8399999999999999998, and that must never reach the API."""
    return amount.quantize(CENTS)


class CompanyRuntime:
    """Runtime state for one company, engine-agnostic.

    Everything durable lives in :class:`BrainStore`. What is here is what
    genuinely should not survive a restart: the running task, the socket bus,
    and who is currently doing what.
    """

    def __init__(self, brain: BrainStore, bus: CompanyBus) -> None:
        self.brain = brain
        self.bus = bus
        self.id = brain.company_id
        self.roles: dict[str, dict[str, Any]] = {
            role.id: {"status": RoleStatus.IDLE, "activity": None} for role in ROSTER
        }
        self.task_handle: asyncio.Task[None] | None = None
        self.answered: dict[str, asyncio.Event] = {}

    # ---------------------------------------------------------------- budget
    @property
    def cap(self) -> Decimal:
        return Decimal(str(self.brain.state.metrics.get("budget_cap", "60.00")))

    @property
    def per_shift_cap(self) -> Decimal:
        return Decimal(str(self.brain.state.metrics.get("per_shift_cap", "12.00")))

    @property
    def spent(self) -> Decimal:
        return self.brain.state.spent

    @property
    def halted(self) -> bool:
        return bool(self.brain.state.metrics.get("halted", False))

    @property
    def archived(self) -> bool:
        return bool(self.brain.state.metrics.get("archived", False))

    # ---------------------------------------------------------------- status
    @property
    def status(self) -> CompanyStatus:
        """Derived, never stored.

        A status field that can disagree with the facts it summarises will
        eventually disagree with them — usually as a company stuck on "working"
        with nothing running.
        """
        if self.archived:
            return CompanyStatus.ARCHIVED
        if self.halted:
            return CompanyStatus.HALTED
        if any(r.answered_at is None for r in self.brain.state.attention.values()):
            return CompanyStatus.BLOCKED
        if self.task_handle is not None and not self.task_handle.done():
            return CompanyStatus.WORKING
        if not self.brain.state.charter:
            return CompanyStatus.DRAFT
        return CompanyStatus.IDLE

    # ----------------------------------------------------------------- views
    @property
    def shifts(self) -> list[Shift]:
        return sorted(self.brain.state.shifts.values(), key=lambda s: s.number)

    @property
    def share(self) -> ShareLink | None:
        raw = self.brain.state.metrics.get("share")
        return ShareLink.model_validate(raw) if raw else None

    @property
    def created_at(self) -> datetime:
        raw = self.brain.state.metrics.get("created_at")
        return datetime.fromisoformat(raw) if raw else datetime.now(UTC)

    def company(self) -> Company:
        state = self.brain.state
        roster = [
            Role(
                **{
                    **base.model_dump(),
                    "status": self.roles[base.id]["status"],
                    "current_activity": self.roles[base.id]["activity"],
                    "shifts_worked": sum(
                        1 for s in state.shifts.values() if base.id in s.roles_active
                    ),
                }
            )
            for base in ROSTER
        ]
        charter = state.charter
        assert charter is not None, "a company always has a charter by creation time"
        return Company(
            id=self.id,
            name=state.name,
            status=self.status,
            charter=charter,
            created_at=self.created_at,
            shift_count=len(state.shifts),
            progress=state.progress,
            budget=Budget(
                spent=self.spent.quantize(CENTS),
                cap=self.cap.quantize(CENTS),
                per_shift_cap=self.per_shift_cap.quantize(CENTS),
            ),
            roster=roster,
            share=self.share,
        )

    def clear_activity(self) -> None:
        for role in self.roles.values():
            if role["status"] is not RoleStatus.FAILED:
                role["status"] = RoleStatus.IDLE
            role["activity"] = None


class BaseEngine(Engine):
    """Everything an engine does that isn't running a shift."""

    def __init__(self, root: str | Path = "./data") -> None:
        self.root = Path(root)
        self._companies: dict[CompanyId, CompanyRuntime] = {}

    # ---------------------------------------------------------------- hooks
    def _make_runtime(self, brain: BrainStore, bus: CompanyBus) -> CompanyRuntime:
        """Build this engine's per-company runtime. The only required hook."""
        raise NotImplementedError

    # -------------------------------------------------------------- lifecycle
    async def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        loop = asyncio.get_running_loop()
        for directory in sorted(self.root.glob("co_*")):
            if not (directory / "_state" / "log.jsonl").exists():
                continue
            try:
                company = self._open(directory.name, directory)
            except Exception:
                logger.exception("could not load company at %s", directory)
                continue
            company.bus.bind_loop(loop)
            self._companies[company.id] = company

            # A shift that was RUNNING when we died is over. Because the log is
            # the source of truth, "nothing was lost" is literally true.
            for shift in company.brain.abort_running_shifts(
                "Werkhaus restarted while this shift was running."
            ):
                company.bus.emit(
                    K.SHIFT_FAILED,
                    f"Shift {shift.number} was interrupted. Nothing was lost — "
                    "here's what got done.",
                    shift_id=shift.id,
                )
        logger.info(
            "%s ready: %d companies", type(self).__name__, len(self._companies)
        )

    async def aclose(self) -> None:
        handles = [
            c.task_handle
            for c in self._companies.values()
            if c.task_handle and not c.task_handle.done()
        ]
        for handle in handles:
            handle.cancel()
        await asyncio.gather(*handles, return_exceptions=True)

    def _open(self, cid: str, root: Path) -> CompanyRuntime:
        brain = BrainStore(root, cid)
        bus = CompanyBus(cid, CompanyPaths(root).events)
        return self._make_runtime(brain, bus)

    def _get(self, cid: CompanyId) -> CompanyRuntime:
        company = self._companies.get(cid)
        if company is None:
            raise CompanyNotFound()
        return company

    def _new_company(
        self,
        *,
        charter: Charter,
        name: str,
        budget_cap: Decimal,
        per_shift_cap: Decimal,
        extra_metrics: dict[str, Any] | None = None,
    ) -> CompanyRuntime:
        """The creation boilerplate both engines share: brain, bus, charter on
        disk, budget metrics, registry entry."""
        cid = f"co_{secrets.token_hex(3)}"
        root = self.root / cid
        brain = BrainStore(root, cid)
        bus = CompanyBus(cid, CompanyPaths(root).events)
        bus.bind_loop(asyncio.get_running_loop())

        brain.set_charter(charter, name)
        for key, value in (extra_metrics or {}).items():
            brain.record_metric(key, value)
        brain.record_metric("created_at", datetime.now(UTC).isoformat())
        brain.record_metric("budget_cap", str(cents(budget_cap)))
        brain.record_metric("per_shift_cap", str(cents(per_shift_cap)))
        CompanyPaths(root).charter.write_text(
            f"# {brain.state.name}\n\n{charter.one_liner}\n\n"
            f"**Who it's for:** {charter.audience}\n\n"
            f"**Done means:** {charter.success_looks_like}\n",
            encoding="utf-8",
        )

        company = self._make_runtime(brain, bus)
        self._companies[cid] = company
        return company

    # ---------------------------------------------------------- autonomy
    AUTO_CHAIN_LIMIT = 2
    """How many shifts the team may start on its own after one the user
    started. A bound, not a budget: the money caps still apply on top."""

    def _schedule_auto_chain(self, company: CompanyRuntime) -> None:
        """On the auto side of the dial, a finished shift starts the next one.

        Bounded three ways — the chain limit, the money cap, and done-ness —
        because "runs by itself" must never mean "spends by itself forever".
        """
        charter = company.brain.state.charter
        if charter is None or charter.autonomy not in ("full_auto", "semi_auto"):
            return
        if company.spent >= company.cap or company.halted:
            return
        if company.brain.state.progress.percent >= 100:
            return
        chained = int(company.brain.state.metrics.get("auto_chained", 0) or 0)
        if chained >= self.AUTO_CHAIN_LIMIT:
            return

        async def _chain() -> None:
            # Wait for the current shift's task to actually finish.
            for _ in range(150):
                handle = company.task_handle
                if handle is None or handle.done():
                    break
                await asyncio.sleep(0.2)
            try:
                company.brain.record_metric("auto_chained", chained + 1)
                await self.start_shift(company.id, auto=True)
                company.bus.emit(
                    K.ROLE_SAID,
                    "Ada: The team is carrying straight on — that's the "
                    "autonomy you chose. Press stop anytime.",
                )
            except WerkhausError:
                pass  # halted, out of budget, or already running: all fine

        asyncio.create_task(_chain())

    def _ensure_can_start(self, company: CompanyRuntime) -> None:
        """The four reasons a shift may not start, in the order the user
        would want to hear about them."""
        if company.halted:
            raise CompanyHalted()
        if company.task_handle and not company.task_handle.done():
            raise ShiftAlreadyRunning()
        if company.spent >= company.cap:
            raise BudgetExceeded()
        allowance = self.allowance()
        if allowance.shifts_left is not None and allowance.shifts_left <= 0:
            raise OutOfShifts(hint=self._refill_hint(allowance))

    # ------------------------------------------------------------------- plan
    @staticmethod
    def _refill_hint(allowance: Allowance) -> str:
        if allowance.next_refill_at is None:
            return "Upgrade to keep the team working."
        days = max(
            0, (allowance.next_refill_at - datetime.now(UTC)).days
        )
        when = "tomorrow" if days <= 1 else f"in {days} days"
        return (
            f"Your next shift arrives {when} — or upgrade to keep going now."
        )

    def _shifts_charged(self) -> int:
        """What the plan has actually been used for, counted from the brains.

        Charged: a shift that is running now, and a finished shift that left a
        document behind. A shift that produced nothing was our failure, and a
        trial billed for our failure is a trial the founder abandons.
        """
        total = 0
        for company in self._companies.values():
            for shift in company.brain.state.shifts.values():
                if shift.status is ShiftStatus.RUNNING:
                    total += 1
                elif shift.status is ShiftStatus.COMPLETED and shift.artifacts_produced:
                    # The list is snapshotted onto the shift when it closes, so
                    # a later shift revising the same document cannot quietly
                    # take credit — and un-charge the shift that wrote it.
                    total += 1
        return total

    def _member_since(self) -> datetime | None:
        """The refill clock starts at the first company, not at install: the
        trial should begin when the founder does."""
        stamps = [c.created_at for c in self._companies.values() if c.created_at]
        return min(stamps) if stamps else None

    def allowance(self) -> Allowance:
        return build_allowance(
            current_plan(), self._member_since(), self._shifts_charged()
        )

    async def get_allowance(self) -> Allowance:
        return self.allowance()

    # --------------------------------------------------------------- companies
    async def get_company(self, cid: CompanyId) -> Company:
        return self._get(cid).company()

    async def list_companies(self) -> list[Company]:
        return [c.company() for c in self._companies.values()]

    async def update_charter(self, cid: CompanyId, patch: CharterPatch) -> Company:
        company = self._get(cid)
        current = company.brain.state.charter
        assert current is not None
        updated = current.model_copy(update=patch.model_dump(exclude_none=True))
        company.brain.set_charter(updated, company.brain.state.name)
        return company.company()

    async def archive_company(self, cid: CompanyId) -> None:
        self._get(cid).brain.record_metric("archived", True)

    # ------------------------------------------------------------------ shifts
    async def get_shift(self, sid: ShiftId) -> Shift:
        company = self._get(sid.split("/")[0])
        shift = company.brain.state.shifts.get(sid)
        if shift is None:
            raise ShiftNotFound()
        return shift

    async def list_shifts(
        self, cid: CompanyId, limit: int = 50, before: int | None = None
    ) -> list[Shift]:
        shifts = sorted(self._get(cid).shifts, key=lambda s: s.number, reverse=True)
        if before is not None:
            shifts = [s for s in shifts if s.number < before]
        return shifts[:limit]

    async def stop_shift(self, sid: ShiftId, reason: str = "user") -> Shift:
        company = self._get(sid.split("/")[0])
        await self._cancel(company)
        return await self.get_shift(sid)

    # -------------------------------------------------------------- read models
    async def list_tasks(
        self, cid: CompanyId, status: TaskStatus | None = None
    ) -> list[Task]:
        tasks = self._get(cid).brain.state.tasks.values()
        return [t for t in tasks if status is None or t.status is status]

    async def list_artifacts(
        self, cid: CompanyId, kind: ArtifactKind | None = None
    ) -> list[Artifact]:
        artifacts = self._get(cid).brain.state.artifacts.values()
        return [a for a in artifacts if kind is None or a.kind is kind]

    async def get_artifact(self, aid: ArtifactId) -> Artifact:
        for company in self._companies.values():
            artifact = company.brain.state.artifacts.get(aid)
            if artifact:
                return artifact
        raise ArtifactNotFound()

    async def read_artifact(self, aid: ArtifactId) -> tuple[bytes, str]:
        artifact = await self.get_artifact(aid)
        company = self._get(artifact.company_id)
        root = company.brain.paths.root.resolve()
        # Ids are opaque and the path comes from our own index, but resolve and
        # check containment anyway: this is the exact shape of the bug that
        # publishes someone's home directory.
        target = (root / artifact.path).resolve()
        if not target.is_relative_to(root):
            raise ArtifactNotFound()
        if not target.is_file():
            return b"", artifact.mime
        return target.read_bytes(), artifact.mime

    async def list_decisions(self, cid: CompanyId) -> list[Decision]:
        return list(self._get(cid).brain.state.decisions.values())

    async def list_objections(self, cid: CompanyId) -> list[Objection]:
        return list(self._get(cid).brain.state.objections.values())

    async def list_attention(self, cid: CompanyId) -> list[AttentionRequest]:
        return list(self._get(cid).brain.state.attention.values())

    async def list_ledger(self, cid: CompanyId, limit: int = 200) -> list[LedgerEntry]:
        return list(reversed(self._get(cid).brain.state.ledger))[:limit]

    # --------------------------------------------------------------- user input
    async def answer_attention(
        self, cid: CompanyId, request_id: str, answer: str
    ) -> None:
        company = self._get(cid)
        request = company.brain.answer(request_id, answer)
        who = display_name(request.role_id or "chief")
        company.bus.emit(
            K.ROLE_SAID,
            f"You answered {who}: {answer}",
            shift_id=request.shift_id,
            role_id=request.role_id,
        )
        event = company.answered.get(request_id)
        if event:
            event.set()

    async def send_note(self, cid: CompanyId, text: str) -> None:
        company = self._get(cid)
        company.brain.add_note(text)
        company.bus.emit(K.ROLE_SAID, f"You told the team: {text}")

    # ------------------------------------------------------------------ control
    async def set_budget_cap(self, cid: CompanyId, cap: Decimal) -> Budget:
        company = self._get(cid)
        company.brain.record_metric("budget_cap", str(cents(cap)))
        if company.halted and company.spent < cap:
            company.brain.record_metric("halted", False)
        return company.company().budget

    async def halt(self, cid: CompanyId) -> Company:
        """The kill switch. Must complete in under two seconds. Tested."""
        company = self._get(cid)
        await self._cancel(company)
        company.brain.record_metric("halted", True)
        company.bus.emit(K.SHIFT_FAILED, "You stopped the company.")
        return company.company()

    async def resume(self, cid: CompanyId) -> Company:
        company = self._get(cid)
        company.brain.record_metric("halted", False)
        return company.company()

    async def _cancel(self, company: CompanyRuntime) -> None:
        handle = company.task_handle
        if handle and not handle.done():
            handle.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(handle), timeout=1.5)
            except (TimeoutError, asyncio.CancelledError):
                pass
        company.task_handle = None
        # A task cancelled before its first step never runs its cleanup, so the
        # shift it belonged to would stay RUNNING forever. Sweep here.
        for shift in company.brain.abort_running_shifts("You stopped this shift."):
            company.bus.emit(
                K.SHIFT_FAILED,
                f"Shift {shift.number} was stopped. "
                "Everything already done is saved.",
                shift_id=shift.id,
            )
        company.clear_activity()

    # -------------------------------------------------------------------- vault
    _VAULT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")

    def _vault_read(self, company: CompanyRuntime) -> dict[str, dict[str, str]]:
        path = company.brain.paths.state / "vault.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _vault_write(
        self, company: CompanyRuntime, vault: dict[str, dict[str, str]]
    ) -> None:
        # Values live only in this file, under _state (0700), outside the
        # workspace the team's file tools can reach with a relative path. They
        # are never written through the event log — a secret in an append-only
        # log can never be deleted.
        path = company.brain.paths.state / "vault.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(vault, indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(path)

    @staticmethod
    def _vault_item(name: str, entry: dict[str, str]) -> VaultItem:
        value = entry["value"]
        return VaultItem(
            name=name,
            hint=f"{len(value)} characters, ends in …{value[-2:]}"
            if len(value) >= 8
            else f"{len(value)} characters",
            added_at=datetime.fromisoformat(entry["added_at"]),
        )

    async def list_vault(self, cid: CompanyId) -> list[VaultItem]:
        vault = self._vault_read(self._get(cid))
        return [self._vault_item(n, e) for n, e in sorted(vault.items())]

    async def set_vault(self, cid: CompanyId, name: str, value: str) -> VaultItem:
        if not self._VAULT_NAME.match(name):
            raise ValidationFailed(
                "That name won't work.",
                hint="Use letters, numbers, dots, dashes or underscores, "
                "starting with a letter — like STRIPE_KEY.",
            )
        company = self._get(cid)
        vault = self._vault_read(company)
        vault[name] = {
            "value": value,
            "added_at": datetime.now(UTC).isoformat(),
        }
        self._vault_write(company, vault)
        return self._vault_item(name, vault[name])

    async def delete_vault(self, cid: CompanyId, name: str) -> None:
        company = self._get(cid)
        vault = self._vault_read(company)
        if name not in vault:
            raise NotFound("There's no key with that name.")
        del vault[name]
        self._vault_write(company, vault)

    # ---------------------------------------------------------------- workspace
    MAX_FILE_BYTES = 512 * 1024

    def _workspace_target(self, company: CompanyRuntime, path: str) -> Path:
        workspace = company.brain.paths.workspace.resolve()
        target = (workspace / path).resolve()
        if not target.is_relative_to(workspace):
            raise NotFound("There's no file at that path.")
        return target

    async def list_files(self, cid: CompanyId) -> list[WorkspaceFile]:
        workspace = self._get(cid).brain.paths.workspace
        if not workspace.exists():
            return []
        files: list[WorkspaceFile] = []
        for path in sorted(workspace.rglob("*")):
            if not path.is_file() or path.name.startswith("."):
                continue
            try:
                path.read_text(encoding="utf-8")
                kind = "text"
            except (UnicodeDecodeError, OSError):
                kind = "binary"
            files.append(
                WorkspaceFile(
                    path=str(path.relative_to(workspace)),
                    size=path.stat().st_size,
                    kind=kind,
                )
            )
        return files[:500]

    async def read_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        target = self._workspace_target(self._get(cid), path)
        if not target.is_file():
            raise NotFound("There's no file at that path.")
        mime = mimetypes.guess_type(target.name)[0] or "text/plain"
        return target.read_bytes()[: self.MAX_FILE_BYTES], mime

    async def read_site_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        company = self._get(cid)
        site = (company.brain.paths.workspace / "site").resolve()
        target = (site / (path or "index.html")).resolve()
        if not target.is_relative_to(site):
            raise NotFound("There's no page at that address.")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            raise NotFound("There's no page at that address.")
        mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        return target.read_bytes(), mime

    # ------------------------------------------------------------------ sharing
    async def publish(self, cid: CompanyId, opts: ShareOptions) -> ShareLink:
        company = self._get(cid)
        state = company.brain.state
        token = secrets.token_urlsafe(16)

        # Raises PublishBlocked if the scan finds anything. The link is only
        # marked servable after a clean scan — fail closed.
        build_snapshot(
            company_root=company.brain.paths.root,
            share_root=self.root / "_share",
            token=token,
            company_name=state.name,
            one_liner=state.charter.one_liner if state.charter else "",
            progress=state.progress,
            roster=company.company().roster,
            shifts=company.shifts,
            artifacts=list(state.artifacts.values()),
            decisions=list(state.decisions.values()),
            objections=list(state.objections.values()),
            include_shifts=opts.include_shifts,
            include_artifacts=opts.include_artifacts,
        )

        link = ShareLink(
            token=token,
            url=f"/public/{token}",
            created_at=datetime.now(UTC),
            include_shifts=opts.include_shifts,
            include_artifacts=opts.include_artifacts,
            scanned_clean_at=datetime.now(UTC),
        )
        company.brain.record_metric("share", link.model_dump(mode="json"))
        return link

    async def unpublish(self, cid: CompanyId) -> None:
        company = self._get(cid)
        link = company.share
        if link:
            import shutil

            shutil.rmtree(self.root / "_share" / link.token, ignore_errors=True)
        company.brain.record_metric("share", None)

    async def get_public_snapshot(self, token: str) -> PublicSnapshot:
        for company in self._companies.values():
            link = company.share
            if not link or link.token != token:
                continue
            if link.scanned_clean_at is None or link.revoked_at is not None:
                raise NotFound("That share link isn't available.")
            state = company.brain.state
            return PublicSnapshot(
                company_name=state.name,
                one_liner=state.charter.one_liner if state.charter else "",
                progress=state.progress,
                roster=company.company().roster,
                shifts=company.shifts if link.include_shifts else [],
                artifacts=[a for a in state.artifacts.values() if a.public]
                if link.include_artifacts
                else [],
                decisions=list(state.decisions.values()),
                published_at=link.created_at,
            )
        raise NotFound("That share link isn't available.")

    # ---------------------------------------------------------------- streaming
    async def stream(self, cid: CompanyId, since_seq: int | None = None):
        async for event in self._get(cid).bus.subscribe(since_seq):
            yield event

    async def replay(
        self, cid: CompanyId, since_seq: int, limit: int = 500
    ) -> list[ShiftEvent]:
        return self._get(cid).bus.replay(since_seq, limit)

    # ------------------------------------------------------------- shift record
    def _write_shift_record(self, company: CompanyRuntime, shift: Shift) -> None:
        """The shift report is engine-generated from structured facts.

        The employees do not write it. A report card written by the thing being
        reported on is worthless.
        """
        brain = company.brain
        produced = [
            a for a in brain.state.artifacts.values() if a.produced_in_shift == shift.id
        ]
        objections = [
            o for o in brain.state.objections.values() if o.shift_id == shift.id
        ]
        lines = [
            f"# Shift {shift.number}",
            "",
            f"{shift.summary or ''}",
            "",
            "## What was on the agenda",
            "",
            *[f"- {item}" for item in shift.agenda],
            "",
            "## What was produced",
            "",
            *[f"- {a.title} ({a.confidence})" for a in produced],
            "",
            "## What the critic flagged",
            "",
            *[f"- [{o.severity}] {o.text}" for o in objections],
            "",
            f"Cost: ${shift.cost}",
            "",
        ]
        brain.paths.shifts.mkdir(parents=True, exist_ok=True)
        brain.paths.shift_md(shift.number).write_text(
            "\n".join(lines), encoding="utf-8"
        )
        brain.paths.shift_json(shift.number).write_text(
            shift.model_dump_json(indent=2), encoding="utf-8"
        )
