"""The durability layer.

The claim M2 makes is "nothing was lost". These tests are what makes that claim
checkable rather than reassuring.
"""

from __future__ import annotations

import json
import threading
from decimal import Decimal
from pathlib import Path

import pytest

from werkhaus.brain.digest import render_digest
from werkhaus.brain.store import BrainStore
from werkhaus.contract.errors import (
    ArtifactOwnedByAnotherRole,
    TaskAlreadyClaimed,
)
from werkhaus.contract.models import ArtifactKind, Charter, Progress, ShiftStatus


def make(tmp_path: Path) -> BrainStore:
    store = BrainStore(tmp_path / "co_test", "co_test")
    store.set_charter(
        Charter(
            idea="A ceramics subscription box",
            one_liner="One hand-thrown object a month, from a named potter.",
            audience="UK apartment-dwellers who buy few objects",
            success_looks_like="A live waitlist with 3 real signups",
            constraints=["UK only for the first year"],
        ),
        "Northwind Ceramics",
    )
    return store


# ------------------------------------------------------------------- the log
def test_the_log_is_the_source_of_truth(tmp_path: Path) -> None:
    """Delete every projection; nothing is lost."""
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=["Check the price"])
    task = store.add_task(title="Validate £29", shift_id=shift.id, actor="chief")
    store.claim_task(task.id, role_id="researcher", shift_id=shift.id)
    store.record_decision(
        title="Price at £29",
        rationale="Every box that names its maker sits above £29.",
        alternatives_rejected=["£9"],
        role_id="strategist",
        shift_id=shift.id,
    )

    for projection in store.paths.projections.glob("*"):
        projection.unlink()

    reopened = BrainStore(store.paths.root, "co_test")
    assert reopened.state.name == "Northwind Ceramics"
    assert len(reopened.state.tasks) == 1
    assert len(reopened.state.decisions) == 1
    assert reopened.state.charter is not None

    reopened.rebuild()
    assert store.paths.backlog.exists()
    assert store.paths.decisions_md.exists()
    assert store.paths.artifacts_index.exists()


def test_a_torn_final_line_is_survivable(tmp_path: Path) -> None:
    """The exact shape of a crash: the process died mid-write."""
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.add_task(title="Kept", shift_id=shift.id, actor="chief")

    # Simulate a partial append.
    with store.paths.log.open("a", encoding="utf-8") as handle:
        handle.write('{"seq": 99, "op": "add_task", "data": {"id": "tk_broke"')

    reopened = BrainStore(store.paths.root, "co_test")
    titles = [t.title for t in reopened.state.tasks.values()]
    assert titles == ["Kept"], "the intact prefix must survive"

    # And the store keeps working afterwards.
    reopened.add_task(title="After the crash", shift_id=shift.id, actor="chief")
    assert len(BrainStore(store.paths.root, "co_test").state.tasks) == 2


def test_projections_are_pure_functions_of_the_log(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.add_task(title="One", shift_id=shift.id, actor="chief")
    store.add_task(title="Two", shift_id=shift.id, actor="chief")
    first = store.paths.backlog.read_text()

    store.paths.backlog.write_text("corrupted: [")
    store.rebuild()
    assert store.paths.backlog.read_text() == first


# ------------------------------------------------------------ concurrency
def test_two_employees_cannot_claim_the_same_task(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    task = store.add_task(title="Contested", shift_id=shift.id, actor="chief")

    store.claim_task(task.id, role_id="researcher", shift_id=shift.id)
    with pytest.raises(TaskAlreadyClaimed) as caught:
        store.claim_task(task.id, role_id="growth", shift_id=shift.id)
    # The loser gets something it can act on, not a stack trace.
    assert "already took" in caught.value.message


def test_parallel_claims_produce_exactly_one_winner(tmp_path: Path) -> None:
    """The real shape of the race: threads, as in M3's role conversations."""
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    task = store.add_task(title="Hotly contested", shift_id=shift.id, actor="chief")

    winners: list[str] = []
    losers: list[str] = []
    barrier = threading.Barrier(8)

    def attempt(role: str) -> None:
        barrier.wait()
        try:
            store.claim_task(task.id, role_id=role, shift_id=shift.id)
            winners.append(role)
        except TaskAlreadyClaimed:
            losers.append(role)

    threads = [
        threading.Thread(target=attempt, args=(f"role{i}",)) for i in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(winners) == 1, f"{len(winners)} employees claimed the same task"
    assert len(losers) == 7


def test_concurrent_appends_do_not_corrupt_the_log(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])

    def add(n: int) -> None:
        for i in range(10):
            store.add_task(title=f"task {n}-{i}", shift_id=shift.id, actor=f"r{n}")

    threads = [threading.Thread(target=add, args=(n,)) for n in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Every line parses, every seq is unique.
    lines = store.paths.log.read_text().strip().splitlines()
    entries = [json.loads(line) for line in lines]
    seqs = [e["seq"] for e in entries]
    assert len(seqs) == len(set(seqs)), "a sequence number was reused"
    assert len(BrainStore(store.paths.root, "co_test").state.tasks) == 60


def test_an_artifact_has_one_owner_per_shift(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.record_artifact(
        path="artifacts/research.md", title="Research", summary="s",
        kind=ArtifactKind.DOC, confidence="inferred", sources=[],
        role_id="researcher", shift_id=shift.id,
    )
    with pytest.raises(ArtifactOwnedByAnotherRole):
        store.record_artifact(
            path="artifacts/research.md", title="Research", summary="s",
            kind=ArtifactKind.DOC, confidence="inferred", sources=[],
            role_id="growth", shift_id=shift.id,
        )
    # The same employee revising their own work is fine, and versions.
    again = store.record_artifact(
        path="artifacts/research.md", title="Research v2", summary="s",
        kind=ArtifactKind.DOC, confidence="inferred", sources=[],
        role_id="researcher", shift_id=shift.id,
    )
    assert again.version == 2
    assert len(store.state.artifacts) == 1, "the superseded version was not replaced"


def test_artifact_paths_must_be_company_relative(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    for bad in ("/etc/passwd", "../../secrets.md"):
        with pytest.raises(ValueError):
            store.record_artifact(
                path=bad, title="x", summary="s", kind=ArtifactKind.DOC,
                confidence="assumption", sources=[], role_id="r", shift_id=shift.id,
            )


# ------------------------------------------------------------------ recovery
def test_running_shifts_are_closed_on_restart(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=["Something"])
    store.add_task(title="Survives", shift_id=shift.id, actor="chief")

    reopened = BrainStore(store.paths.root, "co_test")
    assert reopened.state.shifts[shift.id].status is ShiftStatus.RUNNING
    aborted = reopened.abort_running_shifts("Werkhaus restarted.")

    assert len(aborted) == 1
    assert aborted[0].status is ShiftStatus.ABORTED
    assert "restarted" in (aborted[0].failure_reason or "")
    # The backlog is untouched by the interruption.
    assert len(reopened.state.tasks) == 1


def test_money_survives_a_reload(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.record_cost(Decimal("1.50"), role_id="researcher", shift_id=shift.id)
    store.record_cost(Decimal("3.00"), role_id="engineer", shift_id=shift.id)

    reopened = BrainStore(store.paths.root, "co_test")
    assert reopened.state.spent == Decimal("4.50")
    assert len(reopened.state.ledger) == 2


# -------------------------------------------------------------------- digest
def test_digest_leads_with_what_matters_and_truncates_the_rest(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.set_progress(
        Progress(
            percent=64,
            headline="Price is settled.",
            whats_missing=["No evidence"],
        )
    )
    for i in range(40):
        store.record_artifact(
            path=f"artifacts/doc{i}.md", title=f"Document {i}", summary="s",
            kind=ArtifactKind.DOC, confidence="assumption", sources=[],
            role_id="researcher", shift_id=shift.id,
        )

    full = render_digest(store, role_id="researcher", budget_tokens=4000)
    tight = render_digest(store, role_id="researcher", budget_tokens=120)

    # The charter and the standing survive any budget; the reading list does not.
    assert "Northwind Ceramics" in tight
    assert "Done means:" in tight
    assert len(tight) < len(full)
    assert "Document 39" in full and "Document 39" not in tight
    assert "UK only for the first year" in tight, (
        "a rule must never be truncated away"
    )


def test_digest_names_confidence_so_nobody_trusts_a_guess(tmp_path: Path) -> None:
    store = make(tmp_path)
    shift = store.open_shift(number=1, agenda=[])
    store.record_artifact(
        path="artifacts/econ.md", title="Unit economics", summary="s",
        kind=ArtifactKind.TABLE, confidence="assumption", sources=[],
        role_id="analyst", shift_id=shift.id,
    )
    digest = render_digest(store, role_id="strategist", budget_tokens=4000)
    assert "(assumption)" in digest
