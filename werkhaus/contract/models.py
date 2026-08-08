"""The resource model the dashboard codes against.

This module — and everything else under ``werkhaus.contract`` — must never import
from ``openhands.*``. The dashboard never sees an SDK type, concept, or vocabulary
word; that is what makes StubEngine and OpenHandsEngine drop-in swappable.
Enforced by tests/contract/test_no_sdk_imports.py.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Base(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- ids
# Opaque strings on the wire. No absolute filesystem path is ever an id.
CompanyId = str  # "co_7fbc3a"
RoleId = str  # "researcher" — stable slug, equals the agent definition name
ShiftId = str  # "co_7fbc3a/0007"
TaskId = str
ArtifactId = str
DecisionId = str


# ----------------------------------------------------------------------- company
class CompanyStatus(StrEnum):
    DRAFT = "draft"  # charter not confirmed yet
    IDLE = "idle"  # ready, no shift running
    WORKING = "working"  # a shift is in progress
    BLOCKED = "blocked"  # waiting on a human decision
    HALTED = "halted"  # budget cap or kill switch
    ARCHIVED = "archived"


Autonomy = Literal["full_auto", "semi_auto", "balanced", "limited", "full_control"]
"""How much rope the team gets, chosen at onboarding and changeable anytime.

The dial trades interruption for consumption: the auto end runs shifts on its
own and decides small things without asking (burns budget fast, few questions);
the control end never starts work unasked and checks in on everything (burns
budget fast too — on questions and planning instead of work). ``balanced`` is
the default: shifts start manually, small calls are made for you, big ones ask.
"""


class Charter(Base):
    """What the company is for.

    Structured rather than a blob: the gap between what a non-technical user types
    (two sentences) and what the roles need is the real UX problem, and a guided
    capture flow needs somewhere to put its answers.
    """

    idea: str  # verbatim, as the user typed it
    one_liner: str  # engine-normalised
    audience: str
    success_looks_like: str  # the judge objective — stable across shifts
    constraints: list[str] = Field(default_factory=list)
    tone: str | None = None
    autonomy: Autonomy = "balanced"


class Progress(Base):
    """User-facing progress. The raw judge score never leaves the engine."""

    percent: int = Field(ge=0, le=100)
    headline: str  # "Positioning is settled; the site isn't live yet."
    whats_missing: list[str] = Field(default_factory=list)
    judged_at: datetime | None = None


class Budget(Base):
    spent: Decimal
    cap: Decimal
    per_shift_cap: Decimal
    currency: Literal["USD"] = "USD"

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.cap

    @property
    def remaining(self) -> Decimal:
        return max(Decimal(0), self.cap - self.spent)


# -------------------------------------------------------------------------- role
class RoleStatus(StrEnum):
    IDLE = "idle"
    WORKING = "working"
    BLOCKED = "blocked"
    DONE = "done"
    FAILED = "failed"


class Role(Base):
    """An employee, as the user understands them. Never called an "agent" in the UI."""

    id: RoleId
    display_name: str  # "Maya"
    job_title: str  # "Market Researcher"
    avatar: str  # seed for a generated avatar
    accent: str  # hex
    blurb: str  # one sentence, shown on the org chart
    status: RoleStatus = RoleStatus.IDLE
    current_activity: str | None = None  # THE narrative line
    shifts_worked: int = 0


# ------------------------------------------------------------------------- shift
class ShiftStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    # The three below exist from day 1. If the interface only
    # knows how to succeed, the UI only learns to render success.
    FAILED = "failed"
    ABORTED = "aborted"
    BUDGET_EXCEEDED = "budget_exceeded"


class ShiftPhase(StrEnum):
    PLANNING = "planning"
    WORKING = "working"
    REVIEW = "review"
    INTEGRATING = "integrating"
    CLOSING = "closing"


class Shift(Base):
    id: ShiftId
    company_id: CompanyId
    number: int
    status: ShiftStatus
    phase: ShiftPhase | None = None
    started_at: datetime
    ended_at: datetime | None = None
    agenda: list[str] = Field(default_factory=list)  # human-readable, set at planning
    summary: str | None = None
    artifacts_produced: list[ArtifactId] = Field(default_factory=list)
    decisions_made: list[DecisionId] = Field(default_factory=list)
    cost: Decimal = Decimal(0)
    roles_active: list[RoleId] = Field(default_factory=list)
    failure_reason: str | None = None


# -------------------------------------------------------------------------- task
class TaskStatus(StrEnum):
    OPEN = "open"
    CLAIMED = "claimed"
    DONE = "done"
    DROPPED = "dropped"
    BLOCKED = "blocked"


class Task(Base):
    id: TaskId
    title: str
    detail: str = ""
    status: TaskStatus = TaskStatus.OPEN
    owner: RoleId | None = None
    claimed_by_shift: ShiftId | None = None
    priority: int = Field(default=3, ge=1, le=5)
    depends_on: list[TaskId] = Field(default_factory=list)
    created_in_shift: ShiftId | None = None
    """None when nobody was on shift — the publish gate files work of its own."""
    closed_in_shift: ShiftId | None = None


# ---------------------------------------------------------------------- artifact
class ArtifactKind(StrEnum):
    DOC = "doc"
    TABLE = "table"
    IMAGE = "image"
    SITE = "site"
    DATASET = "dataset"


Confidence = Literal["sourced", "inferred", "assumption"]


class Artifact(Base):
    """A deliverable.

    ``confidence`` and ``sources`` are in the contract from day 1 and are the
    anti-slop hook: a non-technical founder cannot tell an invented TAM from a
    researched one, so the provenance has to be structural, not a prompt request.
    """

    id: ArtifactId
    company_id: CompanyId
    kind: ArtifactKind
    title: str
    summary: str
    path: str  # company-relative. NEVER absolute — that is how home dirs get published.
    mime: str = "text/markdown"
    version: int = 1
    supersedes: ArtifactId | None = None
    produced_by: RoleId
    produced_in_shift: ShiftId
    confidence: Confidence
    sources: list[str] = Field(default_factory=list)  # URLs actually loaded
    public: bool = False  # opt-in, per artifact, for the share page
    preview_url: str | None = None  # kind == SITE
    updated_at: datetime

    @model_validator(mode="after")
    def _sourced_means_sources(self) -> Artifact:
        """"Sourced" is a claim about evidence, so it has to carry the evidence.

        A validator rather than a line in a system prompt: this is the difference
        between provenance the engine guarantees and provenance the model
        remembers to supply. It is also the check that catches us — it failed on
        our own seed data first."""
        if self.confidence == "sourced" and not self.sources:
            raise ValueError(
                f"artifact {self.path!r} claims confidence='sourced' but lists no "
                "sources; use 'inferred' or 'assumption', or supply the URLs"
            )
        return self


# ---------------------------------------------------------------------- decision
class Decision(Base):
    id: DecisionId
    title: str  # "Price at $29/mo, not $9."
    rationale: str
    alternatives_rejected: list[str] = Field(default_factory=list)
    made_by: RoleId
    made_in_shift: ShiftId
    contested_by: RoleId | None = None  # the critic
    contest_note: str | None = None
    reversible: bool = True
    at: datetime


# --------------------------------------------------------------------- objection
Severity = Literal["fatal", "serious", "noted"]


class Objection(Base):
    """The critic's output — a first-class resource, not a log line.

    A non-technical founder cannot evaluate whether an artifact is any good. What
    they *can* evaluate is a specific, falsifiable objection naming a specific
    claim and what evidence would settle it. This is the primary defence against
    plausible slop, so it gets its own list endpoint and equal billing in the UI.
    """

    id: str
    company_id: CompanyId
    shift_id: ShiftId
    severity: Severity
    text: str
    about: str | None = None  # ArtifactId or DecisionId
    about_label: str | None = None  # human-readable target, for when about is None
    settled_by: str = ""  # the evidence that would resolve it
    at: datetime


# ------------------------------------------------------------------------ ledger
class LedgerEntry(Base):
    id: str
    company_id: CompanyId
    shift_id: ShiftId | None = None
    role_id: RoleId | None = None
    amount: Decimal
    kind: Literal["llm", "tool", "adjustment"]
    note: str = ""
    at: datetime


# ------------------------------------------------------------------------- share
class ShareOptions(Base):
    include_shifts: bool = True
    include_artifacts: bool = True


class ShareLink(Base):
    token: str  # 128-bit urlsafe
    url: str
    created_at: datetime
    revoked_at: datetime | None = None
    include_shifts: bool = True
    include_artifacts: bool = True
    # The public router refuses to serve a link whose snapshot has not passed the
    # secret scan. None means "not servable" — fail closed.
    scanned_clean_at: datetime | None = None


class PublicSnapshot(Base):
    company_name: str
    one_liner: str
    progress: Progress
    roster: list[Role]
    shifts: list[Shift] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    published_at: datetime


# ----------------------------------------------------------------------- company
class Company(Base):
    id: CompanyId
    name: str
    status: CompanyStatus
    charter: Charter
    created_at: datetime
    shift_count: int = 0
    progress: Progress
    budget: Budget
    roster: list[Role] = Field(default_factory=list)
    share: ShareLink | None = None


class CharterPatch(BaseModel):
    """Partial charter update. Not frozen — it is a request body."""

    model_config = ConfigDict(extra="forbid")

    one_liner: str | None = None
    audience: str | None = None
    success_looks_like: str | None = None
    constraints: list[str] | None = None
    tone: str | None = None
    autonomy: Autonomy | None = None


class AttentionRequest(Base):
    """The one user-blocking mechanism. Everything else runs unattended."""

    id: str
    company_id: CompanyId
    shift_id: ShiftId | None = None
    role_id: RoleId | None = None
    question: str
    options: list[str] = Field(default_factory=list)
    asked_at: datetime
    answered_at: datetime | None = None
    answer: str | None = None


# ----------------------------------------------------------------- project vault
class VaultItem(Base):
    """A key the company keeps for its work — an API key, an env var, a password.

    The value never appears in this model, in any API response, in the event log,
    or on a share page. ``hint`` is the only echo the user ever gets, and it is
    enough to tell two keys apart without being enough to use one.
    """

    name: str
    hint: str  # e.g. "ends in …4f" — never the value
    added_at: datetime


class WorkspaceFile(Base):
    """One file the team wrote while building. Path is workspace-relative;
    nothing outside ``workspace/`` is ever enumerated."""

    path: str
    size: int
    kind: Literal["text", "binary"]
