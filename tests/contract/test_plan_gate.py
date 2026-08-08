"""The plan gate.

The free tier is the trial, so the rules here are as much product as code: a
shift that produced nothing is free, the allowance is account-wide, and the
dial's expensive ends are not on offer to someone who cannot afford them.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from werkhaus.contract.errors import OutOfShifts
from werkhaus.contract.models import CompanyStatus
from werkhaus.contract.plan import (
    PLANS,
    build_allowance,
    next_refill_at,
    shifts_left,
)
from werkhaus.engines.stub.engine import StubEngine

FREE = PLANS["free"]


def _engine(root: Path) -> StubEngine:
    return StubEngine(root=root, seed=42, scenario="happy", speed=400.0)


async def _run_one(engine: StubEngine, cid: str) -> None:
    await engine.start_shift(cid)
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if (await engine.get_company(cid)).status is not CompanyStatus.WORKING:
            return
        await asyncio.sleep(0.05)
    raise AssertionError("shift never finished")


# ------------------------------------------------------------------ arithmetic
def test_the_grant_is_the_arc_not_a_round_number() -> None:
    """Three shifts is a promise: enough to reach something showable. If this
    ever drops below the arc, the trial ends before the payoff and the number
    should be argued about here, in the open."""
    assert FREE.shift_grant == 3
    assert FREE.byok is False


def test_refills_accrue_weekly_but_do_not_stockpile() -> None:
    joined = datetime(2026, 1, 1, tzinfo=UTC)
    # Used everything on day one.
    assert shifts_left(FREE, joined, joined, used=3) == 0
    # A week later, one shift back.
    assert shifts_left(FREE, joined, joined + timedelta(days=7), used=3) == 1
    assert shifts_left(FREE, joined, joined + timedelta(days=21), used=3) == 3
    # A year of silence is not a year of shifts.
    assert shifts_left(FREE, joined, joined + timedelta(days=365), used=3) == 3
    assert next_refill_at(FREE, joined, joined) == joined + timedelta(days=7)


def test_a_paid_plan_is_uncounted() -> None:
    allowance = build_allowance(PLANS["pro"], datetime.now(UTC), used=99)
    assert allowance.shifts_left is None
    assert allowance.byok is True
    assert allowance.next_refill_at is None


def test_the_free_dial_omits_both_expensive_ends() -> None:
    """Full-auto can chain away a trial unattended; full-control can spend it
    on planning and never produce the thing that sells the product."""
    assert "balanced" in FREE.autonomy
    assert "full_auto" not in FREE.autonomy
    assert "full_control" not in FREE.autonomy
    assert set(FREE.autonomy) < set(PLANS["pro"].autonomy)


# ----------------------------------------------------------------- the gate
async def test_free_runs_out_after_its_grant(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WERKHAUS_PLAN", "free")
    engine = _engine(tmp_path)
    await engine.start()
    try:
        company = await engine.create_company("A ceramics subscription box")
        assert (await engine.get_allowance()).shifts_left == 3

        for expected in (2, 1, 0):
            await _run_one(engine, company.id)
            assert (await engine.get_allowance()).shifts_left == expected

        with pytest.raises(OutOfShifts) as caught:
            await engine.start_shift(company.id)
        assert caught.value.hint and "upgrade" in caught.value.hint.lower()
    finally:
        await engine.aclose()


async def test_the_allowance_is_not_refilled_by_making_a_new_company(
    tmp_path, monkeypatch
) -> None:
    """The obvious exploit. Allowance is account-wide precisely because a
    per-company one is refilled by pressing a button."""
    monkeypatch.setenv("WERKHAUS_PLAN", "free")
    engine = _engine(tmp_path)
    await engine.start()
    try:
        first = await engine.create_company("A ceramics subscription box")
        for _ in range(3):
            await _run_one(engine, first.id)
        assert (await engine.get_allowance()).shifts_left == 0

        second = await engine.create_company("Something else entirely")
        assert (await engine.get_allowance()).shifts_left == 0
        with pytest.raises(OutOfShifts):
            await engine.start_shift(second.id)
    finally:
        await engine.aclose()


async def test_a_shift_that_produced_nothing_is_not_charged(
    tmp_path, monkeypatch
) -> None:
    """Our bad day is not the founder's problem. A shift that filed no
    document leaves the allowance where it was — the same rule the employees
    work under, applied to the bill."""
    monkeypatch.setenv("WERKHAUS_PLAN", "free")
    engine = StubEngine(root=tmp_path, seed=42, scenario="role_failure", speed=400.0)
    await engine.start()
    try:
        company = await engine.create_company("x [scenario:role_failure]")
        await engine.start_shift(company.id)
        await engine.halt(company.id)  # stopped before anything was filed

        left = (await engine.get_allowance()).shifts_left
        artifacts = await engine.list_artifacts(company.id)
        assert left == 3 - (1 if artifacts else 0)
    finally:
        await engine.aclose()


async def test_the_default_is_ungated(tmp_path) -> None:
    """A self-hosted or development run must not hit someone else's paywall."""
    engine = _engine(tmp_path)
    await engine.start()
    try:
        await engine.create_company("x")
        assert (await engine.get_allowance()).shifts_left is None
    finally:
        await engine.aclose()


# ---------------------------------------------------------------------- byok
def test_byok_is_ignored_off_plan_rather_than_rejected(tmp_path, monkeypatch) -> None:
    """A key saved on free must not break the company, and must not be used.
    It simply waits for the plan that includes it."""
    from werkhaus.engines.openhands.engine import OpenHandsEngine

    async def _check() -> None:
        engine = OpenHandsEngine(root=tmp_path, llm_factory=lambda _: None)
        await engine.start()
        try:
            company = await engine.create_company("x")
            await engine.set_vault(company.id, "WERKHAUS_MODEL_KEY", "sk-mine")
            runtime = engine._get(company.id)

            monkeypatch.setenv("WERKHAUS_PLAN", "free")
            assert engine.byok(runtime) == (None, None)

            monkeypatch.setenv("WERKHAUS_PLAN", "pro")
            assert engine.byok(runtime) == ("sk-mine", None)
        finally:
            await engine.aclose()

    monkeypatch.setenv("WERKHAUS_MODEL", "openrouter/some/model")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-platform")
    asyncio.run(_check())
