"""One real shift, one real employee.

The loop keeps the five-phase shape where it can, and is honest where
it can't: there is no review phase because Vera doesn't exist yet, and progress
is a stated heuristic rather than a judged score. Both arrive in M4; pretending
otherwise here would teach the UI to trust theatre.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from decimal import Decimal

from openhands.sdk import LocalConversation

from werkhaus.brain.digest import render_digest
from werkhaus.brain.store import BrainStore
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import (
    Progress,
    RoleStatus,
    ShiftId,
    ShiftPhase,
    ShiftStatus,
)
from werkhaus.engines.common import cents
from werkhaus.engines.openhands.brain_tool import (
    ShiftContext,
    register_shift,
    unregister_shift,
)
from werkhaus.engines.openhands.llm import build_llm, estimate_cost
from werkhaus.engines.openhands.maya import build_agent
from werkhaus.engines.openhands.mcp import build_for_shift
from werkhaus.engines.openhands.narrator import Narrator
from werkhaus.engines.openhands.runtime import OpenHandsCompany

logger = logging.getLogger(__name__)

ROLE_ID = "researcher"
ROLE_CAP = Decimal("1.50")
MAX_ITERATIONS = 80
RESEARCH_ITERATIONS = 64
WRAP_UP_ITERATIONS = MAX_ITERATIONS - RESEARCH_ITERATIONS
"""The turn budget, split. An employee cannot see her own turn counter, so
"stop early enough to write it up" is not something she can be asked to do —
it has to be done to her. The reserve is only ever spent if the research half
ran out with nothing filed, so a shift that finishes normally costs no more
than it did before."""

WATCHDOG_SECONDS = 5.0

WRAP_UP = (
    "Stop researching — you are out of time for this shift, and you have not "
    "filed anything yet.\n\n"
    "Write up what you already have, now, in one pass: write the document, "
    "record it, and finish. Label every claim honestly — inferred and "
    "assumption are fine, and a short document with three sourced facts is "
    "worth far more to the founder than another page of reading. Anything you "
    "could not establish goes down as an open question with add_task, not as "
    "a guess."
)

# The browser executor is one shared chromium for the whole process; two
# companies browsing at once would interleave tabs. One real shift at a time
# in M3 — revisited in M4 with per-company isolation.
_WORK_SLOT = asyncio.Semaphore(1)

DEFAULT_AGENDA = [
    "Find out who else is doing this and what they charge",
    "Write a market overview the team can act on",
]

MISSING_AFTER_RESEARCH = [
    "A positioning and a price",
    "Words and a brand voice",
    "A landing page people can visit",
    "A one-page money model",
]


async def run_shift(engine, company: OpenHandsCompany, sid: ShiftId) -> None:
    brain, bus = company.brain, company.bus
    shift = brain.state.shifts[sid]
    number = shift.number
    ctx: ShiftContext | None = None
    conversation: LocalConversation | None = None
    budget_hit = False
    # The watchdog reads the meter every few seconds anyway; the closing phase
    # reuses that reading instead of racing the close running on another thread.
    run_cost = Decimal("0")

    try:
        bus.emit(K.SHIFT_STARTED, f"Shift {number} has started.", shift_id=sid)
        # ---------------------------------------------------------- planning
        _phase(company, sid, ShiftPhase.PLANNING, "Maya is planning her research.")
        for item in shift.agenda:
            brain.add_task(title=item, shift_id=sid, priority=2, actor="chief")
            bus.emit(K.TASK_ADDED, f"On the agenda: {item}", shift_id=sid)
        brain.update_shift(sid, roles_active=[ROLE_ID])
        company.roles[ROLE_ID]["status"] = RoleStatus.WORKING
        bus.emit(K.ROLE_STARTED, "Maya started work.", shift_id=sid, role_id=ROLE_ID)

        # ----------------------------------------------------------- working
        _phase(company, sid, ShiftPhase.WORKING, "The team is working.")
        ctx = ShiftContext(
            company_id=company.id,
            shift_id=sid,
            role_id=ROLE_ID,
            shift_number=number,
            brain=brain,
            bus=bus,
        )
        ctx.set_activity = lambda text: company.roles[ROLE_ID].__setitem__(
            "activity", text
        )
        register_shift(ctx)
        company.shift_ctx = ctx

        if engine.llm_factory is not None:
            llm = engine.llm_factory(ROLE_ID)
        else:
            api_key, model_name, base_url = engine.byok(company)
            llm = build_llm(
                ROLE_ID, api_key=api_key, model=model_name, base_url=base_url
            )
        # What the founder connected, minus whatever isn't answering and
        # whatever doesn't fit in one employee's head.
        mcp = build_for_shift(engine, company)
        for line in mcp.said():
            bus.emit(K.ROLE_SAID, f"Ada: {line}", shift_id=sid)
        agent = build_agent(
            llm,
            company.id,
            brain,
            number,
            browsing=engine.browsing and mcp.browsing_allowed,
            chromium=getattr(engine, "chromium", True),
            mcp=mcp.servers or None,
            tool_filter=mcp.filter_regex if mcp.servers else None,
        )
        run_cap = min(ROLE_CAP, company.per_shift_cap, company.cap - company.spent)
        conversation = LocalConversation(
            agent=agent,
            workspace=str(brain.paths.workspace),
            persistence_dir=str(brain.paths.conversations / f"{number:04d}"),
            callbacks=[Narrator(ctx)],
            # The research half of MAX_ITERATIONS. The rest is held in reserve
            # and only ever spent on the write-up below.
            max_iteration_per_run=RESEARCH_ITERATIONS,
            visualizer=None,
            max_budget_per_run=float(run_cap),
            delete_on_close=False,
        )
        company.conversation = conversation

        async with _WORK_SLOT:
            watch = _Watchdog(company, ctx, conversation)
            try:
                # The turn budget is split, not spent in one go. Researching
                # until the very last turn is how a shift ends with a head full
                # of findings and an empty workspace — which is the one outcome
                # the founder cannot use.
                conversation.send_message(_kickoff(shift.agenda, brain, number))
                budget_hit = await watch.run()

                if _empty_handed(ctx, brain, sid, budget_hit):
                    # Nothing was filed and the shift is not stopped: buy one
                    # more attempt with the turns held back for exactly this.
                    logger.info("shift %s has filed nothing; wrapping up", sid)
                    ctx.error_code = None
                    conversation.max_iteration_per_run = WRAP_UP_ITERATIONS
                    conversation.send_message(WRAP_UP)
                    budget_hit = await watch.run()
            finally:
                run_cost = watch.cost
                watch.close()

        # ----------------------------------------------------------- closing
        status = _classify(
            conversation, ctx, budget_hit, empty=filed_nothing(brain, sid)
        )
        _phase(company, sid, ShiftPhase.CLOSING, "Writing up the shift.")

        cost = cents(run_cost)
        if cost > 0:
            brain.record_cost(
                cost, role_id=ROLE_ID, shift_id=sid,
                note="Maya's research this shift",
            )
        bus.emit(
            K.BUDGET_SPENT, "", shift_id=sid, role_id=ROLE_ID,
            payload={"spent": str(cents(company.spent)), "cap": str(company.cap)},
        )

        produced = [
            a for a in brain.state.artifacts.values() if a.produced_in_shift == sid
        ]
        finished = [
            t for t in ctx.claimed_task_ids
            if brain.state.tasks[t].status.value == "done"
        ]
        if status is ShiftStatus.COMPLETED:
            company.roles[ROLE_ID]["status"] = RoleStatus.DONE
            bus.emit(
                K.ROLE_FINISHED, "Maya finished for this shift.",
                shift_id=sid, role_id=ROLE_ID,
            )
        else:
            company.roles[ROLE_ID]["status"] = RoleStatus.FAILED
            bus.emit(
                K.ROLE_FAILED,
                "Maya hit a problem and stopped. "
                "The team will pick this up next shift.",
                shift_id=sid, role_id=ROLE_ID,
            )

        progress = Progress(
            percent=min(15, 5 * len(brain.state.artifacts)),
            headline="Market research exists; nothing else does yet."
            if brain.state.artifacts
            else "Nothing usable came out of this shift.",
            whats_missing=list(MISSING_AFTER_RESEARCH),
        )
        brain.set_progress(progress)
        bus.emit(
            K.PROGRESS_UPDATED, progress.headline, shift_id=sid,
            payload={"percent": progress.percent},
        )

        summary = (
            f"Maya read {len(ctx.browsed_urls)} "
            f"{'page' if len(ctx.browsed_urls) == 1 else 'pages'} and produced "
            f"{len(produced)} {'document' if len(produced) == 1 else 'documents'}; "
            f"{len(finished)} of {len(ctx.claimed_task_ids)} claimed tasks finished."
        )
        closed = brain.close_shift(
            sid,
            status=status,
            summary=summary,
            failure_reason=_failure_reason(status, ctx),
            cost=cost,
        )
        engine._write_shift_record(company, closed)

        if status is ShiftStatus.COMPLETED:
            bus.emit(K.SHIFT_COMPLETED, summary, shift_id=sid)
            engine._schedule_auto_chain(company)
        elif status is ShiftStatus.BUDGET_EXCEEDED:
            if company.spent >= company.cap:
                brain.record_metric("halted", True)
            bus.emit(
                K.SHIFT_COMPLETED,
                "The shift stopped because it ran out of budget. "
                "Nothing was lost.",
                detail=summary, shift_id=sid,
            )
        else:
            bus.emit(
                K.SHIFT_FAILED,
                "The shift stopped early. Nothing that was already done was lost.",
                detail=summary, shift_id=sid,
            )
        company.clear_activity()

    except asyncio.CancelledError:
        # Halt or stop: _cancel already closed the shift via
        # abort_running_shifts and set the discard guard. Only close here if
        # the shift is somehow still open.
        current = brain.state.shifts[sid]
        if current.status is ShiftStatus.RUNNING:
            brain.close_shift(
                sid, status=ShiftStatus.ABORTED,
                failure_reason="You stopped this shift.",
                cost=cents(max(run_cost, _run_cost_estimate(conversation))),
            )
        company.clear_activity()
        raise
    except Exception as exc:
        logger.exception("real shift %s blew up", sid)
        if brain.state.shifts[sid].status is ShiftStatus.RUNNING:
            brain.close_shift(
                sid, status=ShiftStatus.FAILED,
                failure_reason=_exception_reason(exc),
                cost=cents(max(run_cost, _run_cost_estimate(conversation))),
            )
        company.clear_activity()
        bus.emit(
            K.SHIFT_FAILED,
            "The shift stopped early. Nothing that was already done was lost.",
            shift_id=sid,
        )
    finally:
        unregister_shift(company.id)
        company.shift_ctx = None
        company.conversation = None


# ------------------------------------------------------------------- helpers
class _Watchdog:
    """Drives ``conversation.run()`` on a worker thread and reads the meter on
    the clock while it works.

    One instance spans every run of a shift, because the cost meter and the
    "spent" event stream are per-shift, not per-run: a second run must keep
    counting from where the first stopped, not start again at zero.
    """

    def __init__(
        self,
        company: OpenHandsCompany,
        ctx: ShiftContext,
        conversation: LocalConversation,
    ) -> None:
        self.company = company
        self.ctx = ctx
        self.conversation = conversation
        self.cost = Decimal("0")
        self._last_shown = ""
        self._run: asyncio.Future | None = None

    async def run(self) -> bool:
        """Run to completion. Returns True if the company cap stopped it."""
        company, ctx, conversation = self.company, self.ctx, self.conversation
        sid = ctx.shift_id
        self._run = asyncio.ensure_future(asyncio.to_thread(conversation.run))
        while True:
            done, _ = await asyncio.wait({self._run}, timeout=WATCHDOG_SECONDS)
            # The estimate, not the raw accumulated cost: open-weight models
            # are routinely missing from the price map, and a watchdog reading
            # a permanent 0.0 guards nothing.
            self.cost = _run_cost_estimate(conversation)
            spent_now = company.spent + self.cost
            shown = str(cents(spent_now))
            # One event per actual change. A 30-minute shift used to emit ~200
            # identical "spent 0.00" events.
            if shown != self._last_shown:
                self._last_shown = shown
                company.bus.emit(
                    K.BUDGET_SPENT, "", shift_id=sid, role_id=ROLE_ID,
                    payload={"spent": shown, "cap": str(company.cap)},
                )
            if done:
                await self._run  # surface ConversationRunError, if any
                return False
            # Layer 4: the live watchdog. The per-run cap is checked between
            # steps; the company cap is checked here, on the clock, and stops
            # the whole shift.
            if spent_now >= company.cap:
                ctx.stopped.set()
                conversation.pause()
                company.bus.emit(
                    K.BUDGET_EXCEEDED,
                    "The company has spent its whole budget, "
                    "so everyone stopped.",
                    shift_id=sid, role_id=ROLE_ID,
                )
                await self._run
                return True

    def close(self) -> None:
        """Release the browser, whether or not a run ever got off the ground."""
        if self._run is not None:
            _close_when_done(self._run, self.conversation)
        else:
            threading.Thread(
                target=_safe_close, args=(self.conversation,), daemon=True
            ).start()


def filed_nothing(brain: BrainStore, sid: ShiftId) -> bool:
    """Did this shift end with nothing the founder can hold?"""
    return not any(
        a.produced_in_shift == sid for a in brain.state.artifacts.values()
    )


def _empty_handed(
    ctx: ShiftContext, brain: BrainStore, sid: ShiftId, budget_hit: bool
) -> bool:
    """Should the reserve be spent trying to get a document out of this shift?

    Originally this only fired on turn exhaustion. That was too narrow: a model
    can also *finish* having done nothing — it emits something the SDK cannot
    read as a tool call, the loop sees a plain final message and stops, and the
    shift closes in four minutes having filed nothing. Turn exhaustion and a
    premature finish are the same problem from the founder's side, so both
    earn the second run.

    A halt or a spent budget still do not. Those mean the shift is genuinely
    over, and paying a model to summarise for a stopped employee is theatre.
    """
    if budget_hit or ctx.stopped.is_set():
        return False
    return filed_nothing(brain, sid)


def _phase(
    company: OpenHandsCompany, sid: ShiftId, phase: ShiftPhase, text: str
) -> None:
    company.brain.update_shift(sid, phase=phase)
    company.bus.emit(K.PHASE_CHANGED, text, shift_id=sid, payload={"phase": phase})


def _kickoff(agenda: list[str], brain, shift_number: int) -> str:
    """The opening message: what to do, and what the company already knows.

    The digest lives here rather than in the system prompt because it changes
    every shift, and anything that changes cannot be part of a cached prefix.
    """
    digest = render_digest(
        brain,
        role_id=ROLE_ID,
        role_name="Maya",
        shift_number=shift_number,
        # Today's agenda is the query. What the company should remember is
        # whatever it has repeatedly worked on alongside this.
        focus=" ".join(agenda),
    )
    lines = "\n".join(f"- {item}" for item in agenda)
    return (
        "Your shift has started. On the agenda:\n"
        f"{lines}\n\n"
        f"{digest}\n\n"
        "Claim what you will work on, and get going."
    )


def _run_cost_estimate(conversation: LocalConversation | None) -> Decimal:
    """The real accumulated cost, or a token-based estimate when the model is
    missing from the price map. Zero only when the configured rates are zero —
    a free tier — never merely because litellm has no price for the model.
    """
    if conversation is None:
        return Decimal("0")
    try:
        metrics = conversation.conversation_stats.get_combined_metrics()
        usage = metrics.accumulated_token_usage
        return estimate_cost(
            metrics.accumulated_cost,
            int(getattr(usage, "prompt_tokens", 0) or 0),
            int(getattr(usage, "completion_tokens", 0) or 0),
        )
    except Exception:
        # Never fail a shift over the meter — but a zero that came from a
        # broken read must not look like a zero that came from a free tier.
        logger.warning("could not read the cost meter", exc_info=True)
        return Decimal("0")


def _classify(
    conversation: LocalConversation,
    ctx: ShiftContext,
    budget_hit: bool,
    empty: bool = False,
) -> ShiftStatus:
    """What actually happened, judged on the output rather than the loop.

    ``empty`` is the important one. The SDK's execution status only says how
    the loop ended, and a loop can end perfectly cleanly having produced
    nothing — which is how two shifts came to be reported as "finished" after
    four minutes each, having read no pages and filed no documents, while
    still charging for the model calls. From the founder's side that is not a
    completed shift, and calling it one is the kind of theatre the stub engine
    was deleted for.
    """
    if budget_hit or ctx.error_code == "MaxBudgetReached":
        return ShiftStatus.BUDGET_EXCEEDED
    status = str(getattr(conversation.state, "execution_status", "")).lower()
    if ctx.error_code == "MaxIterationsReached":
        return ShiftStatus.FAILED
    if "stuck" in status or "error" in status:
        return ShiftStatus.FAILED
    if empty:
        return ShiftStatus.FAILED
    return ShiftStatus.COMPLETED


def _failure_reason(status: ShiftStatus, ctx: ShiftContext | None) -> str | None:
    """Why it stopped, in words a founder can act on.

    "Couldn't finish" tells them nothing: it reads the same whether the model
    broke or the work was simply bigger than one shift. Running out of time is
    the common case and the one with an obvious next move — run another shift.
    """
    if status is not ShiftStatus.FAILED:
        return None
    if ctx is not None and ctx.unreadable_reply:
        # The model answered, but in a shape the harness cannot act on. There
        # is nothing the founder can do about that and no point implying there
        # is, so it says what happened and points at the one setting that
        # changes it.
        return (
            "The service the team thinks with kept answering in a form we "
            "could not act on, so nothing got done. Try a different model in "
            "settings; nothing was lost."
        )
    if ctx is not None and ctx.error_code == "MaxIterationsReached":
        return (
            "There was more to do than fits in one shift. The work so far is "
            "saved — another shift picks up where this one stopped."
        )
    return (
        "This shift ended without producing anything. That is our failure, "
        "not yours, and nothing that was already done was lost."
    )


def _exception_reason(exc: BaseException) -> str:
    """A person can act on "the provider is at its limit"; they cannot act on
    a wrapped stack of provider exceptions. Walk the chain, name the two
    failure families that actually happen, fall back to the honest generic."""
    chain: list[BaseException] = []
    seen = exc
    while seen is not None and seen not in chain:
        chain.append(seen)
        seen = seen.__cause__ or seen.__context__
    text = " ".join(f"{type(e).__name__}: {e}" for e in chain).lower()
    if "ratelimit" in text or "resourceexhausted" in text or "429" in text:
        return (
            "The service the team thinks with is over its limit for now. "
            "Nothing was lost — try again later, or raise the limit with "
            "your provider."
        )
    if "authentication" in text or "401" in text or "invalid api key" in text:
        return (
            "The team's key was refused by its provider. Check the key and "
            "start the shift again."
        )
    return "Something went wrong and the shift stopped."


def _close_when_done(run: asyncio.Future, conversation: LocalConversation) -> None:
    """Release the browser once the worker thread actually drains — off the
    event loop, because closing chromium can take a moment."""

    def _close(_fut) -> None:
        threading.Thread(
            target=_safe_close, args=(conversation,), daemon=True
        ).start()

    if run.done():
        _close(run)
    else:
        run.add_done_callback(_close)


def _safe_close(conversation: LocalConversation) -> None:
    try:
        conversation.close()
    except Exception:
        logger.debug("conversation close failed", exc_info=True)
