"""What every engine shares.

An engine differs from another engine in exactly one place: where the words and
the work come from during a shift. Everything else — the company registry, the
durable brain, the read models, the vault, the workspace, the share gate, the
kill switch — is the same product behaviour, and it lives here once.

No ``openhands.*`` imports in this module, ever. Everything here is about the
company rather than the model, and it stays readable — and testable — without
the SDK in the way.
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
from werkhaus.contract.brains import (
    BRAINS_BY_ID,
    VAULT_BASE_URL,
    VAULT_KEY,
    VAULT_MODEL,
    BrainChoice,
    provider_for,
)
from werkhaus.contract.catalog import CATALOG
from werkhaus.contract.catalog import field as catalog_field
from werkhaus.contract.catalog import refused_names as catalog_refused
from werkhaus.contract.catalog import spec as catalog_spec
from werkhaus.contract.credentials import CredentialClass, classify
from werkhaus.contract.directory import McpConnection
from werkhaus.contract.engine import Engine
from werkhaus.contract.errors import (
    ArtifactNotFound,
    BudgetExceeded,
    CompanyHalted,
    CompanyNotFound,
    CredentialRejected,
    ForbiddenCredential,
    IntegrationNotFound,
    IntegrationUnavailable,
    NotFound,
    OutOfShifts,
    ShiftAlreadyRunning,
    ShiftNotFound,
    ValidationFailed,
    WerkhausError,
)
from werkhaus.contract.events import ShiftEvent
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.integrations import (
    BACKEND_STEPS,
    Availability,
    Connection,
    ConnectionStatus,
    IntegrationSpec,
    IntegrationState,
    ProvisionedResource,
    SpendPolicy,
)
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
from werkhaus.engines.verify import HttpVerifier, Verifier, check_brain
from werkhaus.share.scanner import scan_text
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

    def __init__(
        self, root: str | Path = "./data", verifier: Verifier | None = None
    ) -> None:
        self.root = Path(root)
        self._companies: dict[CompanyId, CompanyRuntime] = {}
        self._site_scan_cache: dict[tuple[str, int], bool] = {}
        # Injected in tests. In production a credential is only ever stored
        # after the provider itself has confirmed it works.
        self.verifier: Verifier = verifier or HttpVerifier()

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

    # ------------------------------------------------------------ connections
    def _connection(
        self, company: CompanyRuntime, entry: IntegrationSpec
    ) -> Connection:
        """Derived: what we hold, what happened, and what the plan allows.

        Nothing here is stored. A "connected" flag can disagree with the vault;
        this cannot.
        """
        allowance = self.allowance()
        vault = self._vault_read(company)
        history = company.brain.state.integrations.get(entry.id, {})
        present = [f.name for f in entry.fields if f.name in vault]
        wanted = [f.name for f in entry.fields if f.required and not f.team_fills_it]
        have_all = bool(wanted) and all(name in vault for name in wanted)

        blocks = [
            step
            for step in BACKEND_STEPS
            if entry.id in step.needs and not have_all
        ]
        unavailable: str | None = None
        if entry.availability is Availability.MANUAL_SETUP:
            unavailable = entry.manual_note
        elif entry.id not in allowance.integrations:
            unavailable = (
                f"{entry.display_name} isn't part of the {allowance.label} plan."
            )

        if unavailable and not have_all:
            status = ConnectionStatus.UNAVAILABLE
        elif not have_all:
            status = ConnectionStatus.NOT_CONNECTED
        elif history.get("event") == "failed":
            status = ConnectionStatus.NEEDS_ATTENTION
        else:
            status = ConnectionStatus.CONNECTED

        return Connection(
            provider=entry.id,
            status=status,
            fields_present=present,
            hints={
                name: self._vault_item(name, vault[name]).hint
                for name in present
                if not entry.availability == Availability.MANUAL_SETUP
            },
            connected_at=_maybe_time(history.get("connected_at")),
            verified_at=_maybe_time(history.get("verified_at")),
            message=history.get("message") or None,
            scope_note=history.get("scope_note"),
            blocks=[step.title for step in blocks],
            unavailable_reason=unavailable,
        )

    async def list_integrations(self, cid: CompanyId) -> list[IntegrationState]:
        company = self._get(cid)
        return [
            IntegrationState(spec=entry, connection=self._connection(company, entry))
            for entry in CATALOG
        ]

    async def connect_integration(
        self, cid: CompanyId, provider: str, values: dict[str, str]
    ) -> IntegrationState:
        """Check, then store. Never the other way round.

        A key that fails during a shift costs a whole shift, and on the free
        plan there are three. So the provider confirms the credential while the
        founder is still on the page, and a value that does not pass is never
        written anywhere.
        """
        company = self._get(cid)
        try:
            entry = catalog_spec(provider)
        except KeyError:
            raise IntegrationNotFound() from None

        if entry.availability is Availability.MANUAL_SETUP:
            raise IntegrationUnavailable(
                f"{entry.display_name} can't be connected from here yet.",
                hint=entry.manual_note,
            )
        allowance = self.allowance()
        if entry.id not in allowance.integrations:
            raise IntegrationUnavailable(
                f"{entry.display_name} isn't part of the {allowance.label} plan.",
                hint="Upgrading adds it. Everything you've built stays as it is.",
            )

        clean: dict[str, str] = {}
        for name, raw in values.items():
            self._refuse_forbidden(name)
            spec_field = catalog_field(provider, name)
            if spec_field is None:
                raise ValidationFailed(
                    f"{entry.display_name} doesn't take a value called {name}."
                )
            value = raw.strip()
            if spec_field.pattern and not re.match(spec_field.pattern, value):
                raise CredentialRejected(
                    spec_field.help
                    or f"That doesn't look like {spec_field.label.lower()}.",
                )
            clean[name] = value

        missing = [
            f.name
            for f in entry.fields
            if f.required and not f.team_fills_it and f.name not in clean
        ]
        if missing:
            raise ValidationFailed(
                f"{entry.display_name} still needs "
                f"{catalog_field(provider, missing[0]).label.lower()}."  # type: ignore[union-attr]
            )

        result = await self.verifier.check(provider, clean)
        if not result.ok:
            company.brain.record_integration(
                provider=provider,
                event="failed",
                fields=sorted(clean),
                message=result.message,
            )
            raise CredentialRejected(result.message, hint=result.hint)

        vault = self._vault_read(company)
        stamp = datetime.now(UTC).isoformat()
        for name, value in {**clean, **result.facts}.items():
            vault[name] = {"value": value, "added_at": stamp}
        self._vault_write(company, vault)
        company.brain.record_integration(
            provider=provider,
            event="connected",
            fields=sorted({**clean, **result.facts}),
            message=result.message,
            scope_note=result.scope_note,
        )
        said = f"Ada: {entry.display_name} is connected."
        if result.scope_note:
            said = f"{said} {result.scope_note}"
        company.bus.emit(K.ROLE_SAID, said)
        return IntegrationState(
            spec=entry, connection=self._connection(company, entry)
        )

    async def verify_integration(
        self, cid: CompanyId, provider: str
    ) -> IntegrationState:
        """Re-check a connection we already hold, on demand."""
        company = self._get(cid)
        try:
            entry = catalog_spec(provider)
        except KeyError:
            raise IntegrationNotFound() from None

        vault = self._vault_read(company)
        held = {
            f.name: vault[f.name]["value"] for f in entry.fields if f.name in vault
        }
        if not held:
            raise IntegrationNotFound(
                f"{entry.display_name} isn't connected yet.",
            )
        result = await self.verifier.check(provider, held)
        company.brain.record_integration(
            provider=provider,
            event="verified" if result.ok else "failed",
            fields=sorted(held),
            message=result.message,
            scope_note=result.scope_note,
        )
        return IntegrationState(
            spec=entry, connection=self._connection(company, entry)
        )

    async def disconnect_integration(self, cid: CompanyId, provider: str) -> None:
        company = self._get(cid)
        try:
            entry = catalog_spec(provider)
        except KeyError:
            raise IntegrationNotFound() from None
        vault = self._vault_read(company)
        removed = [f.name for f in entry.fields if vault.pop(f.name, None) is not None]
        self._vault_write(company, vault)
        company.brain.record_integration(
            provider=provider,
            event="disconnected",
            fields=sorted(removed),
            message=f"{entry.display_name} was disconnected.",
        )

    # ------------------------------------------------------- mcp connections
    MCP_METRIC = "mcp_servers"
    _MCP_NAME = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

    def _mcp_rows(self, company: CompanyRuntime) -> list[dict[str, Any]]:
        return list(company.brain.state.metrics.get(self.MCP_METRIC) or [])

    async def list_mcp(self, cid: CompanyId) -> list[McpConnection]:
        company = self._get(cid)
        vault = self._vault_read(company)
        out = []
        for row in self._mcp_rows(company):
            missing = [n for n in row.get("env_names", []) if n not in vault]
            out.append(
                McpConnection(
                    **row,
                    note="Some of what it needs is missing." if missing else None,
                )
            )
        return out

    async def add_mcp(  # noqa: PLR0913
        self,
        cid: CompanyId,
        name: str,
        label: str,
        transport: str = "stdio",
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        directory_url: str | None = None,
    ) -> McpConnection:
        """Connect any MCP server, by address or by command.

        This is what makes a directory of six thousand servers usable without
        pretending we have tested them: the founder brings what the server's
        own publisher documented, and it is stored the same way every other
        credential is.
        """
        company = self._get(cid)
        name = name.strip().lower().replace("-", "_")
        if not self._MCP_NAME.match(name):
            raise ValidationFailed(
                "Give it a short name in lowercase letters, like `shopify`.",
            )
        if transport == "stdio" and not (command or "").strip():
            raise ValidationFailed("A local server needs a command to start it.")
        if transport != "stdio" and not (url or "").strip():
            raise ValidationFailed("A remote server needs an address.")
        rows = [r for r in self._mcp_rows(company) if r["name"] != name]

        vault = self._vault_read(company)
        stamp = datetime.now(UTC).isoformat()
        env_names = []
        for key, value in (env or {}).items():
            key = key.strip()
            if not key or not value.strip():
                continue
            self._refuse_forbidden(key)
            stored = f"MCP_{name}_{key}".upper()
            vault[stored] = {"value": value.strip(), "added_at": stamp}
            env_names.append(stored)
        self._vault_write(company, vault)

        row = {
            "name": name,
            "label": label.strip() or name,
            "transport": transport,
            "url": (url or "").strip() or None,
            "command": (command or "").strip() or None,
            "args": list(args or []),
            "env_names": env_names,
            "directory_url": directory_url,
            "added_at": stamp,
            "verified": False,
        }
        rows.append(row)
        company.brain.record_metric(self.MCP_METRIC, rows)
        company.brain.record_integration(
            provider=f"mcp:{name}",
            event="connected",
            fields=env_names,
            message=f"{row['label']} is connected.",
        )
        return McpConnection(**row)

    async def remove_mcp(self, cid: CompanyId, name: str) -> None:
        company = self._get(cid)
        rows = self._mcp_rows(company)
        row = next((r for r in rows if r["name"] == name), None)
        if row is None:
            raise IntegrationNotFound("That server isn't connected.")
        vault = self._vault_read(company)
        for key in row.get("env_names", []):
            vault.pop(key, None)
        self._vault_write(company, vault)
        company.brain.record_metric(
            self.MCP_METRIC, [r for r in rows if r["name"] != name]
        )

    def mcp_env(self, company: CompanyRuntime, row: dict[str, Any]) -> dict[str, str]:
        """The values a connected server needs, read at shift time."""
        vault = self._vault_read(company)
        out = {}
        for stored in row.get("env_names", []):
            original = stored[len(f"MCP_{row['name']}_") :]
            value = (vault.get(stored) or {}).get("value")
            if value:
                out[original] = value
        return out

    # ------------------------------------------------------------------ brain
    async def get_brain(self, cid: CompanyId) -> BrainChoice:
        """What this company thinks with, and whether it may be changed."""
        company = self._get(cid)
        allowance = self.allowance()
        vault = self._vault_read(company)
        model = (vault.get(VAULT_MODEL) or {}).get("value") or None
        provider = provider_for(model or "")
        chosen = provider.id if provider else ("custom" if model else None)
        key_entry = None
        for name in ([provider.key_name] if provider else []) + [VAULT_KEY]:
            if name in vault:
                key_entry = vault[name]
                break
        return BrainChoice(
            provider=chosen,
            model=model.split("/", 1)[-1] if model and "/" in model else model,
            base_url=(vault.get(VAULT_BASE_URL) or {}).get("value") or None,
            key_hint=self._vault_item("k", key_entry).hint if key_entry else None,
            configured=bool(model and key_entry),
            editable=allowance.byok and allowance.model_choice,
            note=None
            if allowance.byok
            else "Choosing your own model comes with the bigger plan. Until "
            "then the team thinks with ours, and nothing you save here is used.",
        )

    async def set_brain(
        self,
        cid: CompanyId,
        provider: str,
        model: str,
        key: str,
        base_url: str | None = None,
    ) -> BrainChoice:
        """Check the key reaches a model, then store it. Never the other way
        round: finding out mid-shift costs a whole shift."""
        company = self._get(cid)
        brain = BRAINS_BY_ID.get(provider)
        if brain is None:
            raise IntegrationNotFound("We don't know that provider.")
        if not self.allowance().byok:
            raise IntegrationUnavailable(
                "Choosing your own model comes with the bigger plan.",
                hint="Everything you have built stays exactly as it is.",
            )
        model = model.strip()
        if not model:
            raise ValidationFailed("Which model should the team think with?")
        if brain.needs_base_url and not (base_url or "").strip():
            raise ValidationFailed("That one needs an address as well as a key.")
        if avoid := brain.avoid.get(model):
            raise CredentialRejected(f"That model {avoid}.")

        result = await check_brain(
            provider, key.strip(), (base_url or "").strip(), model
        )
        if not result.ok:
            raise CredentialRejected(result.message, hint=result.hint)

        vault = self._vault_read(company)
        stamp = datetime.now(UTC).isoformat()
        vault[brain.key_name] = {"value": key.strip(), "added_at": stamp}
        vault[VAULT_MODEL] = {"value": f"{brain.prefix}/{model}", "added_at": stamp}
        if brain.needs_base_url:
            vault[VAULT_BASE_URL] = {
                "value": (base_url or "").strip(),
                "added_at": stamp,
            }
        else:
            vault.pop(VAULT_BASE_URL, None)
        self._vault_write(company, vault)
        company.brain.record_integration(
            provider=f"brain:{provider}",
            event="connected",
            fields=[brain.key_name, VAULT_MODEL],
            message=f"The team thinks with {model}.",
        )
        return await self.get_brain(cid)

    async def list_resources(self, cid: CompanyId) -> list[ProvisionedResource]:
        company = self._get(cid)
        return sorted(company.brain.state.resources.values(), key=lambda r: r.at)

    async def get_spend_policy(self, cid: CompanyId) -> SpendPolicy:
        raw = self._get(cid).brain.state.metrics.get("spend_policy")
        return SpendPolicy.model_validate(raw) if raw else SpendPolicy()

    async def set_spend_policy(
        self, cid: CompanyId, policy: SpendPolicy
    ) -> SpendPolicy:
        company = self._get(cid)
        company.brain.record_metric("spend_policy", policy.model_dump(mode="json"))
        return policy

    def _refuse_forbidden(self, name: str) -> None:
        """The one credential we decline by name.

        A database master key bypasses row-level security completely, and
        giving one to an agent is the specific mistake behind the best-known
        leak of this kind. Refusing it mechanically — here and in the raw
        vault — means nobody arrives at that configuration by accident.
        """
        if name.strip().upper() in catalog_refused():
            raise ForbiddenCredential()

    def _secret_values(self, company: CompanyRuntime) -> list[str]:
        """The stored values that must never appear in anything public.

        A public credential is deliberately absent: the anon key is *meant* to
        ship in the page, and listing it here would block every site that talks
        to its own database from ever being published.
        """
        vault = self._vault_read(company)
        return [
            entry["value"]
            for name, entry in vault.items()
            if classify(name) is not CredentialClass.PUBLIC
            and len(entry.get("value", "")) >= 8
        ]

    async def list_vault(self, cid: CompanyId) -> list[VaultItem]:
        vault = self._vault_read(self._get(cid))
        return [self._vault_item(n, e) for n, e in sorted(vault.items())]

    async def set_vault(self, cid: CompanyId, name: str, value: str) -> VaultItem:
        # The guided flow and the raw vault obey the same refusal, or the
        # escape hatch quietly becomes the way round the safety rule.
        self._refuse_forbidden(name)
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
        data = target.read_bytes()
        if target.suffix.lower() in self.SITE_SCAN_SUFFIXES and self._site_leaks(
            company, target, data
        ):
            return _PREVIEW_BLOCKED.encode("utf-8"), "text/html"
        return data, mime

    SITE_SCAN_SUFFIXES = frozenset({".html", ".htm", ".js", ".mjs", ".css", ".json"})

    def _site_leaks(
        self, company: CompanyRuntime, target: Path, data: bytes
    ) -> bool:
        """Is this preview file carrying a key it shouldn't?

        The publish gate runs at publish time, but this preview *is* a real web
        page served over the real API — a key baked into it is live the moment
        it is written, long before anyone presses share. Cached on mtime so a
        page being reloaded doesn't re-scan on every request.
        """
        try:
            stamp = target.stat().st_mtime_ns
        except OSError:
            return False
        key = (str(target), stamp)
        cached = self._site_scan_cache.get(key)
        if cached is None:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                return False
            findings = scan_text(
                text,
                path=target.name,
                extra=self._secret_values(company),
            )
            leaking = [f for f in findings if f.kind != "absolute home path"]
            cached = bool(leaking)
            if cached:
                logger.warning(
                    "site preview withheld for %s: %s",
                    company.id,
                    ", ".join(sorted({f.kind for f in leaking})),
                )
                self._flag_leaking_page(company, target)
            self._site_scan_cache = {key: cached}  # one page's worth is enough
        return cached

    def _flag_leaking_page(self, company: CompanyRuntime, target: Path) -> None:
        """Turn the security stop into work, once. A blocked page the team is
        never told about is a page nobody fixes."""
        title = f"Move the private key out of {target.name} into a server function"
        if any(
            t.title == title and t.status is not TaskStatus.DONE
            for t in company.brain.state.tasks.values()
        ):
            return
        company.brain.add_task(
            title=title, shift_id=None, priority=1, actor="chief"
        )
        company.bus.emit(
            K.TASK_ADDED,
            "One of the website's files has a private key in it, so we're not "
            "showing it. The team will move it somewhere safe.",
        )

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
            secret_values=self._secret_values(company),
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


_FUNCTION_WORDS = frozenset(
    "a an the and or but for of to in on at by with from that who which "
    "your our my their this these those is are was were be been as into "
    "over under about after before while when where how why".split()
)


def name_from_idea(idea: str) -> str:
    """A provisional company name from the founder's own opening words.

    Shared by every engine on purpose. A company named from anywhere other than
    the founder's own words is a company that belongs to somebody else's idea.

    Takes the words up to the first function word, which is usually where the
    thing stops being named and starts being described: "a booking tool for
    mobile dog groomers" is Booking Tool, not Booking Tool For. The founder can
    rename it; a real naming pass is a shift's job.
    """
    picked: list[str] = []
    for raw in idea.split():
        word = raw.strip(".,!?:;\"'()[]")
        if not word:
            continue
        if word.lower() in _FUNCTION_WORDS:
            if picked:
                break  # the description starts here
            continue  # a leading "A"/"The" is not part of the name
        picked.append(word)
        if len(picked) == 3:
            break
    return " ".join(w.capitalize() for w in picked) or "New Company"


_PREVIEW_BLOCKED = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>This page isn't being shown</title>
<style>
 body{font:16px/1.55 system-ui,sans-serif;margin:0;padding:3rem 1.5rem;
      color:#1a1a1a;background:#fbfaf7}
 main{max-width:34rem;margin:0 auto}
 h1{font-size:1.25rem;margin:0 0 .75rem}
 p{margin:0 0 .75rem;color:#444}
</style></head>
<body><main>
<h1>We're not showing this page</h1>
<p>One of its files has a private key written into it, and this preview is a
real web page — anyone with the address could read it.</p>
<p>Nothing is lost. The team has been given the job of moving that key into a
server function, where it belongs, and the page will appear again once it has.</p>
</main></body></html>
"""


def _maybe_time(raw: str | None) -> datetime | None:
    return datetime.fromisoformat(raw) if raw else None
