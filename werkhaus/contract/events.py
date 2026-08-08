"""The stream model.

A dashboard that renders only ``kind`` + ``text`` + ``at`` is a complete, shippable
product. Everything else on ShiftEvent is progressive enhancement. That constraint
is what keeps the narration honest: an employee cannot emit something richer
than the real engine can produce.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from werkhaus.contract.models import Base, CompanyId, RoleId, ShiftId


class ShiftEventKind(StrEnum):
    SHIFT_STARTED = "shift.started"
    PHASE_CHANGED = "shift.phase"
    SHIFT_COMPLETED = "shift.completed"
    SHIFT_FAILED = "shift.failed"

    ROLE_STARTED = "role.started"
    ROLE_ACTIVITY = "role.activity"  # the narrative line — rate-limited, coalesced
    ROLE_SAID = "role.said"  # the employee reporting back
    ROLE_FINISHED = "role.finished"
    ROLE_FAILED = "role.failed"

    ARTIFACT_CREATED = "artifact.created"
    ARTIFACT_UPDATED = "artifact.updated"

    DECISION_MADE = "decision.made"
    DECISION_CONTESTED = "decision.contested"

    TASK_ADDED = "task.added"
    TASK_CLAIMED = "task.claimed"
    TASK_DONE = "task.done"

    BUDGET_SPENT = "budget.spent"
    BUDGET_EXCEEDED = "budget.exceeded"

    PROGRESS_UPDATED = "progress.updated"
    ATTENTION_NEEDED = "attention.needed"  # the only user-blocking event
    HEARTBEAT = "heartbeat"


class ShiftEvent(Base):
    # Monotonic per company. THE resume cursor — not a timestamp, because
    # timestamps collide and clocks drift.
    seq: int
    id: str
    company_id: CompanyId
    shift_id: ShiftId | None = None
    role_id: RoleId | None = None
    kind: ShiftEventKind
    at: datetime

    # ALWAYS present, ALWAYS user-readable, ALWAYS self-sufficient.
    # Never a shell command, a path outside the company dir, a stack trace,
    # a token count, or a model name.
    text: str
    detail: str | None = None  # optional expandable second line
    icon: str | None = None  # lucide icon name
    ref: str | None = None  # ArtifactId | DecisionId | TaskId
    payload: dict[str, Any] = Field(default_factory=dict)
