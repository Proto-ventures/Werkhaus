"""Associative recall over a company's memory.

The digest a shift starts with has a 1,200-token budget and, until now, filled
it by recency: the last eight decisions, the last five objections, the last
three notes. Recency is a reasonable default and a bad one for a company that
has run for a month — the thing that matters for today's work is rarely the
thing that happened most recently.

This is an adaptation of **HeLa-Mem** (arXiv:2604.16839), which pairs ordinary
semantic search with a Hebbian association graph: memories that keep being used
together grow links, and retrieving one spreads activation to its neighbours.
On LoCoMo it beat MemoryOS on every question category while using ~1,010 tokens
against 16,910 for stuffing the raw history in — and the token figure is why it
is interesting here, because our budget is 1,200.

Three deliberate departures from the paper, all of them about scale:

**No embeddings.** The paper scores base activation by cosine similarity. That
needs an embedding model — a dependency, a network call per memory, and a cost
on the same free tier the shift is spending. Werkhaus memories are short and
already structured (an artifact has a title, a summary and a confidence), so
base activation here is lexical overlap plus keyword hits. Weaker than cosine
on paraphrase; free, offline, and deterministic in tests.

**The graph is a projection, not a store.** Weights are recomputed from the
shift history on load rather than written to the log. That is the same rule the
rest of this codebase follows — no fact exists only in a projection — and it
means the graph can never drift from what actually happened, and replaying the
log rebuilds it exactly.

**Co-activation is a shift, not a retrieval.** The paper strengthens pairs that
appear together in one retrieval result. We have something better and cheaper:
things genuinely worked on together. An artifact and a decision produced in the
same shift were used together by an employee, which is a stronger signal than
having been returned by the same search.

The paper's own stated limitation applies to us too, and harder: Hebbian
weights need history. A company on shift one has none, so recall falls back to
recency — which is what it would have used anyway.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from werkhaus.brain.store import CompanyBrain

# Straight from the paper (Table: hyperparameters).
DECAY = 0.995
"""λ. Applied once per shift, so an unused link loses half its weight in about
140 shifts — slow enough that a quiet fortnight forgets nothing."""

LEARN = 0.02
"""η. Added when two memories are worked on in the same shift."""

SPREAD = 0.1
"""β. How much of a neighbour's activation flows across a link. Low on
purpose: association is a tie-breaker among relevant memories, not a way for
an old strongly-linked cluster to drown out something directly on topic."""

TAU_DAYS = 60.0
"""Time constant for recency decay in base activation."""

KEYWORD_WEIGHT = 0.5
"""α. How much an exact term match is worth against overall overlap."""

PRUNE_BELOW = 0.005
"""Links this weak are noise; dropping them keeps the graph small enough to
walk on every digest render."""

_WORD = re.compile(r"[a-z0-9]{3,}")
_STOP = frozenset(
    "the and for with that this from you your our are was were will has have had "
    "not but its into over under about what when where which who whom how any all "
    "can could should would than then them they their there here more most some "
    "one two three each other".split()
)


def _terms(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if w not in _STOP}


@dataclass(frozen=True)
class Memory:
    """One thing the company knows, in the form it will be recalled in."""

    id: str
    kind: str
    text: str
    at: datetime
    terms: set[str] = field(default_factory=set)

    def render(self) -> str:
        return self.text


def memories(state: CompanyBrain) -> dict[str, Memory]:
    """Everything recallable, as flat nodes.

    Artifacts, decisions, objections and open tasks are already structured
    facts with a title and a body — which is the one idea worth taking from
    Panini (arXiv:2602.15156), whose gain comes from retrieving structured
    units rather than prose chunks. Panini pays an LLM per document to build
    them; we get them for free because the employees file them that way.
    """
    out: dict[str, Memory] = {}

    for artifact in state.artifacts.values():
        text = (
            f"- {artifact.path} ({artifact.confidence}) — {artifact.title}"
            f"{': ' + artifact.summary if artifact.summary else ''}"
        )
        out[artifact.id] = Memory(
            id=artifact.id,
            kind="artifact",
            text=text,
            at=artifact.updated_at,
            terms=_terms(f"{artifact.title} {artifact.summary} {artifact.path}"),
        )

    for decision in state.decisions.values():
        line = f"- {decision.title}"
        if decision.contest_note:
            line += f" (contested: {decision.contest_note})"
        out[decision.id] = Memory(
            id=decision.id,
            kind="decision",
            text=line,
            at=decision.at,
            terms=_terms(f"{decision.title} {decision.rationale}"),
        )

    for objection in state.objections.values():
        if objection.severity not in ("fatal", "serious"):
            continue
        out[objection.id] = Memory(
            id=objection.id,
            kind="objection",
            text=f"- [{objection.severity}] {objection.text}",
            at=objection.at,
            terms=_terms(f"{objection.text} {objection.settled_by or ''}"),
        )

    return out


def graph(state: CompanyBrain) -> dict[tuple[str, str], float]:
    """The Hebbian weights, recomputed from the shift history.

    ``w_ij ← (1 − λ)·w_ij + η·1[co-activated]`` — the paper's rule, with one
    decay step per shift and co-activation meaning "produced or settled in the
    same shift".
    """
    weights: dict[tuple[str, str], float] = {}
    for shift in sorted(state.shifts.values(), key=lambda s: s.number):
        # A time step passes whether or not anything was learned.
        if weights:
            for pair in list(weights):
                weights[pair] *= DECAY
                if weights[pair] < PRUNE_BELOW:
                    del weights[pair]

        touched = sorted(
            {*shift.artifacts_produced, *shift.decisions_made}
            | {
                o.id
                for o in state.objections.values()
                if o.shift_id == shift.id and o.severity in ("fatal", "serious")
            }
        )
        for i, left in enumerate(touched):
            for right in touched[i + 1 :]:
                key = (left, right)
                weights[key] = weights.get(key, 0.0) + LEARN
    return weights


def _base_activation(memory: Memory, query: set[str], now: datetime) -> float:
    """Cosine's cheap cousin: overlap, weighted by exact hits, decayed by age."""
    if not memory.terms:
        overlap = 0.0
    else:
        shared = memory.terms & query
        overlap = len(shared) / math.sqrt(len(memory.terms) * max(len(query), 1))
        overlap += KEYWORD_WEIGHT * (len(shared) / max(len(query), 1))
    age_days = max((now - memory.at).total_seconds(), 0.0) / 86_400
    return overlap * math.exp(-age_days / TAU_DAYS)


def recall(
    state: CompanyBrain,
    query: str,
    *,
    limit: int = 12,
    now: datetime | None = None,
) -> list[Memory]:
    """The memories most worth putting in front of an employee today.

    Base activation finds what looks relevant; spreading activation adds what
    has repeatedly been worked on alongside it. With no history, or nothing
    matching the query, the caller gets recency — the honest fallback, and the
    paper's own cold-start caveat.
    """
    nodes = memories(state)
    if not nodes:
        return []
    stamp = now or datetime.now(UTC)
    terms = _terms(query)

    base = {mid: _base_activation(m, terms, stamp) for mid, m in nodes.items()}
    if not terms or not any(base.values()):
        newest = sorted(nodes.values(), key=lambda m: m.at, reverse=True)
        return newest[:limit]

    # S(v_j) = S_base(v_j) + β·Σ_i S_base(v_i)·w_ij
    spread = dict(base)
    for (left, right), weight in graph(state).items():
        if left in base and right in spread:
            spread[right] += SPREAD * base[left] * weight
        if right in base and left in spread:
            spread[left] += SPREAD * base[right] * weight

    ranked = sorted(
        nodes.values(),
        key=lambda m: (-spread.get(m.id, 0.0), -m.at.timestamp()),
    )
    return [m for m in ranked if spread.get(m.id, 0.0) > 0][:limit]


def associations(state: CompanyBrain, memory_id: str, limit: int = 5) -> list[str]:
    """What this memory is habitually used with. For explaining a recall."""
    linked: list[tuple[str, float]] = []
    for (left, right), weight in graph(state).items():
        if left == memory_id:
            linked.append((right, weight))
        elif right == memory_id:
            linked.append((left, weight))
    linked.sort(key=lambda pair: -pair[1])
    return [other for other, _ in linked[:limit]]
