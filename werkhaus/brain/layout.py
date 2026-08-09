"""The on-disk shape of a company.

Split by *mutability*, not by format. Anything an employee may edit freehand
lives where a lost update costs nothing; anything the company reasons over lives
under ``_state/`` and is only ever written through :class:`BrainStore`.

That split is not fastidiousness. The SDK's ``ResourceLockManager`` is
per-conversation, so two employees editing the same file from two conversations
have no lock at all — and an LLM doing ``str_replace`` on YAML produces
syntactically valid YAML with silently wrong semantics far more often than it
produces a parse error. There is no exception to catch.
"""

from __future__ import annotations

from pathlib import Path


class CompanyPaths:
    """Every path in a company, in one place."""

    def __init__(self, root: Path | str) -> None:
        # Absolute, always. The file editor an employee holds refuses relative
        # paths and tells her the workspace by echoing this one back to her —
        # so a relative root here reads as "your workspace is
        # data/co_x/workspace", she prepends a slash to satisfy the tool, and
        # every write lands on a directory that does not exist. A whole shift
        # was lost to that once.
        self.root = Path(root).expanduser().resolve()

    # -- agent-visible -------------------------------------------------------
    @property
    def charter(self) -> Path:
        return self.root / "charter.md"

    @property
    def brief(self) -> Path:
        return self.root / "brief.md"

    @property
    def notes(self) -> Path:
        """Free-form, namespaced per role so two employees never collide."""
        return self.root / "notes"

    def role_notes(self, role_id: str) -> Path:
        return self.notes / role_id

    @property
    def artifacts(self) -> Path:
        return self.root / "artifacts"

    @property
    def workspace(self) -> Path:
        """The agent CWD. Deliberately *not* the company root."""
        return self.root / "workspace"

    @property
    def shifts(self) -> Path:
        return self.root / "shifts"

    @property
    def conversations(self) -> Path:
        return self.root / "conversations"

    # -- engine-only ---------------------------------------------------------
    @property
    def state(self) -> Path:
        """Outside ``workspace/``, so a relative file_editor path cannot reach it.

        Not a security boundary — the terminal tool can see the whole filesystem
        — but it removes the accidental-corruption path entirely.
        """
        return self.root / "_state"

    @property
    def log(self) -> Path:
        """The source of truth. Append-only."""
        return self.state / "log.jsonl"

    @property
    def lock(self) -> Path:
        return self.state / ".lock"

    @property
    def events(self) -> Path:
        return self.state / "events.jsonl"

    @property
    def projections(self) -> Path:
        """Pure functions of the log. Deleting them loses nothing."""
        return self.state / "projections"

    @property
    def backlog(self) -> Path:
        return self.projections / "backlog.yaml"

    @property
    def decisions_md(self) -> Path:
        return self.projections / "decisions.md"

    @property
    def metrics(self) -> Path:
        return self.projections / "metrics.json"

    @property
    def artifacts_index(self) -> Path:
        return self.projections / "artifacts.json"

    @property
    def digest(self) -> Path:
        return self.projections / "digest.md"

    def shift_json(self, number: int) -> Path:
        return self.shifts / f"{number:04d}.json"

    def shift_md(self, number: int) -> Path:
        return self.shifts / f"{number:04d}.md"

    def ensure(self) -> None:
        for path in (
            self.root,
            self.notes,
            self.artifacts,
            self.workspace,
            self.shifts,
            self.state,
            self.projections,
        ):
            path.mkdir(parents=True, exist_ok=True)
        # The engine's own area is not for other users to read.
        self.state.chmod(0o700)
