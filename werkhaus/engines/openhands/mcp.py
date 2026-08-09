"""Connected servers, handed to an employee.

Two things decide what an employee gets, and both are refusals.

**No browser and credentials in the same conversation.** An employee reading
the open web is reading text written by strangers, some of whom would like it
to contain instructions. An employee holding the company's keys can act on
them. Together those are the shape of every published agent data leak, and no
amount of filtering the text has been shown to fix it — Supabase tried and said
so. So a shift with connected servers runs without the browser, and says why.

**A dead server must not cost a shift.** The SDK connects lazily on the first
model call and a server that fails takes the whole run down with it. Each one
is therefore started once, alone, on a timeout, before the agent exists. What
answers is used; what does not is dropped, and the founder is told which.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from openhands.sdk.mcp import MCPServer, create_mcp_tools
from pydantic import SecretStr

from werkhaus.engines.policy import tool_filter_regex, within_budget

logger = logging.getLogger(__name__)

PROBE_SECONDS = 30.0
"""A cold `npx` download is slow the first time and fast afterwards. Thirty
seconds is long enough for the first, and still far shorter than a shift."""


@dataclass
class McpBuild:
    servers: dict[str, MCPServer] = field(default_factory=dict)
    dropped: list[tuple[str, str]] = field(default_factory=list)
    """(label, reason) for each server that did not answer."""

    held_back: list[str] = field(default_factory=list)
    """Servers that answered and were left out to stay inside the tool budget."""

    tools: int = 0

    @property
    def filter_regex(self) -> str:
        return tool_filter_regex()

    @property
    def browsing_allowed(self) -> bool:
        """False the moment the employee holds anything. See the module note."""
        return not self.servers

    def said(self) -> list[str]:
        """What to tell the founder, in their words rather than ours."""
        lines = [
            f"{label} isn't answering, so the team will work without it today."
            for label, _ in self.dropped
        ]
        if self.held_back:
            lines.append(
                "There are more services connected than one employee can hold "
                f"at once, so {', '.join(self.held_back)} sat this shift out. "
                "The team picks up where it left off next time."
            )
        if self.servers:
            lines.append(
                "The team is using the services you connected, so it won't "
                "read the open web this shift — one or the other, never both."
            )
        return lines


def to_server(row: dict[str, Any], env: dict[str, str]) -> MCPServer:
    """One stored connection as the SDK's own config.

    Values go in as ``SecretStr`` because the agent spec is serialized to disk
    with the conversation, and a plain string there would write live keys into
    a file nothing else guards.
    """
    secrets = {k: SecretStr(v) for k, v in env.items()}
    if row.get("transport", "stdio") == "stdio":
        command, *rest = (row.get("command") or "").split()
        return MCPServer(
            command=command,
            args=[*rest, *row.get("args", [])],
            transport="stdio",
            env=secrets or None,
        )
    headers = None
    if "Authorization" in env or "AUTHORIZATION" in env:
        pass  # already explicit; leave it in env for the transport to use
    return MCPServer(
        url=row["url"],
        transport=row.get("transport") or "streamable-http",
        headers={k: SecretStr(v) for k, v in env.items()} or headers,
    )


def probe(candidates: dict[str, tuple[str, MCPServer]]) -> McpBuild:
    """Start each server alone, keep what answers, and stop at the budget.

    Sequential rather than concurrent: these are subprocesses and network calls
    made on the founder's behalf, and a company with ten connections should not
    open ten at once to find out which work.

    Probing also counts tools, which is the number that actually matters — it
    is paid on every model call, and no other stage of the system can measure
    it, because only the server knows what it offers.
    """
    build = McpBuild()
    answered: dict[str, MCPServer] = {}
    counts: dict[str, int] = {}
    labels = {name: label for name, (label, _) in candidates.items()}

    for name, (label, server) in candidates.items():
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(_list_once, {name: server})
                count = future.result(timeout=PROBE_SECONDS)
        except Exception as exc:
            logger.warning("mcp server %s did not answer: %s", name, exc)
            build.dropped.append((label, str(exc)[:200]))
            continue
        logger.info("mcp server %s answered with %d tools", name, count)
        answered[name] = server
        counts[name] = count

    kept = within_budget(counts)
    for name in answered:
        if name in kept:
            build.servers[name] = answered[name]
            build.tools += counts[name]
        else:
            build.held_back.append(labels.get(name, name))
    return build


def _list_once(config: dict[str, MCPServer]) -> int:
    with create_mcp_tools(config, timeout=PROBE_SECONDS) as client:
        return len(client.tools)


def build_for_shift(engine, company) -> McpBuild:
    """Everything this company has connected, minus whatever is not answering."""
    rows = engine._mcp_rows(company)
    if not rows:
        return McpBuild()
    candidates: dict[str, tuple[str, MCPServer]] = {}
    for row in rows:
        try:
            server = to_server(row, engine.mcp_env(company, row))
        except Exception as exc:
            logger.warning("could not build %s: %s", row.get("name"), exc)
            continue
        candidates[row["name"]] = (row.get("label") or row["name"], server)
    return probe(candidates)
