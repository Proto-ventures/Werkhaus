"""Associative recall, and whether it earns its place.

An adaptation of HeLa-Mem (arXiv:2604.16839). The claim being tested is narrow
and checkable: for a company with history, choosing what to remember by
association beats choosing by recency, inside the same token budget.

The scenario below is the one that matters in practice. A company works on
pricing early, spends weeks on unrelated things, and then comes back to
pricing. Recency hands the employee the unrelated recent work. Association
should hand back the pricing cluster.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from werkhaus.brain.memory import DECAY, LEARN, graph, memories, recall
from werkhaus.brain.store import BrainStore


def _company(tmp_path):
    return BrainStore(tmp_path / "co_mem", "co_mem")


def _shift(store: BrainStore, number: int):
    return store.open_shift(number=number, agenda=[f"shift {number}"])


def _artifact(store, shift, path, title, summary=""):
    (store.paths.root / path).parent.mkdir(parents=True, exist_ok=True)
    (store.paths.root / path).write_text("x", encoding="utf-8")
    return store.record_artifact(
        path=path, title=title, summary=summary, kind="doc", sources=[],
        confidence="inferred", role_id="researcher", shift_id=shift.id,
    )


def test_the_graph_follows_the_papers_rule(tmp_path) -> None:
    """w_ij <- (1-lambda)*w_ij + eta*1[co-activated], one decay step per shift."""
    store = _company(tmp_path)
    store.set_charter_from_idea = None  # unused; keeps linters quiet
    first = _shift(store, 1)
    a = _artifact(store, first, "artifacts/a.md", "Pricing model")
    b = _artifact(store, first, "artifacts/b.md", "Pricing research")
    store.close_shift(first.id, status="completed", summary="s")

    weights = graph(store.state)
    pair = tuple(sorted((a.id, b.id)))
    assert weights[pair] == LEARN, "one shift together is one unit of learning"

    # A shift they are both absent from decays the link.
    second = _shift(store, 2)
    store.close_shift(second.id, status="completed", summary="s")
    assert graph(store.state)[pair] == LEARN * DECAY


def test_association_beats_recency_when_the_relevant_memory_is_old(
    tmp_path,
) -> None:
    """The whole point, in one test.

    Pricing work happens early and repeatedly. Unrelated work happens later.
    Asked about pricing, recency returns the recent noise; recall should return
    the pricing cluster.
    """
    store = _company(tmp_path)
    old = datetime.now(UTC) - timedelta(days=20)

    # Three shifts where pricing documents are produced together.
    priced = []
    for n in (1, 2, 3):
        shift = _shift(store, n)
        priced.append(
            _artifact(store, shift, f"artifacts/price{n}.md", f"Price study {n}",
                      "what six competitors charge per month")
        )
        store.close_shift(shift.id, status="completed", summary="s")

    # Then weeks of unrelated, more recent work.
    recent = []
    for n in range(4, 12):
        shift = _shift(store, n)
        recent.append(
            _artifact(store, shift, f"artifacts/brand{n}.md", f"Brand voice {n}",
                      "tone of voice and logo explorations")
        )
        store.close_shift(shift.id, status="completed", summary="s")

    everything = memories(store.state)
    newest = sorted(everything.values(), key=lambda m: m.at, reverse=True)[:3]
    assert all(m.id in {a.id for a in recent} for m in newest), (
        "recency would hand back only the recent brand work"
    )

    recalled = recall(store.state, "what should we charge per month", limit=3)
    ids = {m.id for m in recalled}
    assert ids & {a.id for a in priced}, "recall missed the pricing cluster"
    assert len(ids & {a.id for a in priced}) >= 2, (
        f"expected the pricing cluster, got {[m.text for m in recalled]}"
    )
    assert old  # scenario spans real time


def test_a_new_company_falls_back_to_recency(tmp_path) -> None:
    """The paper's own cold-start caveat: no history, no associations. The
    fallback is what the digest did before, so nothing regresses."""
    store = _company(tmp_path)
    shift = _shift(store, 1)
    first = _artifact(store, shift, "artifacts/a.md", "Market research")
    store.close_shift(shift.id, status="completed", summary="s")

    assert graph(store.state) == {}, "one shift cannot form an association"
    recalled = recall(store.state, "something entirely unrelated to anything")
    assert [m.id for m in recalled] == [first.id], "should degrade to recency"


def test_recall_is_deterministic(tmp_path) -> None:
    """No embeddings and no model calls, so the same state and query must give
    the same answer every time — otherwise a digest is unreproducible."""
    store = _company(tmp_path)
    for n in (1, 2, 3):
        shift = _shift(store, n)
        _artifact(store, shift, f"artifacts/d{n}.md", f"Doc {n}", "pricing and margin")
        store.close_shift(shift.id, status="completed", summary="s")

    once = [m.id for m in recall(store.state, "pricing", limit=5)]
    twice = [m.id for m in recall(store.state, "pricing", limit=5)]
    assert once == twice


def test_the_digest_still_fits_its_budget(tmp_path) -> None:
    from werkhaus.brain.digest import render_digest

    store = _company(tmp_path)
    for n in range(1, 15):
        shift = _shift(store, n)
        _artifact(store, shift, f"artifacts/d{n}.md", f"Document {n}", "pricing " * 40)
        store.close_shift(shift.id, status="completed", summary="s")

    text = render_digest(
        store, role_id="researcher", shift_number=15, budget_tokens=1200,
        focus="pricing",
    )
    assert len(text) / 4 <= 1400, "recall must respect the budget, not blow past it"


def test_association_recalls_what_words_cannot(tmp_path) -> None:
    """The load-bearing test: does the Hebbian layer add anything over plain
    lexical search, or is it decoration?

    A document about courier breakage shares no words with a question about
    monthly pricing. It is nonetheless the right thing to recall, because this
    company has worked on the two together every time — and what a parcel costs
    to send is exactly what decides what you can charge. Lexical search cannot
    find it. Association can.
    """
    from werkhaus.brain import memory as mem

    store = _company(tmp_path)
    for n in (1, 2, 3, 4):
        shift = _shift(store, n)
        _artifact(store, shift, f"artifacts/p{n}.md", f"Price study {n}",
                  "what six competitors charge per month")
        _artifact(store, shift, f"artifacts/ship{n}.md", f"Courier quotes {n}",
                  "breakage and packing for fragile goods")
        store.close_shift(shift.id, status="completed", summary="s")
    for n in range(5, 10):
        shift = _shift(store, n)
        _artifact(
            store, shift, f"artifacts/b{n}.md", f"Brand voice {n}", "tone and logo"
        )
        store.close_shift(shift.id, status="completed", summary="s")

    query = "what should we charge per month"
    linked = {m.id for m in recall(store.state, query, limit=5)}

    spread = mem.SPREAD
    try:
        mem.SPREAD = 0.0  # base activation only, i.e. plain lexical search
        lexical = {m.id for m in recall(store.state, query, limit=5)}
    finally:
        mem.SPREAD = spread

    gained = linked - lexical
    assert gained, "the Hebbian layer added nothing over lexical search"
    recovered = [m for m in memories(store.state).values() if m.id in gained]
    assert any("Courier" in m.text for m in recovered), (
        f"expected the associated cost work, got {[m.text for m in recovered]}"
    )
