"""Raw agent events in, dashboard prose out.

The narrator is the primary defence for the vocabulary rule: the user has
employees who work shifts, not agents with tools. It is deterministic, calls no
model, and suppresses far more than it emits — most of what an agent does reads
as "looking at a file", which on a dashboard reads as the company doing nothing.

Hard rules, enforced here in code and backstopped by the bus redaction regexes:
no shell commands, no absolute paths, no stack traces, no SDK vocabulary. When
in doubt, say something generic and true.
"""

from __future__ import annotations

import logging
import re
import time
from urllib.parse import urlsplit

from openhands.sdk.event import (
    ActionEvent,
    AgentErrorEvent,
    MessageEvent,
    ObservationEvent,
)
from openhands.sdk.event.conversation_error import ConversationErrorEvent

from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.engines.openhands.brain_tool import ShiftContext, normalize_url

logger = logging.getLogger(__name__)

ACTIVITY_INTERVAL = 3.0
"""At most one activity line per role per three seconds. A firehose of
"Maya is reading …" is as unreadable as silence."""

BROWSER_TOOLS = {
    "browser_navigate",
    "browser_click",
    "browser_get_state",
    "browser_get_content",
    "browser_type",
    "browser_scroll",
    "browser_go_back",
    "browser_list_tabs",
    "browser_switch_tab",
    "browser_close_tab",
    "browser_get_storage",
    "browser_set_storage",
    "browser_start_recording",
    "browser_stop_recording",
}

SUPPRESSED_TOOLS = {"think", "glob", "grep", "werkhaus_brain", "finish", "task_tracker"}

# Anything matching these never leaves the narrator, even via the summary
# fallback. The bus has its own list; this one is broader on purpose.
_UNSAFE = re.compile(
    r"[/\\`]|traceback|http|www\.|"
    + "|".join(("open" + "hands", "lite" + "llm", "tok" + "en", "conversat" + "ion"))
    , re.IGNORECASE,
)


def _domain(url: str) -> str | None:
    host = urlsplit(url.strip()).netloc
    return host.removeprefix("www.") or None


class Narrator:
    """One instance per shift, used as the conversation callback. Runs on the
    worker thread; everything it emits goes through ``emit_threadsafe``."""

    def __init__(self, ctx: ShiftContext) -> None:
        self.ctx = ctx
        self._last_domain: str | None = None
        self._pending: str | None = None

    # ------------------------------------------------------------------ entry
    def __call__(self, event) -> None:
        try:
            self._feed(event)
        except Exception:
            # A narrator bug must never take down a running shift.
            logger.exception("narrator choked on %s", type(event).__name__)

    def _feed(self, event) -> None:
        ctx = self.ctx
        if ctx.stopped.is_set():
            return

        if isinstance(event, ActionEvent):
            self._action(event)
        elif isinstance(event, ConversationErrorEvent):
            # Not user-facing; the shift loop reads the code to classify the
            # outcome after the run returns.
            ctx.error_code = event.code
            logger.warning("run limit: %s — %s", event.code, event.detail)
        elif isinstance(event, AgentErrorEvent):
            logger.warning("agent error (%s): %s", event.tool_name, event.error)
            self._activity(f"{ctx.name} hit a problem and is trying another way.")
        elif isinstance(event, MessageEvent) and event.source == "agent":
            text = _message_text(event)
            if text:
                said = scrub_sentence(text)
                if said:
                    ctx.bus.emit_threadsafe(
                        K.ROLE_SAID,
                        f"{ctx.name}: {said}",
                        shift_id=ctx.shift_id,
                        role_id=ctx.role_id,
                    )
        elif isinstance(event, ObservationEvent):
            return  # raw page text and tool output; never user-safe

    # ---------------------------------------------------------------- actions
    def _action(self, event: ActionEvent) -> None:
        ctx = self.ctx
        tool = event.tool_name

        if tool == "browser_navigate" and event.action is not None:
            url = getattr(event.action, "url", None)
            if url:
                ctx.browsed_urls.add(normalize_url(url))
                self._last_domain = _domain(url)
            if self._last_domain:
                self._activity(f"{ctx.name} is reading {self._last_domain}")
            return

        if tool in BROWSER_TOOLS:
            if self._last_domain:
                self._activity(f"{ctx.name} is reading {self._last_domain}")
            return

        if tool == "file_editor" and event.action is not None:
            command = getattr(event.action, "command", None)
            if command == "create":
                path = str(getattr(event.action, "path", "") or "")
                filename = path.rsplit("/", 1)[-1]
                if filename and not _UNSAFE.search(filename):
                    self._activity(f"{ctx.name} is drafting {filename}")
                    return
            return  # view / str_replace / everything else: noise

        if tool in SUPPRESSED_TOOLS or event.action is None:
            return

        # Unknown tool: the model's own ten-word summary, if it survives the
        # scrubber; a generic truth if it doesn't.
        summary = (event.summary or "").strip()
        if summary and not _UNSAFE.search(summary):
            line = summary[0].upper() + summary[1:].rstrip(".")
            self._activity(f"{ctx.name}: {line.lower()}")
        else:
            self._activity(f"{ctx.name} is working.")

    # --------------------------------------------------------------- plumbing
    def _activity(self, text: str) -> None:
        """Rate-limited role activity. The newest line wins; a line inside the
        quiet window is remembered and replaces the display on the next beat."""
        ctx = self.ctx
        now = time.monotonic()
        if now - ctx.last_activity_emit < ACTIVITY_INTERVAL:
            self._pending = text
            return
        if self._pending and self._pending != text:
            text = self._pending
        self._pending = None
        ctx.last_activity_emit = now
        if ctx.set_activity:
            ctx.set_activity(text)
        ctx.bus.emit_threadsafe(
            K.ROLE_ACTIVITY, text, shift_id=ctx.shift_id, role_id=ctx.role_id
        )


def _message_text(event: MessageEvent) -> str:
    parts = []
    for block in event.llm_message.content:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "\n".join(parts).strip()


def scrub_sentence(text: str, limit: int = 280) -> str:
    """Reduce an agent's closing message to something a founder can read:
    first paragraph, no markdown scaffolding, no unsafe fragments, bounded."""
    paragraph = text.split("\n\n")[0].strip()
    paragraph = re.sub(r"[#*_>`]+", "", paragraph).strip()
    # Drop lines with anything the vocabulary rule forbids.
    lines = [
        line for line in paragraph.splitlines() if line and not _UNSAFE.search(line)
    ]
    result = " ".join(lines).strip()
    if len(result) > limit:
        result = result[: limit - 1].rsplit(" ", 1)[0] + "…"
    return result
