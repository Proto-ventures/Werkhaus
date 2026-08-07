"""Contract tests.

Written to be parametrized over ``[StubEngine, OpenHandsEngine]`` in M3. Anything
asserted here is, by construction, drop-in swappable — which is the whole bet of
building the dashboard first.

Everything runs at high ``speed`` so the suite is fast; the *behaviour* under test
is identical at speed 1.0, which is what the UI is developed against.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path

import pytest

from werkhaus.contract.events import ShiftEventKind as K
from werkhaus.contract.models import CompanyStatus, ShiftStatus
from werkhaus.engines.stub.engine import StubEngine
from werkhaus.engines.stub.scenario import list_scenarios

FAST = 400.0


async def make_engine(tmp_path: Path, scenario: str = "happy") -> StubEngine:
    engine = StubEngine(root=tmp_path, seed=42, scenario=scenario, speed=FAST)
    await engine.start()
    return engine


async def run_to_completion(engine: StubEngine, cid: str, timeout: float = 30.0):
    state = engine._companies[cid]
    handle = state.task_handle
    assert handle is not None
    await asyncio.wait_for(asyncio.shield(handle), timeout=timeout)
    return await engine.list_shifts(cid)


# ---------------------------------------------------------------------- scenarios
def test_every_scenario_file_parses() -> None:
    """A scenario that only fails to load at demo time is worse than no scenario."""
    from werkhaus.engines.stub.scenario import load_scenario

    names = list_scenarios()
    assert set(names) == {
        "budget_blowup",
        "firehose",
        "happy",
        "needs_attention",
        "role_failure",
    }
    for name in names:
        assert load_scenario(name).name == name


async def test_happy_shift_produces_real_work(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path)
    company = await engine.create_company("A ceramics subscription box")
    await engine.start_shift(company.id)
    shifts = await run_to_completion(engine, company.id)

    assert shifts[0].status is ShiftStatus.COMPLETED
    assert shifts[0].summary

    artifacts = await engine.list_artifacts(company.id)
    assert len(artifacts) >= 6
    # The anti-slop hook: provenance is structural, not a prompt request.
    assert all(a.confidence in ("sourced", "inferred", "assumption") for a in artifacts)
    sourced = [a for a in artifacts if a.confidence == "sourced"]
    assert sourced and all(a.sources for a in sourced), (
        "an artifact claiming to be sourced must carry the URLs it was sourced from"
    )

    decisions = await engine.list_decisions(company.id)
    assert decisions and all(d.alternatives_rejected for d in decisions), (
        "a decision with no rejected alternatives is a preference, not a decision"
    )

    # The critic always runs, and her output is browsable, not just a log line.
    objections = await engine.list_objections(company.id)
    assert len(objections) >= 3
    assert any(d.contested_by for d in decisions)

    final = await engine.get_company(company.id)
    assert final.status is CompanyStatus.IDLE
    assert final.progress.percent > 0
    assert final.progress.whats_missing
    await engine.aclose()


async def test_budget_cap_halts_the_company_mid_shift(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path, "budget_blowup")
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    shifts = await run_to_completion(engine, company.id)

    assert shifts[0].status is ShiftStatus.BUDGET_EXCEEDED
    final = await engine.get_company(company.id)
    assert final.status is CompanyStatus.HALTED
    assert final.budget.spent >= final.budget.cap

    # A halted company cannot quietly start spending again.
    from werkhaus.contract.errors import CompanyHalted

    with pytest.raises(CompanyHalted):
        await engine.start_shift(company.id)
    await engine.aclose()


async def test_one_role_failing_does_not_sink_the_shift(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path, "role_failure")
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    shifts = await run_to_completion(engine, company.id)

    assert shifts[0].status is ShiftStatus.COMPLETED
    events = await engine.replay(company.id, 0, limit=5000)
    failed = [e for e in events if e.kind is K.ROLE_FAILED]
    assert len(failed) == 1
    # The user is told what happened without being shown a build log.
    assert "hit a problem" in failed[0].text
    assert "Traceback" not in (failed[0].detail or "")

    # The other two employees still delivered.
    assert len(await engine.list_artifacts(company.id)) == 2
    assert await engine.list_objections(company.id)
    await engine.aclose()


async def test_attention_blocks_until_answered(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path, "needs_attention")
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    shifts = await run_to_completion(engine, company.id)

    assert shifts[0].status is ShiftStatus.COMPLETED
    blocked = await engine.get_company(company.id)
    assert blocked.status is CompanyStatus.BLOCKED, (
        "a waiting company must not look idle"
    )

    pending = await engine.list_attention(company.id)
    assert len(pending) == 1 and pending[0].answered_at is None
    assert pending[0].options

    await engine.answer_attention(company.id, pending[0].id, pending[0].options[0])
    answered = await engine.list_attention(company.id)
    assert answered[0].answered_at is not None
    assert answered[0].answer == pending[0].options[0]
    await engine.aclose()


async def test_firehose_emits_thousands_of_events(tmp_path: Path) -> None:
    """The UI must meet real volume before shipping, not after."""
    engine = await make_engine(tmp_path, "firehose")
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id, timeout=120.0)

    events = await engine.replay(company.id, 0, limit=100_000)
    assert len(events) > 2000, f"only {len(events)} events — not a firehose"
    await engine.aclose()


# ------------------------------------------------------------------- streaming
async def test_stream_has_no_gaps_or_duplicates(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path)
    company = await engine.create_company("x")

    seen: list[int] = []

    async def consume() -> None:
        async for event in engine.stream(company.id):
            seen.append(event.seq)

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.05)
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id)
    await asyncio.sleep(0.1)
    consumer.cancel()

    assert seen == sorted(seen), "events arrived out of order"
    assert len(seen) == len(set(seen)), "an event was delivered twice"
    assert seen == list(range(seen[0], seen[0] + len(seen))), "a seq is missing"
    await engine.aclose()


async def test_since_seq_resumes_exactly_where_it_left_off(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path)
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id)

    everything = await engine.replay(company.id, 0, limit=10_000)
    midpoint = everything[len(everything) // 2].seq
    resumed = await engine.replay(company.id, midpoint, limit=10_000)

    assert resumed[0].seq == midpoint + 1
    assert [e.seq for e in resumed] == [e.seq for e in everything if e.seq > midpoint]
    await engine.aclose()


async def test_cold_load_reconstructs_without_a_socket(tmp_path: Path) -> None:
    """"Leave and come back" must work with no live connection at all."""
    engine = await make_engine(tmp_path)
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id)
    live_count = len(await engine.replay(company.id, 0, limit=10_000))
    await engine.aclose()

    restarted = StubEngine(root=tmp_path, seed=42, speed=FAST)
    await restarted.start()
    assert len(await restarted.replay(company.id, 0, limit=10_000)) == live_count
    assert len(await restarted.list_artifacts(company.id)) >= 6
    assert (await restarted.get_company(company.id)).progress.percent > 0
    await restarted.aclose()


# --------------------------------------------------------------------- control
async def test_halt_is_immediate(tmp_path: Path) -> None:
    """The kill switch is a trust feature. Two seconds, tested."""
    engine = StubEngine(root=tmp_path, seed=42, scenario="happy", speed=1.0)
    await engine.start()
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await asyncio.sleep(0.2)

    loop = asyncio.get_running_loop()
    started = loop.time()
    halted = await engine.halt(company.id)
    elapsed = loop.time() - started

    assert elapsed < 2.0, f"halt took {elapsed:.2f}s"
    assert halted.status is CompanyStatus.HALTED
    shifts = await engine.list_shifts(company.id)
    assert shifts[0].status is ShiftStatus.ABORTED
    # Partial work survives; the durable log means "nothing was lost" is literal.
    assert await engine.replay(company.id, 0, limit=10_000)
    await engine.aclose()


async def test_restart_mid_shift_loses_nothing(tmp_path: Path) -> None:
    """The M2 headline: kill it mid-shift and the company is intact.

    Nothing is flushed on the way out — the process simply stops existing, which
    is what actually happens. Everything that survives does so because it was
    already fsynced to the log at the moment it happened.
    """
    engine = StubEngine(root=tmp_path, seed=42, scenario="happy", speed=8.0)
    await engine.start()
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    # Let real work land: tasks claimed, at least one document written.
    await asyncio.sleep(2.0)

    brain = engine._companies[company.id].brain
    tasks_before = len(brain.state.tasks)
    events_before = len(await engine.replay(company.id, 0, limit=10_000))
    assert tasks_before > 0, "test did not get far enough to be meaningful"

    # The process dies. No aclose(), no flush, no cooperation.
    engine._companies[company.id].task_handle.cancel()  # type: ignore[union-attr]
    await asyncio.sleep(0)
    del engine

    restarted = StubEngine(root=tmp_path, seed=42, speed=FAST)
    await restarted.start()

    shifts = await restarted.list_shifts(company.id)
    assert shifts[0].status is ShiftStatus.ABORTED
    assert "restarted" in (shifts[0].failure_reason or "")
    assert (await restarted.get_company(company.id)).status is not CompanyStatus.WORKING

    # The backlog and the history survived the crash.
    assert len(restarted._companies[company.id].brain.state.tasks) == tasks_before
    assert len(await restarted.replay(company.id, 0, limit=10_000)) >= events_before

    # And the user is told, in their own words, rather than shown a spinner.
    recent = await restarted.replay(company.id, events_before, limit=100)
    assert any("was interrupted" in e.text for e in recent)
    assert any("Nothing was lost" in e.text for e in recent)

    # The company is usable again immediately.
    await restarted.start_shift(company.id)
    await restarted.aclose()


async def test_raising_the_cap_unhalts(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path, "budget_blowup")
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id)

    assert (await engine.get_company(company.id)).status is CompanyStatus.HALTED
    await engine.set_budget_cap(company.id, Decimal("50.00"))
    assert (await engine.get_company(company.id)).status is CompanyStatus.IDLE
    await engine.aclose()


async def test_share_links_fail_closed_until_scanned(tmp_path: Path) -> None:
    """The public route serves nothing that has not passed the scan.

    ``publish`` marks a link clean only after the scanner returns nothing, so the
    way to test the gate itself is to forge a link that never went through it —
    the shape a bug, a rollback, or a hand-edited state file would produce.
    """
    from werkhaus.contract.errors import NotFound
    from werkhaus.contract.models import ShareOptions

    engine = await make_engine(tmp_path)
    company = await engine.create_company("x")
    link = await engine.publish(company.id, ShareOptions())
    assert link.scanned_clean_at is not None
    assert await engine.get_public_snapshot(link.token)

    brain = engine._companies[company.id].brain
    revoked = {"revoked_at": "2026-01-01T00:00:00+00:00"}
    for bad in ({"scanned_clean_at": None}, revoked):
        brain.record_metric(
            "share", link.model_copy(update=bad).model_dump(mode="json")
        )
        with pytest.raises(NotFound):
            await engine.get_public_snapshot(link.token)
    await engine.aclose()


async def test_artifact_reads_stay_inside_the_company(tmp_path: Path) -> None:
    engine = await make_engine(tmp_path)
    company = await engine.create_company("x")
    await engine.start_shift(company.id)
    await run_to_completion(engine, company.id)

    for artifact in await engine.list_artifacts(company.id):
        assert not artifact.path.startswith("/"), "no absolute path may cross the API"
        assert ".." not in artifact.path
        content, mime = await engine.read_artifact(artifact.id)
        assert mime
        if artifact.kind != "site":
            assert content, f"{artifact.path} read back empty"
    await engine.aclose()
