"""Request-scoped dependencies.

The engine is held on ``app.state`` so swapping StubEngine for OpenHandsEngine is
a startup decision, not a code change anywhere in the routers.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, Request, WebSocket

from werkhaus.contract.engine import Engine


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_engine_ws(websocket: WebSocket) -> Engine:
    return websocket.app.state.engine


EngineDep = Annotated[Engine, Depends(get_engine)]


DEFAULT_ENGINE = "stub"
"""A server started with no configuration should demonstrate the product, not
present a front door whose only button returns an error. ``null`` stays
available for testing the API surface."""


def engine_kind() -> str:
    """The one reading of the environment. Both the engine and the dev routes
    ask this, because when they each read the variable themselves they drift,
    and a demo server quietly loses its demo controls."""
    return os.getenv("WERKHAUS_ENGINE", DEFAULT_ENGINE).lower()


def build_engine() -> Engine:
    """Choose the engine from the environment. One knob, one place."""
    kind = engine_kind()
    if kind == "null":
        from werkhaus.engines.null import NullEngine

        return NullEngine()
    if kind == "stub":
        from werkhaus.engines.stub.engine import StubEngine

        return StubEngine(
            root=os.getenv("WERKHAUS_DATA", "./data"),
            seed=int(os.getenv("WERKHAUS_STUB_SEED", "42")),
            scenario=os.getenv("WERKHAUS_STUB_SCENARIO", "happy"),
        )
    if kind == "openhands":
        from werkhaus.engines.openhands.engine import OpenHandsEngine

        return OpenHandsEngine(root=os.getenv("WERKHAUS_DATA", "./data"))
    raise ValueError(f"Unknown WERKHAUS_ENGINE={kind!r} (null|stub|openhands)")
