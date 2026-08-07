"""Runtime state for one stub company.

Everything durable lives in :class:`BrainStore`. What is here is what genuinely
should not survive a restart: the running task, the socket bus, and who is
currently doing what. An employee's live activity line is not a fact about the
company — it is a fact about right now.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from werkhaus.brain.store import BrainStore
from werkhaus.contract.models import (
    Budget,
    Company,
    CompanyStatus,
    Role,
    RoleStatus,
    ShareLink,
    Shift,
)
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.roster import ROSTER
from werkhaus.engines.stub.scenario import Scenario

CENTS = Decimal("0.01")


class StubCompany:
    def __init__(self, brain: BrainStore, scenario: Scenario, bus: CompanyBus) -> None:
        self.brain = brain
        self.scenario = scenario
        self.bus = bus
        self.id = brain.company_id
        self.roles: dict[str, dict[str, Any]] = {
            role.id: {"status": RoleStatus.IDLE, "activity": None} for role in ROSTER
        }
        self.task_handle: asyncio.Task[None] | None = None
        self.answered: dict[str, asyncio.Event] = {}

    # ---------------------------------------------------------------- budget
    @property
    def cap(self) -> Decimal:
        return Decimal(str(self.brain.state.metrics.get("budget_cap", "60.00")))

    @property
    def per_shift_cap(self) -> Decimal:
        return Decimal(str(self.brain.state.metrics.get("per_shift_cap", "12.00")))

    @property
    def spent(self) -> Decimal:
        return self.brain.state.spent

    @property
    def halted(self) -> bool:
        return bool(self.brain.state.metrics.get("halted", False))

    @property
    def archived(self) -> bool:
        return bool(self.brain.state.metrics.get("archived", False))

    # ---------------------------------------------------------------- status
    @property
    def status(self) -> CompanyStatus:
        """Derived, never stored.

        A status field that can disagree with the facts it summarises will
        eventually disagree with them — usually as a company stuck on "working"
        with nothing running.
        """
        if self.archived:
            return CompanyStatus.ARCHIVED
        if self.halted:
            return CompanyStatus.HALTED
        if any(r.answered_at is None for r in self.brain.state.attention.values()):
            return CompanyStatus.BLOCKED
        if self.task_handle is not None and not self.task_handle.done():
            return CompanyStatus.WORKING
        if not self.brain.state.charter:
            return CompanyStatus.DRAFT
        return CompanyStatus.IDLE

    # ----------------------------------------------------------------- views
    @property
    def shifts(self) -> list[Shift]:
        return sorted(self.brain.state.shifts.values(), key=lambda s: s.number)

    @property
    def share(self) -> ShareLink | None:
        raw = self.brain.state.metrics.get("share")
        return ShareLink.model_validate(raw) if raw else None

    def company(self) -> Company:
        state = self.brain.state
        roster = [
            Role(
                **{
                    **base.model_dump(),
                    "status": self.roles[base.id]["status"],
                    "current_activity": self.roles[base.id]["activity"],
                    "shifts_worked": sum(
                        1 for s in state.shifts.values() if base.id in s.roles_active
                    ),
                }
            )
            for base in ROSTER
        ]
        charter = state.charter
        assert charter is not None, "a company always has a charter by creation time"
        return Company(
            id=self.id,
            name=state.name,
            status=self.status,
            charter=charter,
            created_at=self.created_at,
            shift_count=len(state.shifts),
            progress=state.progress,
            budget=Budget(
                spent=self.spent.quantize(CENTS),
                cap=self.cap.quantize(CENTS),
                per_shift_cap=self.per_shift_cap.quantize(CENTS),
            ),
            roster=roster,
            share=self.share,
        )

    @property
    def created_at(self) -> datetime:
        raw = self.brain.state.metrics.get("created_at")
        return datetime.fromisoformat(raw) if raw else datetime.now(UTC)

    def clear_activity(self) -> None:
        for role in self.roles.values():
            if role["status"] is not RoleStatus.FAILED:
                role["status"] = RoleStatus.IDLE
            role["activity"] = None
