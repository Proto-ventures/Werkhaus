"""The live socket.

Deliberately trivial and identical for every engine: ``engine.stream()`` is the
entire streaming contract, so this handler never learns what an SDK event is.

The client stores the last ``seq`` it saw and reconnects with ``?since_seq=N``.
That, plus ``GET /companies/{cid}/events``, means a dropped socket is a cosmetic
event rather than lost history.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from werkhaus.api.deps import get_engine_ws

logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/companies/{cid}")
async def company_socket(
    websocket: WebSocket,
    cid: str,
    since_seq: int | None = Query(None, ge=0),
) -> None:
    await websocket.accept()
    engine = get_engine_ws(websocket)
    try:
        async for event in engine.stream(cid, since_seq=since_seq):
            await websocket.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    except Exception:
        # Never leak the reason to the client; it is not something a user can act on.
        logger.exception("company socket failed for %s", cid)
        try:
            await websocket.close(code=1011)
        except RuntimeError:
            pass
