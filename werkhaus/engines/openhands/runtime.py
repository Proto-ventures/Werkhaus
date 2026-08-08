"""Per-company runtime for the real engine."""

from __future__ import annotations

from typing import Any

from werkhaus.brain.store import BrainStore
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.common import CompanyRuntime
from werkhaus.engines.openhands.brain_tool import ShiftContext


class OpenHandsCompany(CompanyRuntime):
    def __init__(self, brain: BrainStore, bus: CompanyBus) -> None:
        super().__init__(brain, bus)
        self.shift_ctx: ShiftContext | None = None
        # The live conversation object, typed loosely so this module stays
        # importable without walking the SDK's import graph.
        self.conversation: Any = None
