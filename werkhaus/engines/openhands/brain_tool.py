"""The company brain, as a tool an employee can hold.

Three reasons this exists, only one of which is concurrency:

1. **Concurrency** — claims are compare-and-set in the store; two employees
   cannot take the same task.
2. **Schema** — the model fills a validated action. ``confidence`` is a required
   field on ``record_artifact``, which enforces sourcing discipline far better
   than a paragraph in a system prompt. And the executor cross-checks: a
   "sourced" claim whose URL was never actually visited this shift is downgraded
   to "inferred", out loud.
3. **Instrumentation** — every semantically meaningful act becomes a first-class
   dashboard event with a real title, emitted here, where the structured facts
   are, not re-parsed from prose downstream.

The executor and the engine must share one :class:`BrainStore` instance (two
instances over the same directory do not share in-memory projections), but tool
params must stay JSON-serializable because the agent spec is serialized. So the
engine registers a :class:`ShiftContext` in a process-global registry and the
tool looks it up by company id — the only param that crosses the boundary.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

from openhands.sdk.tool import (
    Action,
    Observation,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)
from pydantic import ConfigDict, model_validator

from werkhaus.brain.digest import render_digest
from werkhaus.brain.store import BrainStore
from werkhaus.contract.errors import TaskAlreadyClaimed
from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import ArtifactKind, Confidence
from werkhaus.engines.bus import CompanyBus
from werkhaus.engines.roster import display_name

logger = logging.getLogger(__name__)


# ------------------------------------------------------------- shift context
@dataclass
class ShiftContext:
    """Everything the tool, the narrator, the watchdog and halt share about the
    shift that is running right now."""

    company_id: str
    shift_id: str
    role_id: str
    shift_number: int
    brain: BrainStore
    bus: CompanyBus
    stopped: threading.Event = field(default_factory=threading.Event)
    browsed_urls: set[str] = field(default_factory=set)
    """Pages that actually loaded. A citation is only "sourced" if its URL is
    in here, so a page that failed to load must never be added."""

    pending_url: str | None = None
    """A navigation that has been issued and not yet answered for. Promoted
    into ``browsed_urls`` only when the observation says it worked."""
    claimed_task_ids: list[str] = field(default_factory=list)
    last_activity_emit: float = 0.0
    # The run-limit code the SDK reported, if any ("MaxBudgetReached", ...).
    error_code: str | None = None
    # Mirror of the live activity line, read by CompanyRuntime.company().
    set_activity: Any = None  # Callable[[str | None], None] | None

    @property
    def name(self) -> str:
        return display_name(self.role_id)


_CONTEXTS: dict[str, ShiftContext] = {}


def register_shift(ctx: ShiftContext) -> None:
    _CONTEXTS[ctx.company_id] = ctx


def unregister_shift(company_id: str) -> None:
    _CONTEXTS.pop(company_id, None)


def get_shift_context(company_id: str) -> ShiftContext | None:
    return _CONTEXTS.get(company_id)


def normalize_url(url: str) -> str:
    """Two spellings of the same page must compare equal: drop the fragment,
    the trailing slash, and the scheme's case."""
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/")
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


# --------------------------------------------------------------------- schema
class BrainAction(Action):
    """One operation against the company brain.

    Unknown fields are dropped rather than refused. The SDK's ``Action``
    forbids extras, which is right for catching our own typos and wrong for a
    schema an LLM fills in: a model that adds a plausible extra key — a task id
    alongside the artifact it came from — gets its whole call rejected, and if
    that call was ``record_artifact`` the shift loses the only thing it made.
    Being liberal here costs nothing; the extras are logged so a field the
    model keeps reaching for can be made real.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def _note_extras(cls, data: Any) -> Any:
        if isinstance(data, dict):
            unknown = sorted(set(data) - set(cls.model_fields))
            if unknown:
                logger.info("brain tool ignored unknown fields: %s", ", ".join(unknown))
        return data

    op: Literal[
        "read_digest",
        "claim_task",
        "complete_task",
        "add_task",
        "record_artifact",
    ]
    task_id: str | None = None
    title: str | None = None
    detail: str | None = None
    path: str | None = None
    summary: str | None = None
    artifact_kind: ArtifactKind = ArtifactKind.DOC
    confidence: Confidence | None = None
    sources: list[str] = []


class BrainObservation(Observation):
    pass


def _error(text: str) -> BrainObservation:
    return BrainObservation.from_text(text, is_error=True)


class BrainExecutor(ToolExecutor):
    def __init__(self, ctx: ShiftContext) -> None:
        self.ctx = ctx

    def __call__(
        self, action: BrainAction, conversation: Any = None
    ) -> BrainObservation:
        ctx = self.ctx
        # The discard guard. After a halt nothing may reach the brain, no
        # matter how long the worker thread takes to notice.
        if ctx.stopped.is_set():
            return _error("This shift is over. Stop working and finish up.")
        try:
            return getattr(self, f"_{action.op}")(action)
        except TaskAlreadyClaimed:
            return _error("Someone already took that task; pick another.")
        except Exception:
            logger.exception("brain op %s failed", action.op)
            return _error(
                "That didn't work. Check the fields and try once more, or move on."
            )

    # ------------------------------------------------------------------- ops
    def _read_digest(self, action: BrainAction) -> BrainObservation:
        return BrainObservation.from_text(
            render_digest(
                self.ctx.brain,
                role_id=self.ctx.role_id,
                role_name=self.ctx.name,
                shift_number=self.ctx.shift_number,
            )
        )

    def _claim_task(self, action: BrainAction) -> BrainObservation:
        ctx = self.ctx
        if not action.task_id:
            return _error("claim_task needs task_id (from the digest's open items).")
        task = ctx.brain.claim_task(
            action.task_id, role_id=ctx.role_id, shift_id=ctx.shift_id
        )
        ctx.claimed_task_ids.append(task.id)
        ctx.bus.emit_threadsafe(
            K.TASK_CLAIMED,
            f"{ctx.name} took on: {task.title}",
            shift_id=ctx.shift_id,
            role_id=ctx.role_id,
            ref=task.id,
        )
        return BrainObservation.from_text(f"Claimed: {task.title}")

    def _complete_task(self, action: BrainAction) -> BrainObservation:
        ctx = self.ctx
        if not action.task_id:
            return _error("complete_task needs task_id.")
        ctx.brain.complete_task(
            action.task_id, role_id=ctx.role_id, shift_id=ctx.shift_id
        )
        title = ctx.brain.state.tasks[action.task_id].title
        ctx.bus.emit_threadsafe(
            K.TASK_DONE,
            f"{ctx.name} finished: {title}",
            shift_id=ctx.shift_id,
            role_id=ctx.role_id,
            ref=action.task_id,
        )
        return BrainObservation.from_text(f"Done: {title}")

    def _add_task(self, action: BrainAction) -> BrainObservation:
        ctx = self.ctx
        if not action.title:
            return _error("add_task needs a title.")
        task = ctx.brain.add_task(
            title=action.title,
            shift_id=ctx.shift_id,
            detail=action.detail or "",
            actor=ctx.role_id,
        )
        ctx.bus.emit_threadsafe(
            K.TASK_ADDED,
            f"{ctx.name} added: {task.title}",
            shift_id=ctx.shift_id,
            role_id=ctx.role_id,
            ref=task.id,
        )
        return BrainObservation.from_text(
            "Recorded. It will be on the backlog next shift."
        )

    def _record_artifact(self, action: BrainAction) -> BrainObservation:
        ctx = self.ctx
        missing = [
            name
            for name in ("path", "title", "summary", "confidence")
            if not getattr(action, name)
        ]
        if missing:
            return _error(f"record_artifact needs: {', '.join(missing)}.")
        assert action.path and action.title and action.summary and action.confidence

        # The path the agent knows is workspace-relative; the brain records
        # company-root-relative. Refuse anything that tries to leave.
        if action.path.startswith("/") or ".." in action.path:
            return _error("Use a plain path inside your workspace, like notes.md.")
        workspace_file = ctx.brain.paths.workspace / action.path
        if not workspace_file.is_file():
            return _error(
                f"There's no file at {action.path}. Write the document first, "
                "then record it."
            )

        # The provenance cross-check: "sourced" means an URL you actually
        # loaded this shift. Anything else is downgraded, out loud.
        confidence: Confidence = action.confidence
        note = ""
        if confidence == "sourced":
            unvisited = [
                url
                for url in action.sources
                if normalize_url(url) not in ctx.browsed_urls
            ]
            if not action.sources:
                confidence = "inferred"
                note = " Filed as inferred: sourced needs at least one URL."
            elif unvisited:
                confidence = "inferred"
                note = (
                    " Filed as inferred: I can't confirm you visited "
                    f"{', '.join(unvisited[:3])} this shift."
                )

        existing = next(
            (
                a
                for a in ctx.brain.state.artifacts.values()
                if a.path == f"workspace/{action.path}"
            ),
            None,
        )
        artifact = ctx.brain.record_artifact(
            path=f"workspace/{action.path}",
            title=action.title,
            summary=action.summary,
            kind=action.artifact_kind,
            confidence=confidence,
            sources=list(action.sources),
            role_id=ctx.role_id,
            shift_id=ctx.shift_id,
        )
        ctx.bus.emit_threadsafe(
            K.ARTIFACT_UPDATED if existing else K.ARTIFACT_CREATED,
            f"{ctx.name} finished {artifact.title}.",
            detail=artifact.summary,
            shift_id=ctx.shift_id,
            role_id=ctx.role_id,
            ref=artifact.id,
            payload={"confidence": confidence, "sources": len(action.sources)},
        )
        return BrainObservation.from_text(
            f"Recorded {artifact.title} ({confidence}).{note}"
        )


TOOL_DESCRIPTION = """Your connection to the company.

Operations:
- read_digest: where the company stands, your open tasks, decisions in force.
  Call this first, every shift.
- claim_task(task_id): take a task before working on it.
- complete_task(task_id): mark a claimed task finished.
- add_task(title, detail?): record an open question or follow-up for the team.
- record_artifact(path, title, summary, confidence, sources, artifact_kind?): file a
  document you wrote in your workspace. confidence is "sourced" only if every
  source URL is a page you actually opened this shift; otherwise use "inferred"
  (reasoned from something sourced) or "assumption" (made up to keep going).

Work is not done until it is recorded here."""


class WerkhausBrainTool(ToolDefinition[BrainAction, BrainObservation]):
    """Auto-derived tool name: ``werkhaus_brain``."""

    @classmethod
    def create(cls, conv_state=None, **params: Any) -> Sequence[WerkhausBrainTool]:
        company_id = params["company_id"]
        ctx = get_shift_context(company_id)
        if ctx is None:
            raise RuntimeError(f"no shift context registered for {company_id}")
        return [
            cls(
                description=TOOL_DESCRIPTION,
                action_type=BrainAction,
                observation_type=BrainObservation,
                executor=BrainExecutor(ctx),
            )
        ]


register_tool("werkhaus_brain", WerkhausBrainTool)
