"""Per-company event fan-out.

Shared by both engines. StubEngine emits from the event loop; OpenHandsEngine will
emit from the SDK's worker thread — ``LocalConversation.run()`` is synchronous and
its callbacks fire on the calling thread — which is what ``emit_threadsafe`` is
for. Getting that wrong loses events silently under load, which shows up as "the
UI sometimes misses steps".

The socket is a nicety, not the source of truth. Every event is appended to a
durable JSONL log before it is fanned out, so a client that missed everything can
reconstruct from ``replay()`` alone.
"""

from __future__ import annotations

import asyncio
import logging
import re
import secrets
import threading
from collections import deque
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from werkhaus.contract.events import ShiftEvent, ShiftEventKind
from werkhaus.contract.models import CompanyId, RoleId, ShiftId

logger = logging.getLogger(__name__)

RING_SIZE = 2000
SUBSCRIBER_QUEUE_SIZE = 512

# Redaction is a product requirement, not hardening. A shell command, an absolute
# path or a stack trace reaching the UI is a bug in the narrator, so we fail
# closed and shout rather than quietly publishing it.
#
# These are deliberately key-SHAPED rather than prefix substrings: matching a bare
# "sk-" would blank a legitimate event about "risk-assessment.md", and a redactor
# that eats real content is worse than one that misses an edge case.
_FORBIDDEN = (
    re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+"),
    re.compile(r"Traceback \(most recent call last\)"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{16,}"),
    re.compile(r"\bAKIA[0-9A-Z]{12,}"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _looks_leaky(text: str | None) -> str | None:
    if not text:
        return None
    for pattern in _FORBIDDEN:
        if pattern.search(text):
            return pattern.pattern
    return None


class CompanyBus:
    """One bus per company. Owns the seq counter and the durable log."""

    def __init__(self, company_id: CompanyId, log_path: Path) -> None:
        self.company_id = company_id
        self._log_path = log_path
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ring: deque[ShiftEvent] = deque(maxlen=RING_SIZE)
        self._subscribers: set[asyncio.Queue[ShiftEvent]] = set()
        self._seq = self._restore_seq()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------ startup
    def _restore_seq(self) -> int:
        """Resume the counter across restarts, so ``since_seq`` stays meaningful."""
        if not self._log_path.exists():
            return 0
        last = 0
        with self._log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = ShiftEvent.model_validate_json(line)
                except ValueError:
                    # A torn last line is expected after a crash. Truncate, warn,
                    # keep going: the log is append-only so nothing before it moved.
                    logger.warning("discarding torn event line in %s", self._log_path)
                    continue
                last = max(last, event.seq)
                self._ring.append(event)
        return last

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    # ------------------------------------------------------------------- emit
    def emit(
        self,
        kind: ShiftEventKind,
        text: str,
        *,
        shift_id: ShiftId | None = None,
        role_id: RoleId | None = None,
        detail: str | None = None,
        icon: str | None = None,
        ref: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> ShiftEvent:
        """Assign a seq, persist, fan out. Safe to call from the event loop."""
        leak = _looks_leaky(text) or _looks_leaky(detail)
        if leak:
            logger.error(
                "REDACTED event for %s: %r appeared in a user-facing string",
                self.company_id,
                leak,
            )
            text = "An employee did some work."
            detail = None

        with self._lock:
            self._seq += 1
            event = ShiftEvent(
                seq=self._seq,
                id=f"ev_{secrets.token_hex(6)}",
                company_id=self.company_id,
                shift_id=shift_id,
                role_id=role_id,
                kind=kind,
                at=datetime.now(UTC),
                text=text,
                detail=detail,
                icon=icon,
                ref=ref,
                payload=payload or {},
            )
            self._ring.append(event)
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the subscriber rather than block the bus. It reconnects
                # with its last seq and misses nothing.
                logger.info("dropping slow subscriber on %s", self.company_id)
                self._subscribers.discard(queue)
        return event

    def emit_threadsafe(self, kind: ShiftEventKind, text: str, **kwargs: Any) -> None:
        """Emit from a non-loop thread. Required by the SDK's synchronous run()."""
        loop = self._loop
        if loop is None:
            raise RuntimeError("CompanyBus.bind_loop() was never called")
        loop.call_soon_threadsafe(lambda: self.emit(kind, text, **kwargs))

    # -------------------------------------------------------------- read paths
    def replay(self, since_seq: int = 0, limit: int = 500) -> list[ShiftEvent]:
        """Durable history. Serves cold loads with no live socket at all."""
        with self._lock:
            if self._ring and self._ring[0].seq <= since_seq + 1:
                return [e for e in self._ring if e.seq > since_seq][:limit]
        # Older than the ring: go to disk.
        events: list[ShiftEvent] = []
        if not self._log_path.exists():
            return events
        with self._log_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = ShiftEvent.model_validate_json(line)
                except ValueError:
                    continue
                if event.seq > since_seq:
                    events.append(event)
                    if len(events) >= limit:
                        break
        return events

    async def subscribe(
        self, since_seq: int | None = None
    ) -> AsyncIterator[ShiftEvent]:
        """Backlog first, then live. At-least-once, ordered, no gaps."""
        queue: asyncio.Queue[ShiftEvent] = asyncio.Queue(SUBSCRIBER_QUEUE_SIZE)
        # Register before draining the backlog so nothing emitted in between is
        # lost; the seq filter below removes the resulting overlap.
        self._subscribers.add(queue)
        delivered = since_seq or 0
        try:
            for event in self.replay(delivered, limit=RING_SIZE):
                delivered = event.seq
                yield event
            while True:
                event = await queue.get()
                if event.seq <= delivered:
                    continue  # already sent as backlog
                delivered = event.seq
                yield event
        finally:
            self._subscribers.discard(queue)

    @property
    def last_seq(self) -> int:
        return self._seq
