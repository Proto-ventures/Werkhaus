"""Runtime state for one stub company.

Everything engine-agnostic lives in :class:`CompanyRuntime`. The only thing the
stub adds is the scenario — the script that stands in for real employees.
"""

from __future__ import annotations

from werkhaus.brain.store import BrainStore
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.common import CompanyRuntime
from werkhaus.engines.stub.scenario import Scenario


class StubCompany(CompanyRuntime):
    def __init__(self, brain: BrainStore, scenario: Scenario, bus: CompanyBus) -> None:
        super().__init__(brain, bus)
        self.scenario = scenario
