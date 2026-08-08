"""Request-scoped dependencies.

The engine is held on ``app.state``, so which engine is running stays a startup
decision rather than a code change anywhere in the routers.
"""

from __future__ import annotations

import logging
import os
from typing import Annotated

from fastapi import Depends, Request, WebSocket

from werkhaus.contract.engine import Engine

logger = logging.getLogger(__name__)


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_engine_ws(websocket: WebSocket) -> Engine:
    return websocket.app.state.engine


EngineDep = Annotated[Engine, Depends(get_engine)]


def build_engine() -> Engine:
    """There is one engine: real employees, real models.

    Werkhaus used to ship a stub that replayed scripted shifts. It was useful
    for building the interface without spending money, and it was also a
    machine for producing convincing fiction: a founder watching it saw a team
    reading pages nobody opened, about a business they had not described. A
    demo that cannot be told apart from the product is worse than no demo.

    Tests drive this same engine with the SDK's scripted model, so nothing is
    lost except the fiction.

    With no model configured the server still boots — and says so, rather than
    crashing on start or, worse, quietly inventing work.
    """
    root = os.getenv("WERKHAUS_DATA", "./data")
    if not os.getenv("WERKHAUS_MODEL"):
        from werkhaus.engines.null import NullEngine

        logger.warning(
            "WERKHAUS_MODEL is not set: the API will serve, but no company can "
            "be created until an employee has a brain to think with."
        )
        return NullEngine()

    from werkhaus.engines.openhands.engine import OpenHandsEngine

    return OpenHandsEngine(root=root)
