"""The contract, proven against the engine that ships.

Anything asserted here is what the dashboard is allowed to assume. The engine
runs for real — real brain, real budget layers, real halt semantics — driven by
a scripted model, so these are the true code paths and not a rehearsal of them.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from tests.contract.conftest import (
    make_engine,
    prepare_workspace,
    started,
    wait_idle,
)
from werkhaus.contract.models import CharterPatch, CompanyStatus


# ----------------------------------------------------------------------- tests
async def test_company_lifecycle(tmp_path) -> None:
    engine = await started(tmp_path)
    try:
        company = await engine.create_company("A booking tool for mobile dog groomers")
        assert company.status in (CompanyStatus.IDLE, CompanyStatus.DRAFT)
        assert company.charter.idea == "A booking tool for mobile dog groomers"
        assert len(company.roster) == 8

        fetched = await engine.get_company(company.id)
        assert fetched.id == company.id
        assert [c.id for c in await engine.list_companies()] == [company.id]

        patched = await engine.update_charter(
            company.id, CharterPatch(audience="Mobile groomers who work alone")
        )
        assert patched.charter.audience == "Mobile groomers who work alone"
    finally:
        await engine.aclose()


async def test_a_shift_produces_artifacts_and_events(tmp_path) -> None:
    engine = await started(tmp_path)
    try:
        company = await engine.create_company("A booking tool for mobile dog groomers")
        prepare_workspace(tmp_path, company.id)

        shift = await engine.start_shift(company.id)
        assert shift.number == 1

        done = await wait_idle(engine, company.id)
        assert done.status is CompanyStatus.IDLE
        assert done.shift_count == 1

        shifts = await engine.list_shifts(company.id)
        assert shifts[0].status.value == "completed"
        assert shifts[0].summary

        artifacts = await engine.list_artifacts(company.id)
        assert len(artifacts) >= 1
        for artifact in artifacts:
            if artifact.confidence == "sourced":
                assert artifact.sources

        assert done.progress.percent > 0
        assert done.progress.whats_missing

        # The event stream is replayable, gap-free, and strictly ordered.
        events = await engine.replay(company.id, 0, 2000)
        assert events
        seqs = [e.seq for e in events]
        assert seqs == sorted(seqs)
        assert len(set(seqs)) == len(seqs)
        kinds = {e.kind.value for e in events}
        assert "shift.started" in kinds
        assert "artifact.created" in kinds
        assert "shift.completed" in kinds
    finally:
        await engine.aclose()


async def test_halt_is_fast_and_final(tmp_path) -> None:
    engine = await started(tmp_path)
    try:
        company = await engine.create_company("x")
        prepare_workspace(tmp_path, company.id)
        await engine.start_shift(company.id)

        began = time.monotonic()
        halted = await engine.halt(company.id)
        elapsed = time.monotonic() - began

        assert elapsed < 2.0, f"halt took {elapsed:.2f}s"
        assert halted.status is CompanyStatus.HALTED

        # No shift is left running, whatever the race between halt and finish.
        for shift in await engine.list_shifts(company.id):
            assert shift.status.value != "running"

        # A halted company refuses work, then resumes cleanly.
        from werkhaus.contract.errors import CompanyHalted

        with pytest.raises(CompanyHalted):
            await engine.start_shift(company.id)
        resumed = await engine.resume(company.id)
        assert resumed.status is CompanyStatus.IDLE
    finally:
        await engine.aclose()


async def test_cold_reload_loses_nothing(tmp_path) -> None:
    engine = await started(tmp_path)
    company = await engine.create_company("A booking tool for mobile dog groomers")
    prepare_workspace(tmp_path, company.id)
    await engine.start_shift(company.id)
    await wait_idle(engine, company.id)
    artifacts_before = await engine.list_artifacts(company.id)
    events_before = await engine.replay(company.id, 0, 2000)
    await engine.aclose()

    reloaded = await started(tmp_path)
    try:
        company_after = await reloaded.get_company(company.id)
        assert company_after.status is CompanyStatus.IDLE
        assert company_after.shift_count == 1
        assert len(await reloaded.list_artifacts(company.id)) == len(artifacts_before)
        events_after = await reloaded.replay(company.id, 0, 2000)
        assert [e.seq for e in events_after][: len(events_before)] == [
            e.seq for e in events_before
        ]
    finally:
        await reloaded.aclose()


async def test_full_auto_chains_the_next_shift(tmp_path) -> None:
    """On the auto side of the dial a finished shift starts the next one,
    bounded by the chain limit — never an unbounded loop."""
    engine = make_engine(tmp_path)
    await engine.start()
    try:
        company = await engine.create_company("x")
        prepare_workspace(tmp_path, company.id)
        await engine.update_charter(company.id, CharterPatch(autonomy="full_auto"))
        await engine.start_shift(company.id)

        deadline = time.monotonic() + 30
        count = 0
        while time.monotonic() < deadline:
            count = (await engine.get_company(company.id)).shift_count
            if count >= 2:
                break
            await asyncio.sleep(0.1)
        assert count >= 2, "full_auto never chained a second shift"
        await engine.halt(company.id)
    finally:
        await engine.aclose()


async def test_balanced_never_chains(tmp_path) -> None:
    engine = make_engine(tmp_path)
    await engine.start()
    try:
        company = await engine.create_company("x")  # autonomy defaults balanced
        prepare_workspace(tmp_path, company.id)
        await engine.start_shift(company.id)
        await wait_idle(engine, company.id)
        await asyncio.sleep(1.0)
        assert (await engine.get_company(company.id)).shift_count == 1
    finally:
        await engine.aclose()


async def test_a_shift_that_runs_out_of_turns_still_files_something(tmp_path) -> None:
    """The reserve that makes rule 7 real.

    An employee cannot see her own turn counter, so "stop early enough to write
    it up" is not something she can be asked to do — and a shift that reads for
    eighty turns and files nothing is the one outcome a founder cannot use. The
    turn budget is split: research runs out first, and the turns held back buy
    the write-up.
    """
    import json

    from openhands.sdk import Message, TextContent
    from openhands.sdk.llm.message import MessageToolCall
    from openhands.sdk.testing import TestLLM

    from tests.contract.conftest import RESEARCH
    from werkhaus.engines.openhands.shift import RESEARCH_ITERATIONS

    def call(i: int, name: str, args: dict, say: str) -> Message:
        return Message(
            role="assistant",
            content=[TextContent(text=say)],
            tool_calls=[
                MessageToolCall(
                    id=f"call_{i}",
                    name=name,
                    arguments=json.dumps(args),
                    origin="completion",
                )
            ],
        )

    # Research that never converges. Each turn is distinct so this reads as an
    # employee still working, not as the SDK's stuck detector's idea of a loop.
    turns = [
        call(i, "werkhaus_brain", {"op": "add_task", "title": f"Open question {i}"},
             "Still looking.")
        for i in range(RESEARCH_ITERATIONS + 1)
    ]
    # Then, and only when told the research time is gone, the document.
    turns.append(
        call(
            9000,
            "werkhaus_brain",
            {
                "op": "record_artifact",
                "path": RESEARCH,
                "title": "What I found before time ran out",
                "summary": "Partial, labelled honestly.",
                "confidence": "inferred",
                "sources": [],
            },
            "Writing up what I have.",
        )
    )
    turns.append(
        Message(role="assistant", content=[TextContent(text="Filed what I had.")])
    )

    engine = await started(tmp_path, llm=lambda usage_id: TestLLM.from_messages(
        turns, usage_id=usage_id
    ))
    try:
        company = await engine.create_company("A booking tool for mobile dog groomers")
        prepare_workspace(tmp_path, company.id)
        await engine.start_shift(company.id)
        await wait_idle(engine, company.id)

        # The shift ran out of turns — and still came back with a document.
        artifacts = await engine.list_artifacts(company.id)
        assert [a.title for a in artifacts] == ["What I found before time ran out"]

        # Which makes it a shift that worked, not one that failed: the turn
        # limit was reached, but the founder still got the thing they were
        # promised.
        shift = (await engine.list_shifts(company.id))[0]
        assert shift.status.value == "completed", shift.failure_reason
    finally:
        await engine.aclose()
