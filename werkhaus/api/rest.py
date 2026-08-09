"""REST surface, mechanically derived from the Engine protocol.

Two routers: the authenticated app API under ``/api/v1``, and a separate
unauthenticated public router for share links. They are separate objects on
purpose — the public router must have no code path that can read a company
directory (see the share design: snapshots only, allowlist not denylist).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field

from werkhaus.api.deps import EngineDep
from werkhaus.contract.brains import BRAINS, BrainChoice, BrainProvider
from werkhaus.contract.catalog import CATALOG
from werkhaus.contract.events import ShiftEvent
from werkhaus.contract.integrations import (
    IntegrationSpec,
    IntegrationState,
    ProvisionedResource,
    SpendPolicy,
)
from werkhaus.contract.models import (
    Artifact,
    ArtifactKind,
    AttentionRequest,
    Budget,
    CharterPatch,
    Company,
    Decision,
    LedgerEntry,
    Objection,
    PublicSnapshot,
    ShareLink,
    ShareOptions,
    Shift,
    Task,
    TaskStatus,
    VaultItem,
    WorkspaceFile,
)
from werkhaus.contract.plan import Allowance

router = APIRouter(prefix="/api/v1", tags=["werkhaus"])
public_router = APIRouter(prefix="/public", tags=["public"])


# ------------------------------------------------------------------ request bodies
class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateCompanyBody(_Body):
    idea: str = Field(min_length=1, max_length=4000)
    name: str | None = None


class StartShiftBody(_Body):
    focus: str | None = None


class StopShiftBody(_Body):
    reason: str = "user"


class AnswerBody(_Body):
    answer: str = Field(min_length=1)


class NoteBody(_Body):
    text: str = Field(min_length=1, max_length=4000)


class BudgetBody(_Body):
    cap: Decimal = Field(ge=0)


class VaultValueBody(_Body):
    value: str = Field(min_length=1, max_length=8000)


# --------------------------------------------------------------------------- health
@router.get("/health")
async def health(engine: EngineDep) -> dict[str, object]:
    """What this server is, in enough detail to explain "nothing is working".

    Deliberately no filesystem path: the data directory is an absolute home
    path, which is a finding everywhere else in this codebase.
    """
    return {
        "engine": type(engine).__name__.replace("Engine", "").lower(),
        "companies": len(await engine.list_companies()),
        "plan": (await engine.get_allowance()).plan,
    }


# ----------------------------------------------------------------------------- plan
@router.get("/allowance", response_model=Allowance)
async def get_allowance(engine: EngineDep) -> Allowance:
    return await engine.get_allowance()


# -------------------------------------------------------------------- connections
class ConnectBody(_Body):
    values: dict[str, str] = Field(min_length=1)


@router.get("/integrations/catalog", response_model=list[IntegrationSpec])
async def integration_catalog() -> list[IntegrationSpec]:
    """Company-independent, so the marketing site can render it too."""
    return list(CATALOG)


@router.get(
    "/companies/{cid}/integrations", response_model=list[IntegrationState]
)
async def list_integrations(cid: str, engine: EngineDep) -> list[IntegrationState]:
    return await engine.list_integrations(cid)


@router.post(
    "/companies/{cid}/integrations/{provider}", response_model=IntegrationState
)
async def connect_integration(
    cid: str, provider: str, body: ConnectBody, engine: EngineDep
) -> IntegrationState:
    return await engine.connect_integration(cid, provider, body.values)


@router.post(
    "/companies/{cid}/integrations/{provider}/verify",
    response_model=IntegrationState,
)
async def verify_integration(
    cid: str, provider: str, engine: EngineDep
) -> IntegrationState:
    return await engine.verify_integration(cid, provider)


@router.delete(
    "/companies/{cid}/integrations/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def disconnect_integration(
    cid: str, provider: str, engine: EngineDep
) -> Response:
    await engine.disconnect_integration(cid, provider)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/companies/{cid}/resources", response_model=list[ProvisionedResource])
async def list_resources(cid: str, engine: EngineDep) -> list[ProvisionedResource]:
    return await engine.list_resources(cid)


class BrainBody(_Body):
    provider: str
    model: str = Field(min_length=1, max_length=200)
    key: str = Field(min_length=1, max_length=8000)
    base_url: str | None = None


@router.get("/brains", response_model=list[BrainProvider])
async def list_brains() -> list[BrainProvider]:
    """The providers we know, and the models known to work a shift."""
    return list(BRAINS)


@router.get("/companies/{cid}/brain", response_model=BrainChoice)
async def get_brain(cid: str, engine: EngineDep) -> BrainChoice:
    return await engine.get_brain(cid)


@router.put("/companies/{cid}/brain", response_model=BrainChoice)
async def set_brain(cid: str, body: BrainBody, engine: EngineDep) -> BrainChoice:
    return await engine.set_brain(
        cid, body.provider, body.model, body.key, body.base_url
    )


@router.get("/companies/{cid}/spend-policy", response_model=SpendPolicy)
async def get_spend_policy(cid: str, engine: EngineDep) -> SpendPolicy:
    return await engine.get_spend_policy(cid)


@router.put("/companies/{cid}/spend-policy", response_model=SpendPolicy)
async def set_spend_policy(
    cid: str, policy: SpendPolicy, engine: EngineDep
) -> SpendPolicy:
    return await engine.set_spend_policy(cid, policy)


# ------------------------------------------------------------------------ companies
@router.post("/companies", response_model=Company, status_code=status.HTTP_201_CREATED)
async def create_company(body: CreateCompanyBody, engine: EngineDep) -> Company:
    return await engine.create_company(body.idea, body.name)


@router.get("/companies", response_model=list[Company])
async def list_companies(engine: EngineDep) -> list[Company]:
    return await engine.list_companies()


@router.get("/companies/{cid}", response_model=Company)
async def get_company(cid: str, engine: EngineDep) -> Company:
    return await engine.get_company(cid)


@router.patch("/companies/{cid}/charter", response_model=Company)
async def update_charter(cid: str, patch: CharterPatch, engine: EngineDep) -> Company:
    return await engine.update_charter(cid, patch)


@router.delete("/companies/{cid}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_company(cid: str, engine: EngineDep) -> Response:
    await engine.archive_company(cid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- shifts
@router.post(
    "/companies/{cid}/shifts",
    response_model=Shift,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_shift(cid: str, body: StartShiftBody, engine: EngineDep) -> Shift:
    return await engine.start_shift(cid, body.focus)


@router.get("/companies/{cid}/shifts", response_model=list[Shift])
async def list_shifts(
    cid: str,
    engine: EngineDep,
    limit: int = Query(50, ge=1, le=200),
    before: int | None = None,
) -> list[Shift]:
    return await engine.list_shifts(cid, limit=limit, before=before)


@router.get("/shifts/{sid:path}", response_model=Shift)
async def get_shift(sid: str, engine: EngineDep) -> Shift:
    return await engine.get_shift(sid)


@router.post("/shifts/{sid:path}/stop", response_model=Shift)
async def stop_shift(sid: str, body: StopShiftBody, engine: EngineDep) -> Shift:
    return await engine.stop_shift(sid, body.reason)


# ---------------------------------------------------------------------- read models
@router.get("/companies/{cid}/tasks", response_model=list[Task])
async def list_tasks(
    cid: str, engine: EngineDep, task_status: TaskStatus | None = None
) -> list[Task]:
    return await engine.list_tasks(cid, task_status)


@router.get("/companies/{cid}/artifacts", response_model=list[Artifact])
async def list_artifacts(
    cid: str, engine: EngineDep, kind: ArtifactKind | None = None
) -> list[Artifact]:
    return await engine.list_artifacts(cid, kind)


@router.get("/artifacts/{aid}", response_model=Artifact)
async def get_artifact(aid: str, engine: EngineDep) -> Artifact:
    return await engine.get_artifact(aid)


@router.get("/artifacts/{aid}/content")
async def read_artifact(aid: str, engine: EngineDep) -> Response:
    content, mime = await engine.read_artifact(aid)
    return Response(content=content, media_type=mime)


@router.get("/companies/{cid}/decisions", response_model=list[Decision])
async def list_decisions(cid: str, engine: EngineDep) -> list[Decision]:
    return await engine.list_decisions(cid)


@router.get("/companies/{cid}/objections", response_model=list[Objection])
async def list_objections(cid: str, engine: EngineDep) -> list[Objection]:
    return await engine.list_objections(cid)


@router.get("/companies/{cid}/attention", response_model=list[AttentionRequest])
async def list_attention(cid: str, engine: EngineDep) -> list[AttentionRequest]:
    return await engine.list_attention(cid)


@router.get("/companies/{cid}/ledger", response_model=list[LedgerEntry])
async def list_ledger(
    cid: str, engine: EngineDep, limit: int = Query(200, ge=1, le=1000)
) -> list[LedgerEntry]:
    return await engine.list_ledger(cid, limit=limit)


# ----------------------------------------------------------------------- user input
@router.post(
    "/companies/{cid}/attention/{request_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def answer_attention(
    cid: str, request_id: str, body: AnswerBody, engine: EngineDep
) -> Response:
    await engine.answer_attention(cid, request_id, body.answer)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/companies/{cid}/notes", status_code=status.HTTP_204_NO_CONTENT)
async def send_note(cid: str, body: NoteBody, engine: EngineDep) -> Response:
    await engine.send_note(cid, body.text)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------------- control
@router.put("/companies/{cid}/budget", response_model=Budget)
async def set_budget_cap(cid: str, body: BudgetBody, engine: EngineDep) -> Budget:
    return await engine.set_budget_cap(cid, body.cap)


@router.post("/companies/{cid}/halt", response_model=Company)
async def halt(cid: str, engine: EngineDep) -> Company:
    """The kill switch. Big red button in the UI, not buried in settings."""
    return await engine.halt(cid)


@router.post("/companies/{cid}/resume", response_model=Company)
async def resume(cid: str, engine: EngineDep) -> Company:
    return await engine.resume(cid)


# ---------------------------------------------------------------------------- vault
@router.get("/companies/{cid}/vault", response_model=list[VaultItem])
async def list_vault(cid: str, engine: EngineDep) -> list[VaultItem]:
    return await engine.list_vault(cid)


@router.put("/companies/{cid}/vault/{name}", response_model=VaultItem)
async def set_vault(
    cid: str, name: str, body: VaultValueBody, engine: EngineDep
) -> VaultItem:
    """Write-only from the user's side: the value goes in once and is never
    echoed back by any endpoint."""
    return await engine.set_vault(cid, name, body.value)


@router.delete(
    "/companies/{cid}/vault/{name}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_vault(cid: str, name: str, engine: EngineDep) -> Response:
    await engine.delete_vault(cid, name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------------ workspace
@router.get("/companies/{cid}/files", response_model=list[WorkspaceFile])
async def list_files(cid: str, engine: EngineDep) -> list[WorkspaceFile]:
    return await engine.list_files(cid)


@router.get("/companies/{cid}/files/content")
async def read_file(
    cid: str, engine: EngineDep, path: str = Query(min_length=1, max_length=500)
) -> Response:
    content, mime = await engine.read_file(cid, path)
    return Response(content=content, media_type=mime)


@router.get("/companies/{cid}/site/{path:path}")
async def read_site_file(cid: str, path: str, engine: EngineDep) -> Response:
    """The preview the Website tab iframes. Serves only ``workspace/site/``."""
    content, mime = await engine.read_site_file(cid, path)
    return Response(content=content, media_type=mime)


# -------------------------------------------------------------------------- sharing
@router.post("/companies/{cid}/share", response_model=ShareLink)
async def publish(cid: str, opts: ShareOptions, engine: EngineDep) -> ShareLink:
    return await engine.publish(cid, opts)


@router.delete("/companies/{cid}/share", status_code=status.HTTP_204_NO_CONTENT)
async def unpublish(cid: str, engine: EngineDep) -> Response:
    await engine.unpublish(cid)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- events
@router.get("/companies/{cid}/events", response_model=list[ShiftEvent])
async def list_events(
    cid: str,
    engine: EngineDep,
    since_seq: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
) -> list[ShiftEvent]:
    """Cold-load path. A shift must be fully reconstructible from REST alone,
    with no live socket — that is what makes "leave and come back" work."""
    return await engine.replay(cid, since_seq, limit)


# --------------------------------------------------------------------- public share
@public_router.get("/{token}", response_model=PublicSnapshot)
async def public_snapshot(token: str, engine: EngineDep) -> PublicSnapshot:
    return await engine.get_public_snapshot(token)
