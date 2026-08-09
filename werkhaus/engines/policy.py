"""What an employee is allowed to hold, and how much of it.

The single file to read to know what the AI can do. No ``openhands.*`` imports:
this must stay readable and testable without the SDK in the way.

Three layers, and each one is a refusal:

1. **Which servers** attach to a shift at all.
2. **Which tools** inside them the model is allowed to see.
3. **How many** tools in total, because a model handed two hundred of them is
   worse at using any of them than one handed twenty.

The third is the one people skip. Tool schemas are sent on *every* model call,
so a company with ten connected servers pays their whole surface area in tokens
each step, and accuracy degrades long before the context actually overflows.
"""

from __future__ import annotations

import re

TOOL_BUDGET = 48
"""How many tools an employee may see at once.

Not a context limit — a judgement limit. Werkhaus's own tools take a handful;
the rest is what a founder connected. Past roughly this many, models start
picking plausible-looking wrong tools, and the failure looks like the employee
being stupid rather than the toolbox being too big.
"""

DENY_TOOLS = frozenset(
    {
        # The exfiltration primitive. Migrations are the sanctioned way to
        # change a database; ad-hoc SQL is how the best-known MCP data leak
        # actually did its damage.
        "execute_sql",
        "query",
        "run_query",
        # Destroying what the founder owns is never a shift's job.
        "delete_project",
        "delete_branch",
        "drop_table",
        "delete_database",
        "pause_project",
        "restore_project",
        # Spending money without being asked.
        "create_refund",
        "buy_domain",
        "buy_credits",
        "buy_pro",
    }
)


def tool_filter_regex(deny: frozenset[str] = DENY_TOOLS) -> str:
    """A pattern that admits everything except the denied names.

    Must match both ``execute_sql`` and ``supabase_execute_sql``: fastmcp
    mounts multiple servers on one client and prefixes every tool with its
    server name, so a denylist written against bare names silently fails open
    for exactly the companies with the most connections — the ones with the
    most to lose.

    The SDK applies this with an anchored ``re.match`` over the tool name,
    including tools that appear at runtime.
    """
    names = "|".join(sorted(re.escape(n) for n in deny))
    return rf"^(?!(?:[a-z0-9]+_)?(?:{names})$).*"


def denied(tool_name: str, deny: frozenset[str] = DENY_TOOLS) -> bool:
    """Whether a tool would be refused, bare or server-prefixed."""
    return re.match(tool_filter_regex(deny), tool_name) is None


def within_budget(counts: dict[str, int], budget: int = TOOL_BUDGET) -> list[str]:
    """Which servers fit, smallest first.

    Smallest first on purpose: it admits the most *services* for a given number
    of tools, and a company that connected five small servers wants all five
    rather than one enormous one that used up the whole allowance.
    """
    order = sorted(counts, key=lambda name: (counts[name], name))
    kept, spent = [], 0
    for name in order:
        if spent + counts[name] > budget:
            continue
        kept.append(name)
        spent += counts[name]
    return kept
