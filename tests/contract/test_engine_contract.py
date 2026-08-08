"""The contract, proven against both engines.

Anything asserted here is drop-in swappable by construction: the same test body
runs against the stub and against the real engine (with a scripted model, no
network). This file is why the dashboard needed no changes when the real engine
arrived.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

import pytest

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from werkhaus.contract.engine import Engine  # noqa: E402
from werkhaus.contract.models import CharterPatch, CompanyStatus  # noqa: E402


def _scripted_llm(usage_id: str):
    """A fresh scripted model per shift: file the document, then finish.

    The document itself is pre-written by the test (the real Maya writes it
    with her file editor; scripting absolute paths into a canned model is
    noise, not coverage — the file-editor interplay is covered in sdk_seams).
    """
    from openhands.sdk import Message, TextContent
    from openhands.sdk.llm.message import MessageToolCall
    from openhands.sdk.testing import TestLLM

    return TestLLM.from_messages(
        [
            Message(
                role="assistant",
                content=[TextContent(text="Filing what I found.")],
                tool_calls=[
                    MessageToolCall(
                        id="call_1",
                        name="werkhaus_brain",
                        arguments=json.dumps(
                            {
                                "op": "record_artifact",
                                "path": "market-research.md",
                                "title": "Market research",
                                "summary": "What the research found.",
                                "confidence": "inferred",
                                "sources": [],
                            }
                        ),
                        origin="completion",
                    )
                ],
            ),
            Message(
                role="assistant",
                content=[TextContent(text="Research is filed. Two findings.")],
            ),
        ],
        usage_id=usage_id,
    )


def _make(kind: str, root: Path) -> Engine:
    if kind == "stub":
        from werkhaus.engines.stub.engine import StubEngine

        return StubEngine(root=root, seed=42, scenario="happy", speed=400.0)
    from werkhaus.engines.openhands.engine import OpenHandsEngine

    return OpenHandsEngine(root=root, llm_factory=_scripted_llm, browsing=False)


@pytest.fixture(params=["stub", "openhands"])
def kind(request) -> str:
    return request.param


async def _started(kind: str, root: Path) -> Engine:
    engine = _make(kind, root)
    await engine.start()
    return engine


def _prepare_shift(kind: str, root: Path, cid: str) -> None:
    """What the scripted model needs on disk before its shift."""
    if kind == "openhands":
        doc = root / cid / "workspace" / "market-research.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# Market research\n\nFindings.\n", encoding="utf-8")


async def _wait_done(engine: Engine, cid: str, timeout: float = 20.0):
    """Engine-neutral: a shift is over when the company stops working."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        company = await engine.get_company(cid)
        if company.status is not CompanyStatus.WORKING:
            return company
        await asyncio.sleep(0.05)
    raise AssertionError("shift never finished")


# ----------------------------------------------------------------------- tests
async def test_company_lifecycle(kind, tmp_path) -> None:
    engine = await _started(kind, tmp_path)
    try:
        company = await engine.create_company("A ceramics subscription box")
        assert company.status in (CompanyStatus.IDLE, CompanyStatus.DRAFT)
        assert company.charter.idea == "A ceramics subscription box"
        assert len(company.roster) == 8

        fetched = await engine.get_company(company.id)
        assert fetched.id == company.id
        assert [c.id for c in await engine.list_companies()] == [company.id]

        patched = await engine.update_charter(
            company.id, CharterPatch(audience="People in small flats")
        )
        assert patched.charter.audience == "People in small flats"
    finally:
        await engine.aclose()


async def test_a_shift_produces_artifacts_and_events(kind, tmp_path) -> None:
    engine = await _started(kind, tmp_path)
    try:
        company = await engine.create_company("A ceramics subscription box")
        _prepare_shift(kind, tmp_path, company.id)

        shift = await engine.start_shift(company.id)
        assert shift.number == 1

        done = await _wait_done(engine, company.id)
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


async def test_halt_is_fast_and_final(kind, tmp_path) -> None:
    engine = await _started(kind, tmp_path)
    try:
        company = await engine.create_company("x")
        _prepare_shift(kind, tmp_path, company.id)
        await engine.start_shift(company.id)

        started = time.monotonic()
        halted = await engine.halt(company.id)
        elapsed = time.monotonic() - started

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


async def test_cold_reload_loses_nothing(kind, tmp_path) -> None:
    engine = await _started(kind, tmp_path)
    company = await engine.create_company("A ceramics subscription box")
    _prepare_shift(kind, tmp_path, company.id)
    await engine.start_shift(company.id)
    await _wait_done(engine, company.id)
    artifacts_before = await engine.list_artifacts(company.id)
    events_before = await engine.replay(company.id, 0, 2000)
    await engine.aclose()

    reloaded = await _started(kind, tmp_path)
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
    engine = _make("stub", tmp_path)
    await engine.start()
    try:
        company = await engine.create_company("x")
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
    engine = _make("stub", tmp_path)
    await engine.start()
    try:
        company = await engine.create_company("x")  # autonomy defaults balanced
        await engine.start_shift(company.id)
        await _wait_done(engine, company.id)
        await asyncio.sleep(1.0)
        assert (await engine.get_company(company.id)).shift_count == 1
    finally:
        await engine.aclose()
