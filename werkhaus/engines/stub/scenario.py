"""Scenario schema.

A scenario is not a flat list of events. It declares what each employee *does*,
and the engine expands that through the same five phases the real ShiftRunner
uses (planning -> working -> review -> integrating -> closing), with jitter.

That matters: if the stub emitted a canned event list, the UI would be built
against a shape the real engine never produces, and M4 would be a rewrite. This
way the only thing that is fake is the content.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from werkhaus.contract.models import ArtifactKind, Confidence

SCENARIO_DIR = Path(__file__).parent / "scenarios"

Outcome = Literal["completed", "budget_exceeded", "failed", "needs_attention"]
Severity = Literal["fatal", "serious", "noted"]


class _Node(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ScenarioArtifact(_Node):
    path: str
    title: str
    summary: str
    kind: ArtifactKind = ArtifactKind.DOC
    confidence: Confidence
    sources: list[str] = Field(default_factory=list)
    mime: str = "text/markdown"
    preview_url: str | None = None
    body: str = ""


class ScenarioDecision(_Node):
    title: str
    rationale: str
    alternatives_rejected: list[str] = Field(default_factory=list)
    reversible: bool = True


class ScenarioObjection(_Node):
    severity: Severity
    text: str
    about: str | None = None  # artifact path or decision title the objection names
    settled_by: str = ""  # what evidence would resolve it


class ScenarioAttention(_Node):
    question: str
    options: list[str] = Field(default_factory=list)


class ScenarioRoleWork(_Node):
    """One employee's shift."""

    role: str
    activities: list[str] = Field(default_factory=list)
    tasks_claimed: list[str] = Field(default_factory=list)
    tasks_added: list[str] = Field(default_factory=list)
    artifacts: list[ScenarioArtifact] = Field(default_factory=list)
    decisions: list[ScenarioDecision] = Field(default_factory=list)
    says: str | None = None  # the report-back line
    cost: float = 0.0
    # Failure injection, per role.
    fails: bool = False
    failure_reason: str | None = None
    attention: ScenarioAttention | None = None
    # Seconds of simulated work, before jitter and the speed multiplier.
    duration: float = 90.0


class ScenarioCharter(_Node):
    idea: str
    one_liner: str
    audience: str
    success_looks_like: str
    constraints: list[str] = Field(default_factory=list)
    tone: str | None = None


class ScenarioProgress(_Node):
    percent: int = Field(ge=0, le=100)
    headline: str
    whats_missing: list[str] = Field(default_factory=list)


class Scenario(_Node):
    name: str
    title: str
    outcome: Outcome = "completed"
    company_name: str
    charter: ScenarioCharter
    budget_cap: float = 60.0
    per_shift_cap: float = 12.0
    agenda: list[str] = Field(default_factory=list)
    work: list[ScenarioRoleWork] = Field(default_factory=list)
    objections: list[ScenarioObjection] = Field(default_factory=list)
    contests: dict[str, str] = Field(default_factory=dict)  # decision title -> note
    progress: ScenarioProgress
    shift_summary: str = ""
    # Volume knob. `firehose` sets this high so the UI meets thousands of events
    # and someone has to build virtualisation and coalescing before shipping.
    activity_repeat: int = 1
    # Wall-clock scale for one activity, before jitter. Real role runs are
    # 2-8 minutes; this is what makes the stub honest about latency.
    tick_seconds: float = 6.0


def load_scenario(name: str) -> Scenario:
    path = SCENARIO_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in SCENARIO_DIR.glob("*.yaml")))
        raise FileNotFoundError(f"No scenario {name!r}. Available: {available}")
    return Scenario.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def list_scenarios() -> list[str]:
    return sorted(path.stem for path in SCENARIO_DIR.glob("*.yaml"))
