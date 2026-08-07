"""The org, as the user meets it.

Shared by both engines: the stub fakes what these people produce, the real engine
runs them as SDK agents, but the user sees the same eight employees either way.
The `.md` agent definitions in ``agents/`` (M4) carry the prompts and budgets;
this carries only what the dashboard renders.

Names, not roles, in the UI copy. "Maya is reading competitor sites" is a company;
"the researcher agent invoked browser_navigate" is a log.
"""

from __future__ import annotations

from werkhaus.contract.models import Role

# Per-run budget caps, in USD. The sum is the worst case for one full shift
# ($8.80 + condenser and judge overhead). Kept here so the stub's ledger numbers
# match the real engine's shape and we have a cost model before we have a bill.
ROLE_BUDGETS: dict[str, float] = {
    "chief": 0.40,
    "researcher": 1.50,
    "strategist": 1.00,
    "brand": 0.80,
    "growth": 0.80,
    "analyst": 0.60,
    "engineer": 3.00,
    "critic": 0.70,
}

ROSTER: tuple[Role, ...] = (
    Role(
        id="chief",
        display_name="Ada",
        job_title="Chief of Staff",
        avatar="ada",
        accent="#6366f1",
        blurb=(
            "Decides what the company works on this shift, "
            "and writes up what happened."
        ),
    ),
    Role(
        id="researcher",
        display_name="Maya",
        job_title="Market Researcher",
        avatar="maya",
        accent="#0ea5e9",
        blurb="Reads real competitor sites and reports what she can actually source.",
    ),
    Role(
        id="strategist",
        display_name="Ines",
        job_title="Strategist",
        avatar="ines",
        accent="#8b5cf6",
        blurb=(
            "Owns positioning, audience and price. "
            "Commits to one answer, not a menu."
        ),
    ),
    Role(
        id="brand",
        display_name="Otto",
        job_title="Brand & Copy",
        avatar="otto",
        accent="#ec4899",
        blurb="Writes the words, in the customer's language rather than the company's.",
    ),
    Role(
        id="growth",
        display_name="Rafa",
        job_title="Growth",
        avatar="rafa",
        accent="#f59e0b",
        blurb="Finds where the audience already is. Drafts outreach — never sends it.",
    ),
    Role(
        id="analyst",
        display_name="Nia",
        job_title="Numbers",
        avatar="nia",
        accent="#14b8a6",
        blurb="Builds the one-page money model and labels every assumption in it.",
    ),
    Role(
        id="engineer",
        display_name="Kit",
        job_title="Builder",
        avatar="kit",
        accent="#22c55e",
        blurb=(
            "Builds and ships the landing page. "
            "The one thing here that either works or doesn't."
        ),
    ),
    Role(
        id="critic",
        display_name="Vera",
        job_title="Devil's Advocate",
        avatar="vera",
        accent="#ef4444",
        blurb="Paid to be wrong-proof, not agreeable. Files objections you can check.",
    ),
)

ROSTER_BY_ID: dict[str, Role] = {role.id: role for role in ROSTER}


def role(role_id: str) -> Role:
    return ROSTER_BY_ID[role_id]


def display_name(role_id: str) -> str:
    return ROSTER_BY_ID[role_id].display_name
