"""The masking condenser, exercised for real.

This file exists because the first version shipped without it and failed on a
live shift: `Condensation` requires an `llm_response_id`, which every other
condenser inherits from the model call that produced it — and this one makes no
call at all. A unit test that actually constructs the condensation would have
caught it in a second instead of a shift.
"""

from __future__ import annotations

import os

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")


def _view(n_obs: int = 30):
    """A history with plenty of browser output and a few brain calls."""
    from openhands.sdk.context.view import View
    from openhands.sdk.event import ActionEvent, ObservationEvent

    from werkhaus.engines.openhands.brain_tool import BrainObservation

    events = []
    for i in range(n_obs):
        tool = "werkhaus_brain" if i % 7 == 0 else "browser_get_content"
        events.append(
            ObservationEvent(
                source="environment",
                tool_name=tool,
                tool_call_id=f"call_{i}",
                action_id=f"act_{i}",
                observation=BrainObservation.from_text("x" * 400),
            )
        )
    assert ActionEvent  # imported for shape parity with a real view
    return View(events=events)


def test_it_forgets_old_observations_and_keeps_recent_ones() -> None:
    from werkhaus.engines.openhands.condenser import ObservationMaskingCondenser

    condenser = ObservationMaskingCondenser()
    view = _view(30)
    condensation = condenser.get_condensation(view)

    forgotten = condensation.forgotten_event_ids
    ids = [e.id for e in view.events]
    assert forgotten, "nothing was masked"
    # The most recent ones survive.
    for keep in ids[-condenser.keep_last :]:
        assert keep not in forgotten
    # So does the opening exchange.
    for keep in ids[: condenser.keep_first]:
        assert keep not in forgotten


def test_it_never_masks_the_company_brain() -> None:
    """Those replies are the shift's own state — what was claimed, what was
    filed. Forgetting them makes an employee redo work it already did."""
    from werkhaus.engines.openhands.condenser import ObservationMaskingCondenser

    view = _view(30)
    forgotten = ObservationMaskingCondenser().get_condensation(view).forgotten_event_ids
    brain_ids = {
        e.id for e in view.events if getattr(e, "tool_name", "") == "werkhaus_brain"
    }
    assert not (brain_ids & forgotten)


def test_it_costs_nothing_and_still_constructs() -> None:
    """The regression: no model call means no response id to inherit."""
    from werkhaus.engines.openhands.condenser import (
        NO_LLM_RESPONSE,
        ObservationMaskingCondenser,
    )

    condensation = ObservationMaskingCondenser().get_condensation(_view(30))
    assert condensation.summary is None, "summarising is the thing we removed"
    assert condensation.llm_response_id == NO_LLM_RESPONSE


def test_a_short_shift_is_left_alone() -> None:
    from werkhaus.engines.openhands.condenser import ObservationMaskingCondenser

    condenser = ObservationMaskingCondenser()
    assert condenser.condensation_requirement(_view(5)) is None


def test_a_long_shift_triggers() -> None:
    from werkhaus.engines.openhands.condenser import ObservationMaskingCondenser

    condenser = ObservationMaskingCondenser()
    assert condenser.condensation_requirement(_view(40)) is not None
