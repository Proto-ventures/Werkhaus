"""The Werkhaus API application.

Depends on ``werkhaus.contract`` and nothing else product-shaped. No import of
``openhands.*`` may appear anywhere under ``werkhaus/api`` — enforced by
tests/contract/test_no_sdk_imports.py.
"""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from werkhaus.api import rest, ws
from werkhaus.api.deps import build_engine
from werkhaus.contract.engine import Engine
from werkhaus.contract.errors import WerkhausError

logger = logging.getLogger(__name__)

# The SDK prints an ASCII banner advertising OpenHands on import. In a
# proprietary product's logs that is noise at best. Set before anything can
# import openhands.*, which for the openhands engine happens during startup.
os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")


def _error_body(
    code: str, message: str, hint: str | None, request_id: str
) -> dict[str, dict[str, str | None]]:
    return {
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
            "request_id": request_id,
        }
    }


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = getattr(app.state, "prepared_engine", None) or build_engine()
    app.state.engine = engine
    await engine.start()
    logger.info("engine ready: %s", type(engine).__name__)
    try:
        yield
    finally:
        await engine.aclose()


def create_app(engine: Engine | None = None) -> FastAPI:
    """The app. Pass an ``engine`` to run against a prepared one.

    That seam exists for the tests: they drive the real engine with a scripted
    model, which needs constructing rather than selecting from the environment.
    """
    app = FastAPI(
        title="Werkhaus",
        version="0.1.0",
        lifespan=lifespan,
        # The OpenAPI schema is the source of the frontend's TS types, so it is
        # part of the contract, not a debugging convenience.
        openapi_url="/openapi.json",
    )

    if engine is not None:
        app.state.prepared_engine = engine

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request.state.request_id = f"req_{secrets.token_hex(4)}"
        response = await call_next(request)
        response.headers["X-Request-Id"] = request.state.request_id
        return response

    @app.exception_handler(WerkhausError)
    async def handle_werkhaus_error(
        request: Request, exc: WerkhausError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "req_unknown")
        logger.info("%s %s: %s", request_id, exc.code, exc.message)
        return JSONResponse(
            status_code=exc.status,
            content=_error_body(exc.code, exc.message, exc.hint, request_id),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """FastAPI's default 422 body is a list of internal field paths.

        That is a different shape from every other error we emit and it leaks
        parameter names at the user. One envelope, everywhere."""
        request_id = getattr(request.state, "request_id", "req_unknown")
        logger.info("%s invalid request: %s", request_id, exc.errors())
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "invalid_request",
                "That request didn't look right.",
                "Check the values you sent and try again.",
                request_id,
            ),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        """The traceback is logged against the request id and never serialized.

        The user is non-technical; a stack trace is not something they can act on,
        and it is a reliable way to leak absolute paths."""
        request_id = getattr(request.state, "request_id", "req_unknown")
        logger.exception("%s unhandled error", request_id)
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "internal",
                "Something went wrong on our side.",
                "Try again in a moment. If it keeps happening, tell us this code: "
                + request_id,
                request_id,
            ),
        )

    app.include_router(rest.router)
    app.include_router(rest.public_router)
    app.include_router(ws.router)
    @app.get("/healthz", include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "engine": type(app.state.engine).__name__}

    _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Serve the built SPA when it exists (hosted); do nothing in dev.

    In dev the frontend runs on Vite with a proxy to this server, so there is no
    build to mount and no build-time backend URL anywhere.
    """
    default = Path(__file__).parent.parent.parent / "web" / "dist"
    dist = Path(os.getenv("WERKHAUS_STATIC", default))
    if not dist.is_dir():
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> Response:
        """Serve the app for any non-API path.

        `StaticFiles(html=True)` alone 404s on client-side routes, so refreshing
        on /c/{id} — the URL a user is most likely to bookmark or share — breaks.
        Real files win; everything else falls through to the app, which reads the
        path itself.
        """
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(index)

    logger.info("serving SPA from %s", dist)


app = create_app()
