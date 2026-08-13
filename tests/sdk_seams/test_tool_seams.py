"""The SDK behaviours the real engine stands on.

Each assertion here names a seam. On an SDK upgrade, a red test in this file
tells you exactly which seam moved — instead of a mystery in production.
"""

from __future__ import annotations

import inspect
import os

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")


def test_brain_tool_name_is_derived_correctly() -> None:
    from werkhaus.engines.openhands.brain_tool import WerkhausBrainTool

    assert WerkhausBrainTool.name == "werkhaus_brain"


def test_browser_sub_tool_names_are_what_the_narrator_expects() -> None:
    """The narrator's templates key on these names. If an SDK upgrade renames
    them, activity lines silently degrade to the generic fallback — this test
    makes that loud instead."""
    import openhands.tools.browser_use.definition as browser

    from werkhaus.engines.openhands.narrator import BROWSER_TOOLS

    found = {
        name
        for cls in vars(browser).values()
        if inspect.isclass(cls)
        for name in [getattr(cls, "name", None)]
        if isinstance(name, str) and name.startswith("browser_")
    }
    assert BROWSER_TOOLS <= found, BROWSER_TOOLS - found


def test_browser_navigate_action_has_url() -> None:
    from openhands.tools.browser_use.definition import BrowserNavigateAction

    assert "url" in BrowserNavigateAction.model_fields


def test_observation_from_text_round_trips() -> None:
    from werkhaus.engines.openhands.brain_tool import BrainObservation

    ok = BrainObservation.from_text("fine")
    assert ok.text == "fine" and not ok.is_error
    bad = BrainObservation.from_text("nope", is_error=True)
    assert bad.is_error


def test_conversation_constructor_still_has_our_knobs() -> None:
    from openhands.sdk import LocalConversation

    params = inspect.signature(LocalConversation.__init__).parameters
    for knob in (
        "max_budget_per_run",
        "visualizer",
        "delete_on_close",
        "callbacks",
        "persistence_dir",
        "max_iteration_per_run",
    ):
        assert knob in params, knob


def test_conversation_error_event_import_path() -> None:
    from openhands.sdk.event.conversation_error import ConversationErrorEvent

    assert "code" in ConversationErrorEvent.model_fields


def test_scripted_llm_is_available() -> None:
    from openhands.sdk.testing import TestLLM

    llm = TestLLM.from_messages([])
    assert llm.model == "test-model"


def test_condenser_and_soul_kwarg_construct() -> None:
    from openhands.sdk import Agent
    from openhands.sdk.testing import TestLLM

    from werkhaus.engines.openhands.llm import build_condenser

    llm = TestLLM.from_messages([])
    condenser = build_condenser(llm)
    agent = Agent(
        llm=llm,
        tools=[],
        condenser=condenser,
        system_prompt_kwargs={"soul_content": "You are a test."},
    )
    assert agent.system_prompt_kwargs["soul_content"] == "You are a test."


def test_the_meter_reads_tokens_when_the_price_map_has_no_price(monkeypatch) -> None:
    """Open-weight models are routinely absent from litellm's price table, so
    ``accumulated_cost`` stays 0.0 however long they run. The budget watchdog
    reads this function, so a permanent zero here would mean a company cap that
    never trips. Zero is allowed only when the configured rates are zero.
    """
    from decimal import Decimal

    from openhands.sdk.llm.utils.metrics import Metrics, TokenUsage

    from werkhaus.engines.openhands import shift as shift_mod

    metrics = Metrics(model_name="some/open-weight-model")
    metrics.accumulated_token_usage = TokenUsage(
        model="some/open-weight-model",
        prompt_tokens=874_420,
        completion_tokens=22_926,
    )

    class _Stats:
        def get_combined_metrics(self):
            return metrics

    class _Conversation:
        conversation_stats = _Stats()

    monkeypatch.setenv("WERKHAUS_INPUT_COST_PER_MTOK", "0.20")
    monkeypatch.setenv("WERKHAUS_OUTPUT_COST_PER_MTOK", "0.60")
    priced = shift_mod._run_cost_estimate(_Conversation())
    expected = (874_420 * 0.20 + 22_926 * 0.60) / 1_000_000
    assert abs(float(priced) - expected) < 1e-9
    assert priced > Decimal("0.15")

    # A free tier is the one honest way to bill nothing.
    monkeypatch.setenv("WERKHAUS_INPUT_COST_PER_MTOK", "0")
    monkeypatch.setenv("WERKHAUS_OUTPUT_COST_PER_MTOK", "0")
    assert shift_mod._run_cost_estimate(_Conversation()) == Decimal("0")


def test_a_page_that_failed_to_load_is_not_a_source() -> None:
    """Models invent plausible domains. When one dies on DNS the navigation is
    still *attempted*, and counting attempts would let a made-up citation pass
    the "sourced" check — which is the one thing that check exists to stop.
    """
    import threading

    from openhands.sdk.event import ObservationEvent

    from werkhaus.engines.openhands.brain_tool import BrainObservation, ShiftContext
    from werkhaus.engines.openhands.narrator import Narrator

    class _Bus:
        def emit_threadsafe(self, *a, **k) -> None: ...

    ctx = ShiftContext(
        company_id="co_x",
        shift_id="co_x/0001",
        role_id="researcher",
        shift_number=1,
        brain=None,  # type: ignore[arg-type]
        bus=_Bus(),  # type: ignore[arg-type]
        stopped=threading.Event(),
    )
    narrator = Narrator(ctx)

    def observation(is_error: bool) -> ObservationEvent:
        return ObservationEvent(
            source="environment",
            tool_name="browser_navigate",
            tool_call_id="call_1",
            action_id="act_1",
            observation=BrainObservation.from_text("...", is_error=is_error),
        )

    # A page that loaded counts.
    ctx.pending_url = "https://real.example/pricing"
    narrator._settle_navigation(observation(is_error=False))
    assert "https://real.example/pricing" in ctx.browsed_urls
    assert ctx.pending_url is None

    # A page that did not, does not.
    ctx.pending_url = "https://invented.example/pricing"
    narrator._settle_navigation(observation(is_error=True))
    assert "https://invented.example/pricing" not in ctx.browsed_urls
    assert ctx.pending_url is None


def test_the_workspace_the_file_editor_is_told_about_is_absolute(
    tmp_path, monkeypatch
) -> None:
    """The seam a whole shift once died on.

    The SDK's file editor refuses relative paths, and the only place it tells
    an employee where her workspace *is* is by echoing the conversation's
    working directory into its own tool description. A relative directory there
    reads as ``data/co_x/workspace``; she prepends a slash to satisfy the
    "absolute paths only" rule, and every write lands on ``/data/...``, which
    does not exist. Nothing in the loop can recover from that.
    """
    from openhands.tools.file_editor.definition import FileEditorTool

    from werkhaus.brain.store import BrainStore

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    brain = BrainStore("./data/co_x", "co_x")
    workspace = brain.paths.workspace
    assert workspace.is_absolute()

    # And it survives the round trip the shift actually makes: str() into the
    # conversation, back out as the working directory the tool describes.
    class _Workspace:
        working_dir = str(workspace)

    class _LLM:
        def vision_is_active(self) -> bool:
            return False

    class _Agent:
        llm = _LLM()

    class _State:
        workspace = _Workspace()
        agent = _Agent()

    (tool,) = FileEditorTool.create(_State())  # type: ignore[arg-type]
    assert str(workspace) in tool.description
    assert "directory is: data/" not in tool.description


def test_record_artifact_takes_either_spelling_of_the_same_file(tmp_path) -> None:
    """The file editor demands an absolute path; the brain used to demand a
    relative one. An employee cannot satisfy both, and the one that gave way
    was the document — she wrote it, then could not file it."""
    import threading

    from werkhaus.brain.store import BrainStore
    from werkhaus.engines.openhands.brain_tool import (
        BrainAction,
        BrainExecutor,
        ShiftContext,
    )

    class _Bus:
        def emit_threadsafe(self, *a, **k) -> None: ...

    brain = BrainStore(tmp_path / "co_x", "co_x")
    shift = brain.open_shift(number=1, agenda=["research"])
    ctx = ShiftContext(
        company_id="co_x",
        shift_id=shift.id,
        role_id="researcher",
        shift_number=1,
        brain=brain,
        bus=_Bus(),  # type: ignore[arg-type]
        stopped=threading.Event(),
    )
    (brain.paths.workspace / "market-research.md").write_text("# findings\n")
    executor = BrainExecutor(ctx)

    def record(path: str):
        return executor(
            BrainAction(
                op="record_artifact",
                path=path,
                title="Market research",
                summary="What the competitors charge.",
                confidence="inferred",
            )
        )

    plain = record("market-research.md")
    absolute = record(str(brain.paths.workspace / "market-research.md"))
    assert not plain.is_error and not absolute.is_error

    # Both spellings are the same artifact, not two.
    paths = {a.path for a in brain.state.artifacts.values()}
    assert paths == {"workspace/market-research.md"}

    # Outside the workspace is still refused — including the /tmp an employee
    # falls back to when a write fails, which she could otherwise "file"
    # without the founder ever getting a document.
    outside = record("/tmp/market-research.md")
    assert outside.is_error
    assert str(brain.paths.workspace) in outside.text
    escape = record("../_state/log.jsonl")
    assert escape.is_error


def test_running_out_of_time_reads_differently_from_breaking() -> None:
    """Two failures that look identical to the founder unless we separate them.
    One means run another shift; the other means something is wrong."""
    import threading

    from werkhaus.contract.models import ShiftStatus
    from werkhaus.engines.openhands import shift as shift_mod
    from werkhaus.engines.openhands.brain_tool import ShiftContext

    def ctx(code: str | None) -> ShiftContext:
        out = ShiftContext(
            company_id="co_x",
            shift_id="co_x/0001",
            role_id="researcher",
            shift_number=1,
            brain=None,  # type: ignore[arg-type]
            bus=None,  # type: ignore[arg-type]
            stopped=threading.Event(),
        )
        out.error_code = code
        return out

    out_of_time = shift_mod._failure_reason(
        ShiftStatus.FAILED, ctx("MaxIterationsReached")
    )
    broke = shift_mod._failure_reason(ShiftStatus.FAILED, ctx(None))
    assert out_of_time and "another shift" in out_of_time
    assert broke and "another shift" not in broke

    # A shift that did not fail explains nothing.
    assert shift_mod._failure_reason(ShiftStatus.COMPLETED, ctx(None)) is None


def test_a_shift_that_filed_nothing_buys_a_second_run() -> None:
    """The reserve is for a shift that has produced nothing and is not stopped.

    It used to fire only on turn exhaustion, which was too narrow. Observed in
    production: a model answered with its tool call written out as prose, the
    loop read that as a plain final message and stopped, and the shift closed
    in four minutes having read no pages and filed no documents — while still
    charging for the calls. A premature finish and a turn exhaustion are the
    same thing from the founder's side.

    A halt or a spent budget still buy nothing: those mean the shift is
    genuinely over, and paying a model to summarise for a stopped employee is
    theatre on the founder's money.
    """
    import threading

    from werkhaus.engines.openhands.brain_tool import ShiftContext
    from werkhaus.engines.openhands.shift import _empty_handed

    class _Artifact:
        produced_in_shift = "co_x/0001"

    class _Brain:
        def __init__(self, artifacts) -> None:
            self.state = type("S", (), {"artifacts": artifacts})()

    def ctx(stopped: bool = False) -> ShiftContext:
        out = ShiftContext(
            company_id="co_x",
            shift_id="co_x/0001",
            role_id="researcher",
            shift_number=1,
            brain=None,  # type: ignore[arg-type]
            bus=None,  # type: ignore[arg-type]
            stopped=threading.Event(),
        )
        if stopped:
            out.stopped.set()
        return out

    empty, filed = _Brain({}), _Brain({"a": _Artifact()})
    sid = "co_x/0001"

    # Nothing filed and still running: worth one more attempt, however the
    # first run ended.
    assert _empty_handed(ctx(), empty, sid, False)
    # Already filed: she has nothing left to say.
    assert not _empty_handed(ctx(), filed, sid, False)
    # Budget gone or halted: genuinely over.
    assert not _empty_handed(ctx(), empty, sid, True)
    assert not _empty_handed(ctx(stopped=True), empty, sid, False)


def test_a_shift_that_produced_nothing_is_not_reported_as_finished() -> None:
    """Two shifts were reported "finished" after four minutes each, having read
    no pages and filed no documents, and were charged for. The SDK's execution
    status only describes how the loop ended; it can end perfectly cleanly
    having produced nothing. Judging the shift on its output instead is the
    difference between an honest failure and the theatre the stub engine was
    deleted for.
    """
    import threading

    from werkhaus.contract.models import ShiftStatus
    from werkhaus.engines.openhands.brain_tool import ShiftContext
    from werkhaus.engines.openhands.shift import _classify, _failure_reason

    class _Conversation:
        state = type("S", (), {"execution_status": "finished"})()

    def ctx(unreadable: bool = False) -> ShiftContext:
        out = ShiftContext(
            company_id="co_x",
            shift_id="co_x/0001",
            role_id="researcher",
            shift_number=1,
            brain=None,  # type: ignore[arg-type]
            bus=None,  # type: ignore[arg-type]
            stopped=threading.Event(),
        )
        out.unreadable_reply = unreadable
        return out

    conv = _Conversation()
    # A clean finish that produced something is a completed shift.
    assert _classify(conv, ctx(), False, empty=False) is ShiftStatus.COMPLETED
    # The same clean finish having produced nothing is not.
    assert _classify(conv, ctx(), False, empty=True) is ShiftStatus.FAILED

    # And the founder is told which failure it was.
    generic = _failure_reason(ShiftStatus.FAILED, ctx())
    assert generic and "our failure" in generic
    unreadable = _failure_reason(ShiftStatus.FAILED, ctx(unreadable=True))
    assert unreadable and "different model" in unreadable


def test_the_run_budget_is_cumulative_across_runs_despite_its_name() -> None:
    """``max_budget_per_run`` is checked against the *conversation's* total
    accumulated cost, not the current run's.

    A shift now calls ``run()`` twice — research, then the reserved write-up —
    and the whole safety of that rests on this. If an SDK upgrade ever made the
    budget genuinely per-run, the second call would silently hand every shift a
    fresh cap and double the ceiling the founder agreed to. That would be
    invisible in every other test.
    """
    import inspect

    from openhands.sdk import LocalConversation

    source = inspect.getsource(LocalConversation._budget_exceeded_detail)
    assert "conversation_stats.get_combined_metrics().accumulated_cost" in source


def test_mayas_whole_system_message_is_ours_and_static(tmp_path) -> None:
    """Two things at once, both measured on the shift that prompted the change.

    The SDK's stock prompt spends ~2,658 tokens per call on version control,
    pull requests, code quality and "try curl/wget first" — ~133k tokens across
    one shift, aimed at a market researcher with no shell and no repository.

    And handing rules to AgentContext as a suffix puts them in the SDK's
    *dynamic* context block, outside the cacheable prefix, re-sent in full on
    every call. Inline, they are static — which is the entire reason the digest
    is kept out of here.
    """
    from openhands.sdk.testing import TestLLM

    from werkhaus.brain.store import BrainStore
    from werkhaus.engines.openhands.maya import build_agent

    brain = BrainStore(tmp_path / "co_x", "co_x")
    agent = build_agent(
        TestLLM.from_messages([]), "co_x", brain, 1, browsing=False
    )
    static = agent.static_system_message

    # Hers, in the static tier.
    assert "You are Maya" in static
    assert "web_read" in static and "ONE CALL" in static
    assert str(brain.paths.workspace) in static

    # Not the coding agent's.
    for stock in (
        "<VERSION_CONTROL>", "<PULL_REQUESTS>", "<CODE_QUALITY>",
        "<PROBLEM_SOLVING_WORKFLOW>", "curl/wget", "Co-authored-by",
    ):
        assert stock not in static, stock

    assert len(static) < 6_000, f"{len(static)} chars — the bloat is creeping back"


def test_the_web_tools_live_and_die_with_the_browser(tmp_path) -> None:
    """web_search and web_read are the same capability as the browser — reading
    text strangers wrote — so they must obey the same refusal. An employee
    holding the company's keys gets none of them."""
    from openhands.sdk.testing import TestLLM

    from werkhaus.brain.store import BrainStore
    from werkhaus.engines.openhands.maya import build_agent

    brain = BrainStore(tmp_path / "co_x", "co_x")

    def names(**kwargs) -> set[str]:
        agent = build_agent(
            TestLLM.from_messages([]), "co_x", brain, 1, **kwargs
        )
        return {t.name for t in agent.tools}

    browsing = names(browsing=True)
    assert {"web_search", "web_read", "browser_tool_set"} <= browsing

    # Credentials in the room: no browser, and no fetching either.
    from openhands.sdk.mcp import MCPServer

    holding = names(
        browsing=False, mcp={"stripe": MCPServer(url="https://mcp.example/sse")}
    )
    assert not ({"web_search", "web_read", "browser_tool_set"} & holding)
    assert {"file_editor", "werkhaus_brain"} <= holding


def test_the_browser_is_separable_from_reading_the_web(tmp_path) -> None:
    """Measured on a real shift: with chromium in the tool list the model made
    46 browser calls and *zero* web_read calls, for roughly ten times the token
    bill. browser_navigate is the most familiar web action there is and a model
    reaches for it out of habit however the prompt is worded.

    So the heavy browser is now its own switch. Turning it off must leave an
    employee able to research — it is a fallback for script-rendered pages, not
    the thing that grants her the web.
    """
    from openhands.sdk.testing import TestLLM

    from werkhaus.brain.store import BrainStore
    from werkhaus.engines.openhands.maya import build_agent

    brain = BrainStore(tmp_path / "co_x", "co_x")

    def names(**kwargs) -> set[str]:
        agent = build_agent(TestLLM.from_messages([]), "co_x", brain, 1, **kwargs)
        return {t.name for t in agent.tools}

    with_browser = names(browsing=True, chromium=True)
    without = names(browsing=True, chromium=False)

    assert "browser_tool_set" in with_browser
    assert "browser_tool_set" not in without
    # The part that matters: she can still research.
    assert {"web_search", "web_read"} <= without


def test_no_browser_no_longer_means_no_research(monkeypatch, tmp_path) -> None:
    """WERKHAUS_NO_BROWSER used to take the whole web away, because the browser
    *was* the web. It isn't any more, and the flag now means what people always
    read it as: don't run a chromium."""
    from werkhaus.engines.openhands.engine import OpenHandsEngine

    monkeypatch.setenv("WERKHAUS_NO_BROWSER", "1")
    engine = OpenHandsEngine(root=tmp_path)
    assert engine.chromium is False
    assert engine.browsing is True

    monkeypatch.delenv("WERKHAUS_NO_BROWSER")
    assert OpenHandsEngine(root=tmp_path).chromium is True
