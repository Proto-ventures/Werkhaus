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
from werkhaus.engines.openhands.narrator import Narrator
from werkhaus.engines.openhands.runtime import OpenHandsCompany

logger = logging.getLogger(__name__)

ROLE_ID = "researcher"
ROLE_CAP = Decimal("1.50")
MAX_ITERATIONS = 80
WATCHDOG_SECONDS = 5.0

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
    last_shown = ""

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
        agent = build_agent(
            llm, company.id, brain, number, browsing=engine.browsing
        )
        run_cap = min(ROLE_CAP, company.per_shift_cap, company.cap - company.spent)
        conversation = LocalConversation(
            agent=agent,
            workspace=str(brain.paths.workspace),
            persistence_dir=str(brain.paths.conversations / f"{number:04d}"),
            callbacks=[Narrator(ctx)],
            max_iteration_per_run=MAX_ITERATIONS,
            visualizer=None,
            max_budget_per_run=float(run_cap),
            delete_on_close=False,
        )
        company.conversation = conversation

        async with _WORK_SLOT:
            conversation.send_message(_kickoff(shift.agenda))
            run = asyncio.ensure_future(asyncio.to_thread(conversation.run))
            try:
                while True:
                    done, _ = await asyncio.wait({run}, timeout=WATCHDOG_SECONDS)
                    # The estimate, not the raw accumulated cost: open-weight
                    # models are routinely missing from the price map, and a
                    # watchdog reading a permanent 0.0 guards nothing.
                    run_cost = _run_cost_estimate(conversation)
                    spent_now = company.spent + run_cost
                    shown = str(cents(spent_now))
                    # One event per actual change. A 30-minute shift used to
                    # emit ~200 identical "spent 0.00" events.
                    if shown != last_shown:
                        last_shown = shown
                        bus.emit(
                            K.BUDGET_SPENT, "", shift_id=sid, role_id=ROLE_ID,
                            payload={"spent": shown, "cap": str(company.cap)},
                        )
                    if done:
                        await run  # surface ConversationRunError, if any
                        break
                    # Layer 4: the live watchdog. The per-run cap is checked
                    # between steps; the company cap is checked here, on the
                    # clock, and stops the whole shift.
                    if spent_now >= company.cap:
                        budget_hit = True
                        ctx.stopped.set()
                        conversation.pause()
                        bus.emit(
                            K.BUDGET_EXCEEDED,
                            "The company has spent its whole budget, "
                            "so everyone stopped.",
                            shift_id=sid, role_id=ROLE_ID,
                        )
                        await run
                        break
            finally:
                _close_when_done(run, conversation)

        # ----------------------------------------------------------- closing
        status = _classify(conversation, ctx, budget_hit)
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
            failure_reason=_failure_reason(status),
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
def _phase(
    company: OpenHandsCompany, sid: ShiftId, phase: ShiftPhase, text: str
) -> None:
    company.brain.update_shift(sid, phase=phase)
    company.bus.emit(K.PHASE_CHANGED, text, shift_id=sid, payload={"phase": phase})


def _kickoff(agenda: list[str]) -> str:
    lines = "\n".join(f"- {item}" for item in agenda)
    return (
        "Your shift has started. On the agenda:\n"
        f"{lines}\n\n"
        "Start by reading the company digest (werkhaus_brain, op=read_digest), "
        "claim what you will work on, and get going."
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
) -> ShiftStatus:
    if budget_hit or ctx.error_code == "MaxBudgetReached":
        return ShiftStatus.BUDGET_EXCEEDED
    status = str(getattr(conversation.state, "execution_status", "")).lower()
    if ctx.error_code == "MaxIterationsReached":
        return ShiftStatus.FAILED
    if "stuck" in status or "error" in status:
        return ShiftStatus.FAILED
    return ShiftStatus.COMPLETED


def _failure_reason(status: ShiftStatus) -> str | None:
    if status is ShiftStatus.FAILED:
        return "Maya couldn't finish this one. The work so far is saved."
    return None


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
