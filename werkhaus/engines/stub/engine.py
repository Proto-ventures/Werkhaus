"""The stub engine.

Fakes the *content* of a shift and nothing else. It runs the same five phases the
real ShiftRunner will run, with the same concurrency cap, the same budget layers,
the same halt semantics — and, since M2, writes through the same
:class:`BrainStore`. So every stub shift exercises the durable layer that
OpenHandsEngine will inherit, and the only thing left to swap in M3/M4 is where
the words come from.

Two deliberate choices that look like bugs and aren't:

* **Shifts are slow by default.** A real role run is 2-8 minutes. If the team only
  ever sees a 20-second shift, nobody builds resumability, virtualisation or
  "leave and come back", and those are exactly the three things that break at real
  latency. Pass ``speed`` to go faster for demos.
* **Failure is reachable from a tag in the description.** Four of the five
  scenarios end badly. A stub that only knows how to succeed teaches the UI to
  only render success.
"""

from __future__ import annotations

import asyncio
import logging
import random
import secrets
from collections.abc import AsyncIterator
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
    ShiftAlreadyRunning,
    ShiftNotFound,
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
    Decision,
    LedgerEntry,
    Objection,
    Progress,
    PublicSnapshot,
    RoleStatus,
    ShareLink,
    ShareOptions,
    Shift,
    ShiftId,
    ShiftPhase,
    ShiftStatus,
    Task,
    TaskStatus,
)
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.roster import display_name
from werkhaus.engines.stub.scenario import (
    ScenarioRoleWork,
    list_scenarios,
    load_scenario,
)
from werkhaus.engines.stub.state import StubCompany
from werkhaus.share.snapshot import build_snapshot

logger = logging.getLogger(__name__)

MAX_CONCURRENT_ROLES = 3
"""Not for correctness — for LLM rate limits, and because seven simultaneous
activity streams is an unreadable dashboard."""

CENTS = Decimal("0.01")


def cents(amount: Decimal) -> Decimal:
    """Money is money. Dividing a role's budget across its activities produces
    things like 6.8399999999999999998, and that must never reach the API."""
    return amount.quantize(CENTS)


_PHASE_TEXT: dict[ShiftPhase, str] = {
    ShiftPhase.PLANNING: "Ada is working out what the team should do this shift.",
    ShiftPhase.WORKING: "The team is working.",
    ShiftPhase.REVIEW: "Vera is reviewing what everyone produced.",
    ShiftPhase.INTEGRATING: "Filing everything away.",
    ShiftPhase.CLOSING: "Writing up the shift.",
}


class StubEngine(Engine):
    def __init__(
        self,
        root: str | Path = "./data",
        seed: int = 42,
        scenario: str = "happy",
        speed: float = 1.0,
    ) -> None:
        self.root = Path(root)
        self.seed = seed
        self.default_scenario = scenario
        self.speed = max(0.01, speed)
        self._companies: dict[CompanyId, StubCompany] = {}

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
        logger.info("stub engine ready: %d companies", len(self._companies))

    async def aclose(self) -> None:
        handles = [
            c.task_handle
            for c in self._companies.values()
            if c.task_handle and not c.task_handle.done()
        ]
        for handle in handles:
            handle.cancel()
        await asyncio.gather(*handles, return_exceptions=True)

    def _open(self, cid: str, root: Path) -> StubCompany:
        brain = BrainStore(root, cid)
        name = brain.state.metrics.get("scenario", self.default_scenario)
        scenario = load_scenario(name)
        bus = CompanyBus(cid, CompanyPaths(root).events)
        return StubCompany(brain, scenario, bus)

    def _get(self, cid: CompanyId) -> StubCompany:
        company = self._companies.get(cid)
        if company is None:
            raise CompanyNotFound()
        return company

    # --------------------------------------------------------------- companies
    async def create_company(self, idea: str, name: str | None = None) -> Company:
        scenario_name = self.default_scenario
        for candidate in list_scenarios():
            tag = f"[scenario:{candidate}]"
            if tag in idea:
                scenario_name = candidate
                idea = idea.replace(tag, "").strip()
                break
        scenario = load_scenario(scenario_name)

        cid = f"co_{secrets.token_hex(3)}"
        root = self.root / cid
        brain = BrainStore(root, cid)
        bus = CompanyBus(cid, CompanyPaths(root).events)
        bus.bind_loop(asyncio.get_running_loop())

        charter = Charter(
            idea=idea or scenario.charter.idea,
            one_liner=scenario.charter.one_liner,
            audience=scenario.charter.audience,
            success_looks_like=scenario.charter.success_looks_like,
            constraints=list(scenario.charter.constraints),
            tone=scenario.charter.tone,
        )
        brain.set_charter(charter, name or scenario.company_name)
        brain.record_metric("scenario", scenario.name)
        brain.record_metric("created_at", datetime.now(UTC).isoformat())
        brain.record_metric("budget_cap", str(cents(Decimal(str(scenario.budget_cap)))))
        brain.record_metric(
            "per_shift_cap", str(cents(Decimal(str(scenario.per_shift_cap))))
        )
        CompanyPaths(root).charter.write_text(
            f"# {brain.state.name}\n\n{charter.one_liner}\n\n"
            f"**Who it's for:** {charter.audience}\n\n"
            f"**Done means:** {charter.success_looks_like}\n",
            encoding="utf-8",
        )

        company = StubCompany(brain, scenario, bus)
        self._companies[cid] = company
        return company.company()

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
    async def start_shift(self, cid: CompanyId, focus: str | None = None) -> Shift:
        company = self._get(cid)
        if company.halted:
            raise CompanyHalted()
        if company.task_handle and not company.task_handle.done():
            raise ShiftAlreadyRunning()
        if company.spent >= company.cap:
            raise BudgetExceeded()

        shift = company.brain.open_shift(
            number=len(company.brain.state.shifts) + 1,
            agenda=[focus] if focus else list(company.scenario.agenda),
        )
        company.task_handle = asyncio.create_task(self._run_shift(company, shift.id))
        return shift

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

    async def _cancel(self, company: StubCompany) -> None:
        handle = company.task_handle
        if handle and not handle.done():
            handle.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(handle), timeout=1.5)
            except (TimeoutError, asyncio.CancelledError):
                pass
        company.task_handle = None
        company.clear_activity()

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
    async def stream(
        self, cid: CompanyId, since_seq: int | None = None
    ) -> AsyncIterator[ShiftEvent]:
        async for event in self._get(cid).bus.subscribe(since_seq):
            yield event

    async def replay(
        self, cid: CompanyId, since_seq: int, limit: int = 500
    ) -> list[ShiftEvent]:
        return self._get(cid).bus.replay(since_seq, limit)

    # ====================================================================== shift
    async def _sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds) / self.speed)

    async def _run_shift(self, company: StubCompany, sid: ShiftId) -> None:
        brain = company.brain
        scenario = company.scenario
        shift = brain.state.shifts[sid]
        rng = random.Random(self.seed + shift.number)
        spent = Decimal("0")

        try:
            company.bus.emit(
                K.SHIFT_STARTED, f"Shift {shift.number} has started.", shift_id=sid
            )
            await self._phase(company, sid, ShiftPhase.PLANNING)
            await self._sleep(4)
            for item in shift.agenda:
                brain.add_task(title=item, shift_id=sid, priority=2, actor="chief")
                company.bus.emit(K.TASK_ADDED, f"On the agenda: {item}", shift_id=sid)
                await self._sleep(1.2)

            await self._phase(company, sid, ShiftPhase.WORKING)
            budget_hit = asyncio.Event()
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_ROLES)

            async def work(entry: ScenarioRoleWork) -> Decimal:
                async with semaphore:
                    if budget_hit.is_set():
                        return Decimal("0")
                    return await self._role(company, sid, entry, rng, budget_hit)

            spent += sum(
                await asyncio.gather(*(work(e) for e in scenario.work)), Decimal("0")
            )

            if budget_hit.is_set():
                await self._close(company, sid, ShiftStatus.BUDGET_EXCEEDED, spent)
                return
            if any(a.answered_at is None for a in brain.state.attention.values()):
                await self._close(
                    company, sid, ShiftStatus.COMPLETED, spent, blocked=True
                )
                return

            # Review always runs and always last, even out of budget. A shift
            # that skipped the critic is a shift that shipped unchallenged slop.
            await self._phase(company, sid, ShiftPhase.REVIEW)
            spent += await self._critic(company, sid, rng)

            await self._phase(company, sid, ShiftPhase.INTEGRATING)
            await self._sleep(5)

            await self._close(company, sid, ShiftStatus.COMPLETED, spent)

        except asyncio.CancelledError:
            brain.close_shift(
                sid, status=ShiftStatus.ABORTED,
                failure_reason="You stopped this shift.", cost=cents(spent),
            )
            company.clear_activity()
            raise
        except Exception:
            logger.exception("stub shift %s blew up", sid)
            brain.close_shift(
                sid, status=ShiftStatus.FAILED,
                failure_reason="Something went wrong and the shift stopped.",
                cost=cents(spent),
            )
            company.clear_activity()
            company.bus.emit(
                K.SHIFT_FAILED,
                "The shift stopped early. Nothing that was already done was lost.",
                shift_id=sid,
            )

    async def _phase(
        self, company: StubCompany, sid: ShiftId, phase: ShiftPhase
    ) -> None:
        company.brain.update_shift(sid, phase=phase)
        company.bus.emit(
            K.PHASE_CHANGED, _PHASE_TEXT[phase], shift_id=sid, payload={"phase": phase}
        )

    async def _role(
        self,
        company: StubCompany,
        sid: ShiftId,
        entry: ScenarioRoleWork,
        rng: random.Random,
        budget_hit: asyncio.Event,
    ) -> Decimal:
        brain = company.brain
        rid = entry.role
        name = display_name(rid)
        company.roles[rid]["status"] = RoleStatus.WORKING
        company.bus.emit(
            K.ROLE_STARTED, f"{name} started work.", shift_id=sid, role_id=rid
        )

        shift = brain.state.shifts[sid]
        if rid not in shift.roles_active:
            brain.update_shift(sid, roles_active=[*shift.roles_active, rid])

        claimed: list[str] = []
        for title in entry.tasks_claimed:
            task = brain.add_task(title=title, shift_id=sid, owner=rid, actor=rid)
            brain.claim_task(task.id, role_id=rid, shift_id=sid)
            claimed.append(task.id)
            company.bus.emit(
                K.TASK_CLAIMED, f"{name} took on: {title}", shift_id=sid,
                role_id=rid, ref=task.id,
            )

        activities = list(entry.activities) * max(1, company.scenario.activity_repeat)
        base = entry.duration / max(1, len(activities))
        step = Decimal(str(entry.cost)) / max(1, len(activities))
        spent = Decimal("0")

        for index, activity in enumerate(activities):
            # Jitter is seeded per role, so a role's own sequence is reproducible
            # even though the interleaving between roles is not.
            await self._sleep(base * rng.uniform(0.6, 1.4))
            company.roles[rid]["activity"] = f"{name} {activity}"
            company.bus.emit(
                K.ROLE_ACTIVITY, f"{name} {activity}", shift_id=sid, role_id=rid
            )

            spent += step
            if index % 4 == 0 or index == len(activities) - 1:
                company.bus.emit(
                    K.BUDGET_SPENT, "", shift_id=sid, role_id=rid,
                    payload={
                        "spent": str(cents(company.spent + spent)),
                        "cap": str(company.cap),
                    },
                )

            # Layer 4: the live watchdog. A per-run cap is only checked between
            # iterations, so without this the overshoot is unbounded.
            if company.spent + spent >= company.cap:
                budget_hit.set()
                company.roles[rid]["status"] = RoleStatus.IDLE
                company.roles[rid]["activity"] = None
                brain.record_cost(
                    spent, role_id=rid, shift_id=sid, note=f"{name}'s work this shift"
                )
                company.bus.emit(
                    K.BUDGET_EXCEEDED,
                    "The company has spent its whole budget, so everyone stopped.",
                    shift_id=sid, role_id=rid,
                )
                return spent

            if entry.attention and index == len(activities) - 1:
                request = brain.ask(
                    question=entry.attention.question,
                    options=list(entry.attention.options),
                    role_id=rid,
                    shift_id=sid,
                )
                company.answered[request.id] = asyncio.Event()
                company.roles[rid]["status"] = RoleStatus.BLOCKED
                company.roles[rid]["activity"] = None
                company.bus.emit(
                    K.ATTENTION_NEEDED, f"{name} needs an answer from you.",
                    detail=request.question, shift_id=sid, role_id=rid, ref=request.id,
                    payload={"options": request.options, "request_id": request.id},
                )
                brain.record_cost(
                    spent, role_id=rid, shift_id=sid, note=f"{name}'s work this shift"
                )
                return spent

        if entry.fails:
            company.roles[rid]["status"] = RoleStatus.FAILED
            company.roles[rid]["activity"] = None
            company.bus.emit(
                K.ROLE_FAILED,
                f"{name} hit a problem and stopped. "
                "The team will pick this up next shift.",
                detail=entry.failure_reason, shift_id=sid, role_id=rid,
            )
            brain.record_cost(
                spent, role_id=rid, shift_id=sid, note=f"{name}'s work this shift"
            )
            return spent

        for spec in entry.artifacts:
            self._write_artifact(company, sid, rid, spec)
        for spec in entry.decisions:
            decision = brain.record_decision(
                title=spec.title,
                rationale=spec.rationale,
                alternatives_rejected=list(spec.alternatives_rejected),
                role_id=rid,
                shift_id=sid,
                reversible=spec.reversible,
            )
            company.bus.emit(
                K.DECISION_MADE, f"{name} decided: {spec.title}",
                detail=spec.rationale, shift_id=sid, role_id=rid, ref=decision.id,
            )
        for title in entry.tasks_added:
            task = brain.add_task(title=title, shift_id=sid, actor=rid)
            company.bus.emit(
                K.TASK_ADDED, f"{name} added: {title}", shift_id=sid,
                role_id=rid, ref=task.id,
            )
        for task_id in claimed:
            brain.complete_task(task_id, role_id=rid, shift_id=sid)
            company.bus.emit(
                K.TASK_DONE,
                f"{name} finished: {brain.state.tasks[task_id].title}",
                shift_id=sid, role_id=rid, ref=task_id,
            )

        if entry.says:
            company.bus.emit(
                K.ROLE_SAID, f"{name}: {entry.says}", shift_id=sid, role_id=rid
            )

        company.roles[rid]["status"] = RoleStatus.DONE
        company.roles[rid]["activity"] = None
        company.bus.emit(
            K.ROLE_FINISHED,
            f"{name} finished for this shift.",
            shift_id=sid,
            role_id=rid,
        )
        brain.record_cost(
            spent, role_id=rid, shift_id=sid, note=f"{name}'s work this shift"
        )
        return spent

    async def _critic(
        self, company: StubCompany, sid: ShiftId, rng: random.Random
    ) -> Decimal:
        brain = company.brain
        rid, name = "critic", display_name("critic")
        company.roles[rid]["status"] = RoleStatus.WORKING
        company.bus.emit(
            K.ROLE_STARTED, f"{name} started reviewing the shift.",
            shift_id=sid, role_id=rid,
        )
        for activity in (
            "is reading everything produced this shift",
            "is checking which claims have a source behind them",
            "is looking for the weakest number in the room",
        ):
            await self._sleep(6 * rng.uniform(0.6, 1.4))
            company.roles[rid]["activity"] = f"{name} {activity}"
            company.bus.emit(
                K.ROLE_ACTIVITY, f"{name} {activity}", shift_id=sid, role_id=rid
            )

        by_path = {a.path: a for a in brain.state.artifacts.values()}
        for spec in company.scenario.objections:
            target = by_path.get(spec.about or "")
            objection = brain.record_objection(
                severity=spec.severity,
                text=spec.text,
                settled_by=spec.settled_by,
                about=target.id if target else None,
                about_label=target.title if target else spec.about,
                role_id=rid,
                shift_id=sid,
            )
            company.bus.emit(
                K.DECISION_CONTESTED, f"{name} raised a {spec.severity} objection.",
                detail=spec.text, shift_id=sid, role_id=rid, ref=objection.id,
                payload={"severity": spec.severity},
            )
            await self._sleep(2)

        for title, note in company.scenario.contests.items():
            for decision in list(brain.state.decisions.values()):
                if decision.title == title:
                    brain.contest_decision(decision.id, role_id=rid, note=note)
                    company.bus.emit(
                        K.DECISION_CONTESTED, f"{name} contested a decision: {title}",
                        detail=note, shift_id=sid, role_id=rid, ref=decision.id,
                    )

        company.roles[rid]["status"] = RoleStatus.DONE
        company.roles[rid]["activity"] = None
        company.bus.emit(
            K.ROLE_FINISHED,
            f"{name} finished for this shift.",
            shift_id=sid,
            role_id=rid,
        )
        cost = Decimal("0.70")
        brain.record_cost(cost, role_id=rid, shift_id=sid, note="Vera's review")
        return cost

    async def _close(
        self,
        company: StubCompany,
        sid: ShiftId,
        status: ShiftStatus,
        spent: Decimal,
        blocked: bool = False,
    ) -> None:
        brain = company.brain
        scenario = company.scenario
        await self._phase(company, sid, ShiftPhase.CLOSING)
        await self._sleep(4)

        progress = Progress(
            percent=scenario.progress.percent,
            headline=scenario.progress.headline,
            whats_missing=list(scenario.progress.whats_missing),
            judged_at=datetime.now(UTC),
        )
        brain.set_progress(progress)
        company.bus.emit(
            K.PROGRESS_UPDATED, progress.headline, shift_id=sid,
            payload={"percent": progress.percent},
        )
        # What is missing becomes next shift's backlog. This is the loop that
        # makes a company converge instead of wandering.
        for item in progress.whats_missing:
            brain.add_task(title=item, shift_id=sid, priority=2, actor="chief")

        shift = brain.close_shift(
            sid, status=status, summary=scenario.shift_summary, cost=cents(spent)
        )
        self._write_shift_record(company, shift)

        if status is ShiftStatus.COMPLETED and not blocked:
            company.bus.emit(K.SHIFT_COMPLETED, scenario.shift_summary, shift_id=sid)
        elif status is ShiftStatus.BUDGET_EXCEEDED:
            brain.record_metric("halted", True)
            company.bus.emit(
                K.SHIFT_COMPLETED,
                "The shift stopped because the company ran out of budget. "
                "Nothing was lost.",
                detail=scenario.shift_summary, shift_id=sid,
            )
        elif blocked:
            company.bus.emit(
                K.SHIFT_COMPLETED, "The shift is paused until you answer.",
                detail=scenario.shift_summary, shift_id=sid,
            )

        company.clear_activity()

    def _write_shift_record(self, company: StubCompany, shift: Shift) -> None:
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

    def _write_artifact(
        self, company: StubCompany, sid: ShiftId, rid: str, spec: Any
    ) -> None:
        root = company.brain.paths.root
        target = (root / spec.path).resolve()
        if not target.is_relative_to(root.resolve()):
            logger.error(
                "refusing to write artifact outside company root: %s", spec.path
            )
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        if spec.kind is ArtifactKind.SITE:
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.md").write_text(spec.body, encoding="utf-8")
        else:
            target.write_text(spec.body, encoding="utf-8")

        existing = next(
            (a for a in company.brain.state.artifacts.values() if a.path == spec.path),
            None,
        )
        artifact = company.brain.record_artifact(
            path=spec.path,
            title=spec.title,
            summary=spec.summary,
            kind=spec.kind,
            confidence=spec.confidence,
            sources=list(spec.sources),
            role_id=rid,
            shift_id=sid,
            mime=spec.mime,
            preview_url=spec.preview_url,
        )
        company.bus.emit(
            K.ARTIFACT_UPDATED if existing else K.ARTIFACT_CREATED,
            f"{display_name(rid)} finished {spec.title}.",
            detail=spec.summary, shift_id=sid, role_id=rid, ref=artifact.id,
            payload={"confidence": spec.confidence, "sources": len(spec.sources)},
        )


