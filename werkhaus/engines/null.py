"""An engine that does nothing, correctly.

Exists so the API layer, the WS handler and the type generation can be built and
verified before StubEngine lands. It is also the honest floor for the contract
tests: every method that must exist, exists.
"""

from __future__ import annotations

import asyncio
import itertools
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

from werkhaus.contract.engine import Engine
from werkhaus.contract.errors import (
    CompanyNotFound,
    EngineNotConfigured,
    ShiftNotFound,
)
from werkhaus.contract.events import ShiftEvent, ShiftEventKind
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
from werkhaus.contract.plan import Allowance, build_allowance, current_plan

HEARTBEAT_SECONDS = 20


class NullEngine(Engine):
    """Empty everywhere. Streams nothing but heartbeats."""

    def __init__(self) -> None:
        self._seq = itertools.count(1)

    async def start(self) -> None:
        return None

    async def aclose(self) -> None:
        return None

    # ---------------------------------------------------------------- companies
    async def create_company(self, idea: str, name: str | None = None) -> Company:
        # A bare exception here surfaces as "Something went wrong on our side."
        # on the one button the front door has, which is how a misconfigured
        # server looks identical to a broken product.
        raise EngineNotConfigured()

    async def get_company(self, cid: CompanyId) -> Company:
        raise CompanyNotFound()

    async def get_allowance(self) -> Allowance:
        return build_allowance(current_plan(), None, used=0)

    async def list_companies(self) -> list[Company]:
        return []

    async def update_charter(self, cid: CompanyId, patch: CharterPatch) -> Company:
        raise CompanyNotFound()

    async def archive_company(self, cid: CompanyId) -> None:
        raise CompanyNotFound()

    # ------------------------------------------------------------------- shifts
    async def start_shift(self, cid: CompanyId, focus: str | None = None) -> Shift:
        raise CompanyNotFound()

    async def get_shift(self, sid: ShiftId) -> Shift:
        raise ShiftNotFound()

    async def list_shifts(
        self, cid: CompanyId, limit: int = 50, before: int | None = None
    ) -> list[Shift]:
        return []

    async def stop_shift(self, sid: ShiftId, reason: str = "user") -> Shift:
        raise ShiftNotFound()

    # -------------------------------------------------------------- read models
    async def list_tasks(
        self, cid: CompanyId, status: TaskStatus | None = None
    ) -> list[Task]:
        return []

    async def list_artifacts(
        self, cid: CompanyId, kind: ArtifactKind | None = None
    ) -> list[Artifact]:
        return []

    async def get_artifact(self, aid: ArtifactId) -> Artifact:
        from werkhaus.contract.errors import ArtifactNotFound

        raise ArtifactNotFound()

    async def read_artifact(self, aid: ArtifactId) -> tuple[bytes, str]:
        from werkhaus.contract.errors import ArtifactNotFound

        raise ArtifactNotFound()

    async def list_decisions(self, cid: CompanyId) -> list[Decision]:
        return []

    async def list_objections(self, cid: CompanyId) -> list[Objection]:
        return []

    async def list_attention(self, cid: CompanyId) -> list[AttentionRequest]:
        return []

    async def list_ledger(
        self, cid: CompanyId, limit: int = 200
    ) -> list[LedgerEntry]:
        return []

    # --------------------------------------------------------------- user input
    async def answer_attention(
        self, cid: CompanyId, request_id: str, answer: str
    ) -> None:
        raise CompanyNotFound()

    async def send_note(self, cid: CompanyId, text: str) -> None:
        raise CompanyNotFound()

    # ------------------------------------------------------------------ control
    async def set_budget_cap(self, cid: CompanyId, cap: Decimal) -> Budget:
        raise CompanyNotFound()

    async def halt(self, cid: CompanyId) -> Company:
        raise CompanyNotFound()

    async def resume(self, cid: CompanyId) -> Company:
        raise CompanyNotFound()

    # -------------------------------------------------------------- connections
    async def list_integrations(self, cid: CompanyId) -> list[IntegrationState]:
        raise CompanyNotFound()

    async def connect_integration(
        self, cid: CompanyId, provider: str, values: dict[str, str]
    ) -> IntegrationState:
        raise CompanyNotFound()

    async def verify_integration(
        self, cid: CompanyId, provider: str
    ) -> IntegrationState:
        raise CompanyNotFound()

    async def disconnect_integration(self, cid: CompanyId, provider: str) -> None:
        raise CompanyNotFound()

    async def list_resources(self, cid: CompanyId) -> list[ProvisionedResource]:
        raise CompanyNotFound()

    async def get_spend_policy(self, cid: CompanyId) -> SpendPolicy:
        raise CompanyNotFound()

    async def set_spend_policy(
        self, cid: CompanyId, policy: SpendPolicy
    ) -> SpendPolicy:
        raise CompanyNotFound()

    # -------------------------------------------------------------------- vault
    async def list_vault(self, cid: CompanyId) -> list[VaultItem]:
        raise CompanyNotFound()

    async def set_vault(self, cid: CompanyId, name: str, value: str) -> VaultItem:
        raise CompanyNotFound()

    async def delete_vault(self, cid: CompanyId, name: str) -> None:
        raise CompanyNotFound()

    # ---------------------------------------------------------------- workspace
    async def list_files(self, cid: CompanyId) -> list[WorkspaceFile]:
        raise CompanyNotFound()

    async def read_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        raise CompanyNotFound()

    async def read_site_file(self, cid: CompanyId, path: str) -> tuple[bytes, str]:
        raise CompanyNotFound()

    # ------------------------------------------------------------------ sharing
    async def publish(self, cid: CompanyId, opts: ShareOptions) -> ShareLink:
        raise CompanyNotFound()

    async def unpublish(self, cid: CompanyId) -> None:
        raise CompanyNotFound()

    async def get_public_snapshot(self, token: str) -> PublicSnapshot:
        from werkhaus.contract.errors import NotFound

        raise NotFound("That share link isn't available.")

    # ---------------------------------------------------------------- streaming
    async def stream(
        self, cid: CompanyId, since_seq: int | None = None
    ) -> AsyncIterator[ShiftEvent]:
        while True:
            yield ShiftEvent(
                seq=next(self._seq),
                id=f"ev_null_{cid}",
                company_id=cid,
                kind=ShiftEventKind.HEARTBEAT,
                at=datetime.now(UTC),
                text="",
            )
            await asyncio.sleep(HEARTBEAT_SECONDS)

    async def replay(
        self, cid: CompanyId, since_seq: int, limit: int = 500
    ) -> list[ShiftEvent]:
        return []
