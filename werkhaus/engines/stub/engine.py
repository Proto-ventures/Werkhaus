"""The stub engine.

Fakes the *content* of a shift and nothing else. It runs the same five phases the
real ShiftRunner runs, with the same concurrency cap, the same budget layers, the
same halt semantics — and writes through the same :class:`BrainStore`, via the
same :class:`BaseEngine`. So every stub shift exercises the durable layer the
real engine inherits, and the only thing swapped is where the words come from.

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
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from werkhaus.brain.store import BrainStore
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import (
    ArtifactKind,
    Charter,
    Company,
    CompanyId,
    Progress,
    RoleStatus,
    Shift,
    ShiftId,
    ShiftPhase,
    ShiftStatus,
)
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.common import BaseEngine, cents
from werkhaus.engines.roster import display_name
from werkhaus.engines.stub.scenario import (
    ScenarioRoleWork,
    list_scenarios,
    load_scenario,
)
from werkhaus.engines.stub.state import StubCompany

logger = logging.getLogger(__name__)

MAX_CONCURRENT_ROLES = 3
"""Not for correctness — for LLM rate limits, and because seven simultaneous
activity streams is an unreadable dashboard."""

_PHASE_TEXT: dict[ShiftPhase, str] = {
    ShiftPhase.PLANNING: "Ada is working out what the team should do this shift.",
    ShiftPhase.WORKING: "The team is working.",
    ShiftPhase.REVIEW: "Vera is reviewing what everyone produced.",
    ShiftPhase.INTEGRATING: "Filing everything away.",
    ShiftPhase.CLOSING: "Writing up the shift.",
}


class StubEngine(BaseEngine):
    def __init__(
        self,
        root: str | Path = "./data",
        seed: int = 42,
        scenario: str = "happy",
        speed: float = 1.0,
    ) -> None:
        super().__init__(root)
        self.seed = seed
        self.default_scenario = scenario
        self.speed = max(0.01, speed)

    def _make_runtime(self, brain: BrainStore, bus: CompanyBus) -> StubCompany:
        name = brain.state.metrics.get("scenario", self.default_scenario)
        return StubCompany(brain, load_scenario(name), bus)

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

        charter = Charter(
            idea=idea or scenario.charter.idea,
            one_liner=scenario.charter.one_liner,
            audience=scenario.charter.audience,
            success_looks_like=scenario.charter.success_looks_like,
            constraints=list(scenario.charter.constraints),
            tone=scenario.charter.tone,
        )
        company = self._new_company(
            charter=charter,
            name=name or scenario.company_name,
            budget_cap=Decimal(str(scenario.budget_cap)),
            per_shift_cap=Decimal(str(scenario.per_shift_cap)),
            extra_metrics={"scenario": scenario.name},
        )
        return company.company()

    # ------------------------------------------------------------------ shifts
    async def start_shift(self, cid: CompanyId, focus: str | None = None) -> Shift:
        company = self._get(cid)
        assert isinstance(company, StubCompany)
        self._ensure_can_start(company)

        shift = company.brain.open_shift(
            number=len(company.brain.state.shifts) + 1,
            agenda=[focus] if focus else list(company.scenario.agenda),
        )
        company.task_handle = asyncio.create_task(self._run_shift(company, shift.id))
        return shift

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
            if brain.state.shifts[sid].status is ShiftStatus.RUNNING:
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

    def _seed_site(self, company: StubCompany) -> None:
        """Write the landing page Kit 'built' as real files.

        This is the one place the stub produces something that can be judged
        directly: the Website tab iframes it, the Code tab lists these files,
        and both are telling the truth.
        """
        state = company.brain.state
        charter = state.charter
        name = state.name
        one_liner = charter.one_liner if charter else ""
        audience = charter.audience if charter else ""

        site = company.brain.paths.workspace / "site"
        site.mkdir(parents=True, exist_ok=True)

        (site / "index.html").write_text(
            "<!doctype html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="utf-8">\n'
            '  <meta name="viewport" content="width=device-width, '
            'initial-scale=1">\n'
            f"  <title>{name}</title>\n"
            '  <link rel="stylesheet" href="styles.css">\n'
            "</head>\n"
            "<body>\n"
            "  <header>\n"
            f"    <span class=\"brand\">{name}</span>\n"
            "  </header>\n"
            "  <main>\n"
            f"    <h1>{one_liner}</h1>\n"
            f"    <p class=\"for\">Made for {audience.lower().rstrip('.')}"
            ".</p>\n"
            '    <form id="waitlist">\n'
            '      <label for="email">Be first in line</label>\n'
            '      <div class="row">\n'
            '        <input id="email" type="email" required '
            'placeholder="you@example.com">\n'
            '        <button type="submit">Join the waitlist</button>\n'
            "      </div>\n"
            '      <p class="note" id="confirm" hidden>'
            "You're on the list. We'll write when it's ready.</p>\n"
            "    </form>\n"
            "  </main>\n"
            "  <footer>\n"
            f"    <span>&copy; {datetime.now(UTC).year} {name}</span>\n"
            "  </footer>\n"
            '  <script src="script.js"></script>\n'
            "</body>\n"
            "</html>\n",
            encoding="utf-8",
        )
        (site / "styles.css").write_text(
            "*{box-sizing:border-box;margin:0}\n"
            ":root{--paper:#faf6ee;--ink:#26221c;--soft:#6b6355;"
            "--accent:#8a5a2b}\n"
            "body{font-family:Georgia,'Times New Roman',serif;"
            "background:var(--paper);color:var(--ink);min-height:100vh;"
            "display:flex;flex-direction:column}\n"
            "header,footer{padding:1.25rem 2rem;font-size:.9rem;"
            "letter-spacing:.06em}\n"
            ".brand{text-transform:uppercase;font-weight:700}\n"
            "main{flex:1;max-width:38rem;margin:0 auto;padding:14vh 2rem 4rem}\n"
            "h1{font-size:clamp(1.9rem,4.5vw,3rem);line-height:1.15;"
            "font-weight:400}\n"
            ".for{margin-top:1.25rem;color:var(--soft);font-size:1.05rem;"
            "line-height:1.5}\n"
            "form{margin-top:3rem}\n"
            "label{display:block;font-size:.8rem;text-transform:uppercase;"
            "letter-spacing:.12em;color:var(--soft)}\n"
            ".row{display:flex;gap:.5rem;margin-top:.75rem;flex-wrap:wrap}\n"
            "input{flex:1;min-width:14rem;padding:.8rem 1rem;font:inherit;"
            "border:1px solid var(--ink);background:#fff}\n"
            "button{padding:.8rem 1.4rem;font:inherit;cursor:pointer;"
            "border:1px solid var(--ink);background:var(--ink);color:var(--paper)}\n"
            "button:hover{background:var(--accent);border-color:var(--accent)}\n"
            ".note{margin-top:1rem;color:var(--accent)}\n"
            "footer{color:var(--soft)}\n",
            encoding="utf-8",
        )
        (site / "script.js").write_text(
            "document.getElementById('waitlist').addEventListener('submit',"
            "function(e){\n"
            "  e.preventDefault();\n"
            "  document.getElementById('confirm').hidden = false;\n"
            "  document.getElementById('email').value = '';\n"
            "});\n",
            encoding="utf-8",
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
        preview_url = spec.preview_url
        if spec.kind is ArtifactKind.SITE:
            target.mkdir(parents=True, exist_ok=True)
            (target / "index.md").write_text(spec.body, encoding="utf-8")
            # The site is the one artifact that either works or doesn't, so the
            # stub builds a real one: actual files in workspace/site/, served at
            # a real URL the Website tab can load.
            self._seed_site(company)
            preview_url = f"/api/v1/companies/{company.id}/site/"
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
            preview_url=preview_url,
        )
        company.bus.emit(
            K.ARTIFACT_UPDATED if existing else K.ARTIFACT_CREATED,
            f"{display_name(rid)} finished {spec.title}.",
            detail=spec.summary, shift_id=sid, role_id=rid, ref=artifact.id,
            payload={"confidence": spec.confidence, "sources": len(spec.sources)},
        )
