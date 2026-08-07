"""What an employee reads before starting work.

The single biggest context-window lever in the product: a role agent must never
see the whole brain. This renders it in priority order and truncates from the
bottom, so the things that change what an employee does survive and the things
that merely inform them get cut first.

In M3 this goes into the *first user message* of a role's conversation rather
than its system prompt — it changes every shift, and keeping the system prefix
stable is what makes prompt caching work.
"""

from __future__ import annotations

from werkhaus.brain.store import BrainStore
from werkhaus.contract.models import TaskStatus

# Rough and deliberately pessimistic. A real tokenizer here would be precision
# theatre: the budget exists to stop a runaway, not to pack the window.
CHARS_PER_TOKEN = 3.6


def _fits(blocks: list[str], budget_tokens: int) -> bool:
    return sum(len(b) for b in blocks) / CHARS_PER_TOKEN <= budget_tokens


def render_digest(
    store: BrainStore,
    *,
    role_id: str,
    role_name: str | None = None,
    shift_number: int | None = None,
    budget_tokens: int = 1200,
) -> str:
    state = store.state
    who = role_name or role_id
    blocks: list[str] = []

    # 1. Why the company exists. Never cut.
    header = [f"# {state.name or 'This company'}"]
    if shift_number is not None:
        header[0] += f" — shift {shift_number}"
    if state.charter:
        header.append(f"\n**What we're building:** {state.charter.one_liner}")
        header.append(f"**Who it's for:** {state.charter.audience}")
        header.append(f"**Done means:** {state.charter.success_looks_like}")
        if state.charter.constraints:
            header.append("\n**Rules you must not break:**")
            header.extend(f"- {c}" for c in state.charter.constraints)
    blocks.append("\n".join(header))

    # 2. Where we stand. Drives what is worth doing at all.
    progress = state.progress
    stand = ["\n## Where we stand\n", f"{progress.percent}% — {progress.headline}"]
    if progress.whats_missing:
        stand.append("\nStill missing:")
        stand.extend(f"- {item}" for item in progress.whats_missing)
    blocks.append("\n".join(stand))

    # 3. This employee's own work. The most actionable thing here.
    mine = [
        t
        for t in state.tasks.values()
        if t.status is TaskStatus.OPEN and t.owner in (role_id, None)
    ]
    mine.sort(key=lambda t: t.priority)
    if mine:
        lines = [f"\n## Open items for {who}\n"]
        lines.extend(f"- [P{t.priority}] #{t.id} {t.title}" for t in mine[:8])
        blocks.append("\n".join(lines))

    # 4. Decisions already made — so nobody relitigates them.
    if state.decisions:
        lines = ["\n## Decisions in force\n"]
        for decision in list(state.decisions.values())[-8:]:
            line = f"- {decision.title}"
            if decision.contest_note:
                line += f" (contested: {decision.contest_note})"
            lines.append(line)
        blocks.append("\n".join(lines))

    # 5. Open objections. The reason not to repeat last shift's mistake.
    if state.objections:
        serious = [
            o for o in state.objections.values() if o.severity in ("fatal", "serious")
        ]
        if serious:
            lines = ["\n## What the critic flagged\n"]
            lines.extend(f"- [{o.severity}] {o.text}" for o in serious[-5:])
            blocks.append("\n".join(lines))

    # 6. What exists to read, and how much to trust it.
    if state.artifacts:
        lines = ["\n## Documents you can read\n"]
        for artifact in state.artifacts.values():
            lines.append(
                f"- {artifact.path} ({artifact.confidence}) — {artifact.title}"
            )
        blocks.append("\n".join(lines))

    # 7. Anything the founder said. Rare, so it goes last but is worth keeping.
    if state.notes:
        lines = ["\n## From the founder\n"]
        lines.extend(f"- {note}" for note in state.notes[-3:])
        blocks.append("\n".join(lines))

    # Truncate from the bottom: keep the charter and the standing, drop the
    # nice-to-know. Never drop block 0.
    while len(blocks) > 1 and not _fits(blocks, budget_tokens):
        blocks.pop()

    return "\n".join(blocks).strip() + "\n"
