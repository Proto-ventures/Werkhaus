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
