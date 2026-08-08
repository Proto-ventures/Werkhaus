"""The company brain.

The SDK gives per-conversation event sourcing and no cross-conversation shared
world state. This is that state.

One rule holds the design together: **``log.jsonl`` is the source of truth and
everything else is a projection of it.** Projections can be deleted and rebuilt;
no fact exists only in a projection. That is what makes "nothing was lost" a
literal statement after a crash rather than a hopeful one.

Writes are serialized by a process-local ``RLock`` *and* a cross-process
``FileLock``, because in M3 several role conversations mutate this concurrently
from different threads, and later possibly different processes.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import yaml
from filelock import FileLock

from werkhaus.brain.layout import CompanyPaths
from werkhaus.contract.errors import (
    ArtifactOwnedByAnotherRole,
    NotFound,
    TaskAlreadyClaimed,
)
from werkhaus.contract.integrations import ProvisionedResource
from werkhaus.contract.models import (
    Artifact,
    ArtifactKind,
    AttentionRequest,
    Charter,
    Confidence,
    Decision,
    LedgerEntry,
    Objection,
    Progress,
    Severity,
    Shift,
    ShiftStatus,
    Task,
    TaskStatus,
)

logger = logging.getLogger(__name__)

CENTS = Decimal("0.01")


def _now() -> datetime:
    return datetime.now(UTC)


def _oid(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(3)}"


class CompanyBrain:
    """The in-memory projection. Rebuilt from the log, never authoritative."""

    def __init__(self) -> None:
        self.charter: Charter | None = None
        self.name: str = ""
        self.progress = Progress(
            percent=0, headline="Nothing has happened yet.", whats_missing=[]
        )
        self.tasks: dict[str, Task] = {}
        self.artifacts: dict[str, Artifact] = {}
        self.decisions: dict[str, Decision] = {}
        self.objections: dict[str, Objection] = {}
        self.attention: dict[str, AttentionRequest] = {}
        self.shifts: dict[str, Shift] = {}
        self.ledger: list[LedgerEntry] = []
        self.metrics: dict[str, Any] = {}
        self.spent = Decimal("0")
        self.notes: list[str] = []
        # What happened to each connection, in order. Never a stored value:
        # a secret written to an append-only log can never be deleted.
        self.integrations: dict[str, dict[str, Any]] = {}
        self.resources: dict[str, ProvisionedResource] = {}

    @property
    def open_tasks(self) -> list[Task]:
        return [t for t in self.tasks.values() if t.status is TaskStatus.OPEN]


class BrainStore:
    """Append-only company state. One writer at a time, by construction."""

    def __init__(self, root: Path | str, company_id: str) -> None:
        self.paths = CompanyPaths(root)
        self.company_id = company_id
        self.paths.ensure()
        self._rlock = threading.RLock()
        self._flock = FileLock(str(self.paths.lock), timeout=30)
        self.state = CompanyBrain()
        self._seq = 0
        self.replay()

    # ================================================================== replay
    def _read_log(self) -> Iterator[dict[str, Any]]:
        """Parse the log, physically truncating a torn tail.

        The truncation has to hit the *file*, not just this read. A torn final
        line is the normal shape of a crash — the process died mid-write — and if
        we only skipped it in memory, the next append would land after the
        garbage and be skipped by every future replay. One crash would silently
        stop the company from recording anything ever again.

        Standard write-ahead-log recovery: everything after the first unparseable
        record is unreachable, so cut there and say so loudly.
        """
        if not self.paths.log.exists():
            return

        raw = self.paths.log.read_bytes()
        good_bytes = 0
        records: list[dict[str, Any]] = []
        torn_at: int | None = None

        for number, line in enumerate(raw.split(b"\n"), 1):
            if not line.strip():
                good_bytes += len(line) + 1
                continue
            try:
                records.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError):
                torn_at = number
                break
            good_bytes += len(line) + 1

        if torn_at is not None:
            dropped = len(raw) - good_bytes
            logger.error(
                "torn log at line %d of %s: discarding the trailing %d byte(s) so "
                "future writes are readable. %d entries recovered.",
                torn_at,
                self.paths.log,
                dropped,
                len(records),
            )
            with self.paths.log.open("r+b") as handle:
                handle.truncate(max(0, good_bytes))
                handle.flush()
                os.fsync(handle.fileno())

        yield from records

    def replay(self) -> None:
        """Rebuild the whole projection from the log. Idempotent."""
        with self._rlock:
            self.state = CompanyBrain()
            self._seq = 0
            for entry in self._read_log():
                self._seq = max(self._seq, int(entry.get("seq", 0)))
                try:
                    self._apply(entry)
                except Exception:
                    logger.exception("could not apply log entry %s", entry.get("seq"))

    def rebuild(self) -> None:
        """Replay and rewrite every projection file. `werkhaus brain rebuild`."""
        self.replay()
        with self._rlock:
            self._write_projections()

    # =================================================================== write
    def _append(self, op: str, data: dict[str, Any], actor: str | None = None) -> None:
        with self._rlock, self._flock:
            self._seq += 1
            entry = {
                "seq": self._seq,
                "at": _now().isoformat(),
                "op": op,
                "actor": actor,
                "data": data,
            }
            # Durable before visible: fsync, then project. If we die between the
            # two, replay reconstructs the projection anyway.
            with self.paths.log.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._apply(entry)
            self._write_projections()

    def _apply(self, entry: dict[str, Any]) -> None:
        handler = getattr(self, f"_on_{entry['op']}", None)
        if handler is None:
            logger.warning("unknown brain op %r", entry["op"])
            return
        handler(entry["data"], entry.get("actor"), entry["at"])

    # ------------------------------------------------------------- charter
    def set_charter(self, charter: Charter, name: str) -> None:
        self._append(
            "charter",
            {"charter": charter.model_dump(mode="json"), "name": name},
        )

    def _on_charter(self, data: dict, actor: str | None, at: str) -> None:
        self.state.charter = Charter.model_validate(data["charter"])
        self.state.name = data["name"]

    # ---------------------------------------------------------------- tasks
    def add_task(  # noqa: PLR0913
        self,
        *,
        title: str,
        shift_id: str | None,
        detail: str = "",
        owner: str | None = None,
        priority: int = 3,
        actor: str | None = None,
    ) -> Task:
        task_id = _oid("tk")
        self._append(
            "add_task",
            {
                "id": task_id,
                "title": title,
                "detail": detail,
                "owner": owner,
                "priority": priority,
                "shift_id": shift_id,
            },
            actor,
        )
        return self.state.tasks[task_id]

    def _on_add_task(self, data: dict, actor: str | None, at: str) -> None:
        self.state.tasks[data["id"]] = Task(
            id=data["id"],
            title=data["title"],
            detail=data.get("detail", ""),
            status=TaskStatus.OPEN,
            owner=data.get("owner"),
            priority=data.get("priority", 3),
            created_in_shift=data["shift_id"],
        )

    def claim_task(self, task_id: str, *, role_id: str, shift_id: str) -> Task:
        """Compare-and-set.

        Two employees running in parallel cannot both take the same task. The
        loser gets a refusal it can act on ("someone already took that, pick
        another") instead of both quietly doing the same work.
        """
        with self._rlock:
            task = self.state.tasks.get(task_id)
            if task is None:
                raise NotFound("That task doesn't exist.")
            if task.status is not TaskStatus.OPEN:
                raise TaskAlreadyClaimed(
                    f"{task.owner or 'Someone'} already took “{task.title}”."
                )
            self._append(
                "claim_task", {"id": task_id, "shift_id": shift_id}, role_id
            )
            return self.state.tasks[task_id]

    def _on_claim_task(self, data: dict, actor: str | None, at: str) -> None:
        task = self.state.tasks.get(data["id"])
        if task:
            self.state.tasks[data["id"]] = task.model_copy(
                update={
                    "status": TaskStatus.CLAIMED,
                    "owner": actor,
                    "claimed_by_shift": data["shift_id"],
                }
            )

    def complete_task(self, task_id: str, *, role_id: str, shift_id: str) -> None:
        self._append("complete_task", {"id": task_id, "shift_id": shift_id}, role_id)

    def _on_complete_task(self, data: dict, actor: str | None, at: str) -> None:
        task = self.state.tasks.get(data["id"])
        if task:
            self.state.tasks[data["id"]] = task.model_copy(
                update={"status": TaskStatus.DONE, "closed_in_shift": data["shift_id"]}
            )

    def block_task(self, task_id: str, *, reason: str, role_id: str) -> None:
        self._append("block_task", {"id": task_id, "reason": reason}, role_id)

    def _on_block_task(self, data: dict, actor: str | None, at: str) -> None:
        task = self.state.tasks.get(data["id"])
        if task:
            self.state.tasks[data["id"]] = task.model_copy(
                update={"status": TaskStatus.BLOCKED, "detail": data["reason"]}
            )

    # ------------------------------------------------------------ artifacts
    def record_artifact(
        self,
        *,
        path: str,
        title: str,
        summary: str,
        kind: ArtifactKind,
        confidence: Confidence,
        sources: list[str],
        role_id: str,
        shift_id: str,
        mime: str = "text/markdown",
        preview_url: str | None = None,
    ) -> Artifact:
        if path.startswith("/") or ".." in path:
            raise ValueError(f"artifact path must be company-relative: {path!r}")

        with self._rlock:
            existing = next(
                (a for a in self.state.artifacts.values() if a.path == path), None
            )
            # One owning role per artifact per shift. Enforced here rather than
            # asked for in a prompt, because a prompt is a suggestion.
            if (
                existing
                and existing.produced_in_shift == shift_id
                and existing.produced_by != role_id
            ):
                raise ArtifactOwnedByAnotherRole(
                    f"{existing.produced_by} is working on {title} this shift."
                )
            artifact_id = _oid("ar")
            self._append(
                "record_artifact",
                {
                    "id": artifact_id,
                    "path": path,
                    "title": title,
                    "summary": summary,
                    "kind": kind,
                    "confidence": confidence,
                    "sources": sources,
                    "mime": mime,
                    "preview_url": preview_url,
                    "shift_id": shift_id,
                    "supersedes": existing.id if existing else None,
                    "version": (existing.version + 1) if existing else 1,
                },
                role_id,
            )
            return self.state.artifacts[artifact_id]

    def _on_record_artifact(self, data: dict, actor: str | None, at: str) -> None:
        if data.get("supersedes"):
            self.state.artifacts.pop(data["supersedes"], None)
        self.state.artifacts[data["id"]] = Artifact(
            id=data["id"],
            company_id=self.company_id,
            kind=ArtifactKind(data["kind"]),
            title=data["title"],
            summary=data["summary"],
            path=data["path"],
            mime=data.get("mime", "text/markdown"),
            version=data.get("version", 1),
            supersedes=data.get("supersedes"),
            produced_by=actor or "unknown",
            produced_in_shift=data["shift_id"],
            confidence=data["confidence"],
            sources=list(data.get("sources", [])),
            preview_url=data.get("preview_url"),
            updated_at=datetime.fromisoformat(at),
        )

    def set_artifact_public(self, artifact_id: str, public: bool) -> None:
        self._append("set_artifact_public", {"id": artifact_id, "public": public})

    def _on_set_artifact_public(self, data: dict, actor: str | None, at: str) -> None:
        artifact = self.state.artifacts.get(data["id"])
        if artifact:
            self.state.artifacts[data["id"]] = artifact.model_copy(
                update={"public": data["public"]}
            )

    # ------------------------------------------------------------ decisions
    def record_decision(
        self,
        *,
        title: str,
        rationale: str,
        alternatives_rejected: list[str],
        role_id: str,
        shift_id: str,
        reversible: bool = True,
    ) -> Decision:
        decision_id = _oid("de")
        self._append(
            "record_decision",
            {
                "id": decision_id,
                "title": title,
                "rationale": rationale,
                "alternatives_rejected": alternatives_rejected,
                "reversible": reversible,
                "shift_id": shift_id,
            },
            role_id,
        )
        return self.state.decisions[decision_id]

    def _on_record_decision(self, data: dict, actor: str | None, at: str) -> None:
        self.state.decisions[data["id"]] = Decision(
            id=data["id"],
            title=data["title"],
            rationale=data["rationale"],
            alternatives_rejected=list(data.get("alternatives_rejected", [])),
            made_by=actor or "unknown",
            made_in_shift=data["shift_id"],
            reversible=data.get("reversible", True),
            at=datetime.fromisoformat(at),
        )

    def contest_decision(self, decision_id: str, *, role_id: str, note: str) -> None:
        self._append("contest_decision", {"id": decision_id, "note": note}, role_id)

    def _on_contest_decision(self, data: dict, actor: str | None, at: str) -> None:
        decision = self.state.decisions.get(data["id"])
        if decision:
            self.state.decisions[data["id"]] = decision.model_copy(
                update={"contested_by": actor, "contest_note": data["note"]}
            )

    # ----------------------------------------------------------- objections
    def record_objection(
        self,
        *,
        severity: Severity,
        text: str,
        settled_by: str,
        role_id: str,
        shift_id: str,
        about: str | None = None,
        about_label: str | None = None,
    ) -> Objection:
        objection_id = _oid("ob")
        self._append(
            "record_objection",
            {
                "id": objection_id,
                "severity": severity,
                "text": text,
                "settled_by": settled_by,
                "about": about,
                "about_label": about_label,
                "shift_id": shift_id,
            },
            role_id,
        )
        return self.state.objections[objection_id]

    def _on_record_objection(self, data: dict, actor: str | None, at: str) -> None:
        self.state.objections[data["id"]] = Objection(
            id=data["id"],
            company_id=self.company_id,
            shift_id=data["shift_id"],
            severity=data["severity"],
            text=data["text"],
            about=data.get("about"),
            about_label=data.get("about_label"),
            settled_by=data.get("settled_by", ""),
            at=datetime.fromisoformat(at),
        )

    # --------------------------------------------------------------- shifts
    def open_shift(self, *, number: int, agenda: list[str]) -> Shift:
        shift_id = f"{self.company_id}/{number:04d}"
        self._append(
            "open_shift", {"id": shift_id, "number": number, "agenda": agenda}
        )
        return self.state.shifts[shift_id]

    def _on_open_shift(self, data: dict, actor: str | None, at: str) -> None:
        self.state.shifts[data["id"]] = Shift(
            id=data["id"],
            company_id=self.company_id,
            number=data["number"],
            status=ShiftStatus.RUNNING,
            phase=None,
            started_at=datetime.fromisoformat(at),
            agenda=list(data.get("agenda", [])),
        )

    def update_shift(self, shift_id: str, **fields: Any) -> None:
        self._append("update_shift", {"id": shift_id, "fields": fields})

    def _on_update_shift(self, data: dict, actor: str | None, at: str) -> None:
        shift = self.state.shifts.get(data["id"])
        if not shift:
            return
        fields = dict(data["fields"])
        if "cost" in fields:
            fields["cost"] = Decimal(str(fields["cost"]))
        self.state.shifts[data["id"]] = shift.model_copy(update=fields)

    def close_shift(
        self,
        shift_id: str,
        *,
        status: ShiftStatus,
        summary: str | None = None,
        failure_reason: str | None = None,
        cost: Decimal = Decimal("0"),
    ) -> Shift:
        self._append(
            "close_shift",
            {
                "id": shift_id,
                "status": status,
                "summary": summary,
                "failure_reason": failure_reason,
                "cost": str(cost.quantize(CENTS)),
            },
        )
        return self.state.shifts[shift_id]

    def _on_close_shift(self, data: dict, actor: str | None, at: str) -> None:
        shift = self.state.shifts.get(data["id"])
        if not shift:
            return
        self.state.shifts[data["id"]] = shift.model_copy(
            update={
                "status": ShiftStatus(data["status"]),
                "phase": None,
                "ended_at": datetime.fromisoformat(at),
                "summary": data.get("summary"),
                "failure_reason": data.get("failure_reason"),
                "cost": Decimal(data["cost"]),
                "artifacts_produced": [
                    a.id
                    for a in self.state.artifacts.values()
                    if a.produced_in_shift == data["id"]
                ],
                "decisions_made": [
                    d.id
                    for d in self.state.decisions.values()
                    if d.made_in_shift == data["id"]
                ],
            }
        )

    def abort_running_shifts(self, reason: str) -> list[Shift]:
        """Called on startup. A shift that was RUNNING when we died is over.

        Saying so plainly beats a spinner that never resolves, and because the
        log is the source of truth, "nothing was lost" is literally true.
        """
        aborted: list[Shift] = []
        for shift in list(self.state.shifts.values()):
            if shift.status is ShiftStatus.RUNNING:
                aborted.append(
                    self.close_shift(
                        shift.id, status=ShiftStatus.ABORTED, failure_reason=reason
                    )
                )
        return aborted

    # ------------------------------------------------------------- progress
    def set_progress(self, progress: Progress) -> None:
        self._append("set_progress", {"progress": progress.model_dump(mode="json")})

    def _on_set_progress(self, data: dict, actor: str | None, at: str) -> None:
        self.state.progress = Progress.model_validate(data["progress"])

    # -------------------------------------------------------- integrations
    _MAX_LOGGED = 96
    """Nothing about a connection is long. A value that got in here by mistake
    almost certainly would be — so refuse it rather than trust the caller."""

    def record_integration(
        self,
        *,
        provider: str,
        event: str,
        fields: list[str],
        message: str = "",
        scope_note: str | None = None,
        actor: str | None = None,
    ) -> None:
        """What happened to a connection. Names and outcomes only.

        The vault holds the values; this holds the history. Keeping them apart
        is what makes "disconnect" mean something: a secret in an append-only
        log can never be deleted.
        """
        for text in (*fields, provider, event):
            if len(text) > self._MAX_LOGGED:
                raise ValueError(
                    "refusing to log an over-long value against an integration"
                )
        self._append(
            "record_integration",
            {
                "provider": provider,
                "event": event,
                "fields": list(fields),
                "message": message,
                "scope_note": scope_note,
            },
            actor,
        )

    def _on_record_integration(self, data: dict, actor: str | None, at: str) -> None:
        entry = self.state.integrations.setdefault(data["provider"], {})
        entry["event"] = data["event"]
        entry["fields"] = list(data.get("fields") or [])
        entry["message"] = data.get("message") or ""
        entry["scope_note"] = data.get("scope_note")
        entry["at"] = at
        if data["event"] == "connected":
            entry["connected_at"] = at
        if data["event"] in ("connected", "verified"):
            entry["verified_at"] = at
        if data["event"] == "disconnected":
            entry.pop("connected_at", None)
            entry.pop("verified_at", None)

    def record_resource(  # noqa: PLR0913
        self,
        *,
        provider: str,
        kind: str,
        ref: str,
        label: str,
        url: str | None = None,
        shift_id: str | None = None,
        actor: str | None = None,
    ) -> ProvisionedResource:
        """Something the team made that the founder now owns."""
        rid = _oid("rs")
        self._append(
            "record_resource",
            {
                "id": rid,
                "provider": provider,
                "kind": kind,
                "ref": ref,
                "label": label,
                "url": url,
                "shift_id": shift_id,
            },
            actor,
        )
        return self.state.resources[rid]

    def _on_record_resource(self, data: dict, actor: str | None, at: str) -> None:
        self.state.resources[data["id"]] = ProvisionedResource(
            id=data["id"],
            provider=data["provider"],
            kind=data["kind"],
            ref=data["ref"],
            label=data["label"],
            url=data.get("url"),
            created_in_shift=data.get("shift_id"),
            at=datetime.fromisoformat(at),
        )

    def record_metric(
        self, key: str, value: Any, *, role_id: str | None = None
    ) -> None:
        self._append("record_metric", {"key": key, "value": value}, role_id)

    def _on_record_metric(self, data: dict, actor: str | None, at: str) -> None:
        self.state.metrics[data["key"]] = data["value"]

    # --------------------------------------------------------------- money
    def record_cost(
        self,
        amount: Decimal,
        *,
        role_id: str | None,
        shift_id: str | None,
        note: str = "",
        kind: Literal["llm", "tool", "adjustment"] = "llm",
    ) -> LedgerEntry:
        entry_id = _oid("le")
        self._append(
            "record_cost",
            {
                "id": entry_id,
                "amount": str(amount.quantize(CENTS)),
                "shift_id": shift_id,
                "note": note,
                "kind": kind,
            },
            role_id,
        )
        return self.state.ledger[-1]

    def _on_record_cost(self, data: dict, actor: str | None, at: str) -> None:
        amount = Decimal(data["amount"])
        self.state.ledger.append(
            LedgerEntry(
                id=data["id"],
                company_id=self.company_id,
                shift_id=data.get("shift_id"),
                role_id=actor,
                amount=amount,
                kind=data.get("kind", "llm"),
                note=data.get("note", ""),
                at=datetime.fromisoformat(at),
            )
        )
        self.state.spent += amount

    # ----------------------------------------------------------- attention
    def ask(
        self, *, question: str, options: list[str], role_id: str, shift_id: str
    ) -> AttentionRequest:
        request_id = _oid("at")
        self._append(
            "ask",
            {
                "id": request_id,
                "question": question,
                "options": options,
                "shift_id": shift_id,
            },
            role_id,
        )
        return self.state.attention[request_id]

    def _on_ask(self, data: dict, actor: str | None, at: str) -> None:
        self.state.attention[data["id"]] = AttentionRequest(
            id=data["id"],
            company_id=self.company_id,
            shift_id=data["shift_id"],
            role_id=actor,
            question=data["question"],
            options=list(data.get("options", [])),
            asked_at=datetime.fromisoformat(at),
        )

    def answer(self, request_id: str, answer: str) -> AttentionRequest:
        if request_id not in self.state.attention:
            raise NotFound("We couldn't find that question.")
        self._append("answer", {"id": request_id, "answer": answer})
        return self.state.attention[request_id]

    def _on_answer(self, data: dict, actor: str | None, at: str) -> None:
        request = self.state.attention.get(data["id"])
        if request:
            self.state.attention[data["id"]] = request.model_copy(
                update={
                    "answer": data["answer"],
                    "answered_at": datetime.fromisoformat(at),
                }
            )

    def add_note(self, text: str) -> None:
        """The boss walks in. Read at the next shift's planning phase."""
        self._append("add_note", {"text": text})

    def _on_add_note(self, data: dict, actor: str | None, at: str) -> None:
        self.state.notes.append(data["text"])

    # ============================================================ projections
    def _write_projections(self) -> None:
        """Every file here is derivable. Losing them costs nothing but time."""
        self.paths.projections.mkdir(parents=True, exist_ok=True)
        state = self.state

        _atomic(
            self.paths.backlog,
            yaml.safe_dump(
                {
                    "open": [
                        {"id": t.id, "title": t.title, "priority": t.priority}
                        for t in sorted(state.open_tasks, key=lambda t: t.priority)
                    ],
                    "in_progress": [
                        {"id": t.id, "title": t.title, "owner": t.owner}
                        for t in state.tasks.values()
                        if t.status is TaskStatus.CLAIMED
                    ],
                    "done": [
                        {"id": t.id, "title": t.title}
                        for t in state.tasks.values()
                        if t.status is TaskStatus.DONE
                    ],
                },
                sort_keys=False,
                allow_unicode=True,
            ),
        )

        lines = ["# Decisions in force", ""]
        for decision in state.decisions.values():
            lines.append(f"## {decision.title}")
            lines.append("")
            lines.append(decision.rationale)
            if decision.alternatives_rejected:
                lines.append("")
                lines.append("Instead of:")
                lines.extend(f"- {alt}" for alt in decision.alternatives_rejected)
            if decision.contest_note:
                lines.append("")
                lines.append(
                    f"> Contested by {decision.contested_by}: "
                    f"{decision.contest_note}"
                )
            lines.append("")
        _atomic(self.paths.decisions_md, "\n".join(lines))

        _atomic(
            self.paths.metrics,
            json.dumps(
                {
                    "progress": state.progress.model_dump(mode="json"),
                    "spent": str(state.spent.quantize(CENTS)),
                    "shifts": len(state.shifts),
                    "open_tasks": len(state.open_tasks),
                    **state.metrics,
                },
                indent=2,
            ),
        )

        _atomic(
            self.paths.artifacts_index,
            json.dumps(
                [a.model_dump(mode="json") for a in state.artifacts.values()], indent=2
            ),
        )

    # ================================================================ reads
    def snapshot(self) -> CompanyBrain:
        return self.state


def _atomic(path: Path, text: str) -> None:
    """Write via a temp file and rename, so a reader never sees a half file."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
