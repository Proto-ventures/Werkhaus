"""Forget old tool output instead of summarising it.

Measured on a real shift before writing this: 874,420 prompt tokens against
22,926 completion, across 33 model calls averaging 26,497 tokens each. Ninety-
seven per cent of what a shift costs is *input*, and most of that is old text
being carried forward — a single browser page read early on rides along in
every later call.

The obvious fix is what we inherited: an LLM that periodically summarises the
history. `The Complexity Trap` (Lindenbauer et al., JetBrains Research and TUM,
NeurIPS DL4Code 2025, arXiv:2508.21433) compared that against simply dropping
old observations, on SWE-bench Verified across five model configurations, and
found masking **halves cost relative to the raw agent while matching or
slightly exceeding summarisation's solve rate**. The paper names OpenHands'
summarising condenser specifically as the thing it beats.

Two reasons it wins, and both apply to us:

* Summarising costs extra model calls, on the same budget the shift is trying
  to spend on work.
* A summary loses the record of what was already tried. Agents then repeat
  failed work — which for us means a shift that browses the same dead page
  twice and files nothing.

What is kept, deliberately:

* Every action, every message, every tool *call*. Only the environment's
  replies are dropped, and only old ones. The agent can still see what it did.
* The last ``keep_last`` observations in full, because the thing it just looked
  at is the thing it is reasoning about.
* Everything from our own brain tool. Those are small, and they are the record
  of what has been claimed and filed — the state a shift is actually building.
"""

from __future__ import annotations

import logging

from openhands.sdk.context.condenser.base import (
    CondensationRequirement,
    RollingCondenser,
)
from openhands.sdk.context.view import View
from openhands.sdk.event import ObservationEvent
from openhands.sdk.event.condenser import Condensation
from openhands.sdk.llm import LLM
from pydantic import Field

logger = logging.getLogger(__name__)

KEEP_LAST = 10
"""How many recent observations stay in full.

Ten is the paper's window. It is enough to hold the page currently being read
plus the few before it, and small enough that a long shift stops growing.
"""

NO_LLM_RESPONSE = "werkhaus-masking-no-llm-call"
"""Stands in for the response id every other condenser inherits from the model
call that produced it. Masking makes no call."""

NEVER_MASK = frozenset({"werkhaus_brain", "finish", "think"})
"""Tool replies that are cheap and load-bearing. The brain tool's answers are
the shift's own state — what was claimed, what was filed — and forgetting them
would make an employee re-claim work it had already done."""


class ObservationMaskingCondenser(RollingCondenser):
    """Drop old environment replies. Never calls a model.

    A rolling condenser normally returns a summary; this one returns only the
    set of events to forget, which the SDK removes from the view. Costing
    nothing is the point: the condenser is not supposed to be another thing
    competing for the shift's budget.
    """

    keep_last: int = Field(default=KEEP_LAST, ge=1)
    keep_first: int = Field(default=4, ge=0)
    """The opening exchange sets the task. Losing it means losing the brief."""

    trigger_at: int = Field(default=24, gt=0)
    """Start dropping once the view is this long. Below it there is nothing
    worth the disruption of a changing prefix."""

    def condensation_requirement(
        self, view: View, agent_llm: LLM | None = None
    ) -> CondensationRequirement | None:
        if len(view) < self.trigger_at:
            return None
        return CondensationRequirement.SOFT if self._maskable(view) else None

    def get_condensation(
        self, view: View, agent_llm: LLM | None = None
    ) -> Condensation:
        forget = self._maskable(view)
        logger.info(
            "masking %d old observations from a view of %d events",
            len(forget),
            len(view),
        )
        return Condensation(
            forgotten_event_ids=set(forget),
            # No summary on purpose. A summary is the thing that costs a call
            # and loses the record of what was already tried.
            summary=None,
            # The field exists because every other condenser is produced *by*
            # a model response and is traced back to it. This one never calls a
            # model, which is the point, so it says so rather than borrowing an
            # unrelated id and making the trace lie.
            llm_response_id=NO_LLM_RESPONSE,
        )

    def _maskable(self, view: View) -> list[str]:
        """Old environment replies, oldest first, excluding the protected ones."""
        events = list(view.events)
        window = events[self.keep_first : len(events) - self.keep_last]
        return [
            event.id
            for event in window
            if isinstance(event, ObservationEvent)
            and getattr(event, "tool_name", "") not in NEVER_MASK
        ]
