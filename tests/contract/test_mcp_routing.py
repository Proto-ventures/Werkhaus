"""Which servers reach an employee, and how many of their tools.

A directory of thousands of servers is only useful if connecting several of
them doesn't break the employee holding them. Three refusals do the work, and
each has cost somebody a production incident somewhere:

* browser and credentials never share a conversation,
* dangerous tools are denied by name in both the bare and prefixed forms,
* and the total number of tools is capped, because schemas are re-sent on every
  model call and accuracy falls off long before the context does.
"""

from __future__ import annotations

import pytest

from werkhaus.engines.policy import (
    DENY_TOOLS,
    TOOL_BUDGET,
    denied,
    tool_filter_regex,
    within_budget,
)


@pytest.mark.parametrize("tool", sorted(DENY_TOOLS))
def test_denied_tools_are_denied_bare_and_prefixed(tool: str) -> None:
    """fastmcp mounts several servers on one client and prefixes every tool
    with its server name. A denylist written against bare names would fail
    open for exactly the companies with the most connections."""
    assert denied(tool), tool
    assert denied(f"supabase_{tool}"), f"supabase_{tool}"
    assert denied(f"shopify_{tool}"), f"shopify_{tool}"


@pytest.mark.parametrize(
    "tool",
    [
        "apply_migration",
        "supabase_apply_migration",
        "deploy_edge_function",
        "get_orders",
        "shopify_list_products",
        "werkhaus_brain",
        "file_editor",
    ],
)
def test_ordinary_tools_get_through(tool: str) -> None:
    assert not denied(tool), tool


def test_the_filter_is_anchored() -> None:
    """The SDK applies this with re.match, so an unanchored pattern would let
    `x_execute_sql_y` through while looking correct."""
    pattern = tool_filter_regex()
    assert pattern.startswith("^")
    assert denied("execute_sql")
    assert not denied("execute_sql_safely")


def test_the_tool_budget_admits_the_most_services() -> None:
    """Smallest first: a founder who connected five small services wants all
    five, not one enormous one that ate the whole allowance."""
    counts = {"big": TOOL_BUDGET, "a": 5, "b": 5, "c": 5}
    kept = within_budget(counts)
    assert set(kept) == {"a", "b", "c"}
    assert sum(counts[k] for k in kept) <= TOOL_BUDGET


def test_everything_fits_when_it_fits() -> None:
    counts = {"a": 10, "b": 12}
    assert set(within_budget(counts)) == {"a", "b"}


def test_nothing_connected_is_not_an_error() -> None:
    assert within_budget({}) == []


def test_an_employee_may_not_browse_and_hold_keys() -> None:
    from werkhaus.engines.openhands.mcp import McpBuild

    assert McpBuild().browsing_allowed
    held = McpBuild(servers={"shopify": object()})  # type: ignore[dict-item]
    assert not held.browsing_allowed
    assert any("never both" in line for line in held.said())


def test_build_agent_refuses_the_dangerous_combination() -> None:
    """Enforced in code, not asked for in a prompt."""
    from openhands.sdk.testing import TestLLM

    from werkhaus.brain.store import BrainStore
    from werkhaus.engines.openhands.maya import build_agent

    with pytest.raises(ValueError, match="browse"):
        build_agent(
            TestLLM.from_messages([]),
            "co_x",
            BrainStore.__new__(BrainStore),
            1,
            browsing=True,
            mcp={"shopify": object()},
        )
