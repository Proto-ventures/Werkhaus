"""The engine contract.

``StubEngine`` and ``OpenHandsEngine`` both implement this, and the API layer
codes against nothing else. The REST surface in ``werkhaus.api.rest`` is derived
mechanically from these methods — that is the point.

Everything is async. Note that the SDK's ``LocalConversation.run()`` is
*synchronous* and its callbacks fire on the calling thread, so the real engine
drives it with ``asyncio.to_thread`` and marshals events back onto the loop with
``loop.call_soon_threadsafe``. None of that leaks past this interface.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Protocol, runtime_checkable

from werkhaus.contract.brains import BrainChoice
from werkhaus.contract.directory import McpConnection
from werkhaus.contract.events import ShiftEvent
from werkhaus.contract.integrations import (
    IntegrationState,
    ProvisionedResource,
    SpendPolicy,
)
from werkhaus.contract.models import (
    Artifact,
    ArtifactId,
    ArtifactKind,
    AttentionRequest,
    Budget,
    CharterPatch,
    Company,
    CompanyId,
    Decision,
    LedgerEntry,
    MoneyModel,
    Objection,
    PublicSnapshot,
    ShareLink,
    ShareOptions,
    Shift,
    ShiftId,
    Task,
    TaskStatus,
    VaultItem,
    WorkspaceFile,
)
from werkhaus.contract.plan import Allowance


@runtime_checkable
class Engine(Protocol):
    # ---------------------------------------------------------------- lifecycle
    async def start(self) -> None: ...

    async def aclose(self) -> None: ...

    # ---------------------------------------------------------------- companies
    async def create_company(
        self, idea: str, name: str | None = None
    ) -> Company: ...

    async def get_company(self, cid: CompanyId) -> Company: ...

    async def list_companies(self) -> list[Company]: ...

    async def update_charter(self, cid: CompanyId, patch: CharterPatch) -> Company: ...

    async def archive_company(self, cid: CompanyId) -> None: ...

    # ------------------------------------------------------------------- shifts
    async def start_shift(self, cid: CompanyId, focus: str | None = None) -> Shift: ...

    async def get_shift(self, sid: ShiftId) -> Shift: ...

    async def list_shifts(
        self, cid: CompanyId, limit: int = 50, before: int | None = None
    ) -> list[Shift]: ...

    async def stop_shift(self, sid: ShiftId, reason: str = "user") -> Shift: ...

    # -------------------------------------------------------------- read models
    async def list_tasks(
        self, cid: CompanyId, status: TaskStatus | None = None
    ) -> list[Task]: ...

    async def list_artifacts(
        self, cid: CompanyId, kind: ArtifactKind | None = None
    ) -> list[Artifact]: ...

    async def get_artifact(self, aid: ArtifactId) -> Artifact: ...

    async def read_artifact(self, aid: ArtifactId) -> tuple[bytes, str]:
        """Return ``(content, mime)``. Resolves id -> path through the artifact
        index with a containment check; no user-supplied path reaches the disk."""
        ...

    async def list_decisions(self, cid: CompanyId) -> list[Decision]: ...

    async def list_objections(self, cid: CompanyId) -> list[Objection]:
        """The critic's findings. Rendered at the same weight as the artifacts."""
        ...

    async def list_attention(self, cid: CompanyId) -> list[AttentionRequest]:
        """Open and answered questions. A blocked company must never look idle."""
        ...

    async def list_ledger(
        self, cid: CompanyId, limit: int = 200
    ) -> list[LedgerEntry]: ...

    async def get_money_model(self, cid: CompanyId) -> MoneyModel | None:
        """What the business would earn, as the assumptions it rests on.

        None until somebody has modelled it. Deliberately not an empty model:
        "nobody has done this yet" and "we modelled it and it comes to nothing"
        are different facts, and a founder has to be able to tell them apart.
        """
        ...

    # --------------------------------------------------------------- user input
    async def answer_attention(
        self, cid: CompanyId, request_id: str, answer: str
    ) -> None: ...

    async def send_note(self, cid: CompanyId, text: str) -> None:
        """The boss walks in. Queued for the next shift's planning phase."""
        ...

    # --------------------------------------------------------------------- plan
    async def get_allowance(self) -> Allowance:
        """What the plan allows, counted from the work actually done.

        Account-wide, never per company: an allowance that resets per company
        is an allowance you refill by pressing "new company"."""
        ...

    # -------------------------------------------------------------- connections
    async def list_integrations(self, cid: CompanyId) -> list[IntegrationState]:
        """Every service in the catalog with this company's connection state.
        Always all six: a card the founder can't use yet still explains what it
        would unlock."""
        ...

    async def connect_integration(
        self, cid: CompanyId, provider: str, values: dict[str, str]
    ) -> IntegrationState:
        """Check the credential with the provider, then store it. A value that
        fails verification is never written anywhere."""
        ...

    async def verify_integration(
        self, cid: CompanyId, provider: str
    ) -> IntegrationState: ...

    async def disconnect_integration(self, cid: CompanyId, provider: str) -> None: ...

    async def list_resources(self, cid: CompanyId) -> list[ProvisionedResource]:
        """What the team has built that the founder now owns."""
        ...

    async def list_mcp(self, cid: CompanyId) -> list[McpConnection]:
        """Servers this company has been connected to by hand."""
        ...

    async def add_mcp(  # noqa: PLR0913
        self,
        cid: CompanyId,
        name: str,
        label: str,
        transport: str = "stdio",
        url: str | None = None,
        command: str | None = None,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        directory_url: str | None = None,
    ) -> McpConnection:
        ...

    async def remove_mcp(self, cid: CompanyId, name: str) -> None:
        ...

    async def get_brain(self, cid: CompanyId) -> BrainChoice:
        """What the employees think with. Never returns the key."""
        ...

    async def set_brain(
        self,
        cid: CompanyId,
        provider: str,
        model: str,
        key: str,
        base_url: str | None = None,
    ) -> BrainChoice: ...

    async def get_spend_policy(self, cid: CompanyId) -> SpendPolicy: ...

    async def set_spend_policy(
        self, cid: CompanyId, policy: SpendPolicy
    ) -> SpendPolicy: ...

    # ------------------------------------------------------------------ control
    async def set_budget_cap(self, cid: CompanyId, cap: Decimal) -> Budget: ...

    async def halt(self, cid: CompanyId) -> Company:
        """The kill switch. Must complete in under two seconds: interrupt every
        live conversation, cancel the shift task, commit partial artifacts.

        On the protocol from day 1 — retrofitting a kill switch through a UI is
        miserable, and the ability to stop your company is a trust feature."""
        ...

    async def resume(self, cid: CompanyId) -> Company: ...

    # -------------------------------------------------------------------- vault
    async def list_vault(self, cid: CompanyId) -> list[VaultItem]:
        """Names and hints only. There is no engine method that returns a
        stored value — the team reads the vault, the user never does again."""
        ...

    async def set_vault(self, cid: CompanyId, name: str, value: str) -> VaultItem: ...

    async def delete_vault(self, cid: CompanyId, name: str) -> None: ...

    # ---------------------------------------------------------------- workspace
    async def list_files(self, cid: CompanyId) -> list[WorkspaceFile]:
        """Everything under ``workspace/``, the only directory a user can see.
        ``_state``, notes and conversations are never enumerated."""
        ...

    async def read_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        """Return ``(content, mime)`` for one workspace file, with a containment
        check. No user-supplied path escapes ``workspace/``."""
        ...

    async def read_site_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        """Serve the built site under ``workspace/site/`` — what the preview
        iframe loads. Empty path means ``index.html``."""
        ...

    # ------------------------------------------------------------------ sharing
    async def publish(self, cid: CompanyId, opts: ShareOptions) -> ShareLink: ...

    async def unpublish(self, cid: CompanyId) -> None: ...

    async def get_public_snapshot(self, token: str) -> PublicSnapshot: ...

    # ---------------------------------------------------------------- streaming
    def stream(
        self, cid: CompanyId, since_seq: int | None = None
    ) -> AsyncIterator[ShiftEvent]:
        """Live events, resuming after ``since_seq``.

        Subscribers get a bounded queue; a slow one is dropped rather than allowed
        to block the bus, and reconnects with its last seq."""
        ...

    async def replay(
        self, cid: CompanyId, since_seq: int, limit: int = 500
    ) -> list[ShiftEvent]:
        """Durable history, for gaps beyond the in-memory ring buffer and for
        cold loads with no live socket."""
        ...
