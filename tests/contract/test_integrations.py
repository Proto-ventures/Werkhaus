"""Connections: the guided credential flow.

Every provider needs a human to make the account and mint the first key — there
is no automated path from nothing to a working backend. So this file guards the
promises made around that boundary: a key is checked before it is stored, a
value never appears anywhere but the vault, and a card never claims to do
something it can't.
"""

from __future__ import annotations

import json

import pytest

from werkhaus.contract.catalog import BY_ID, CATALOG, refused_names
from werkhaus.contract.credentials import classify
from werkhaus.contract.errors import (
    CredentialRejected,
    ForbiddenCredential,
    IntegrationUnavailable,
)
from werkhaus.contract.integrations import (
    BACKEND_STEPS,
    Availability,
    ConnectionStatus,
)
from werkhaus.engines.stub.engine import StubEngine
from werkhaus.engines.verify import NullVerifier, VerifyResult

GOOD_TOKEN = "sbp_" + "a1b2c3d4e5" * 3


class Refusing:
    """A provider that says no. Nothing may be written when it does."""

    async def check(self, provider: str, values: dict[str, str]) -> VerifyResult:
        return VerifyResult(
            False, "Supabase didn't recognise that token.", hint="Try again."
        )


async def _engine(tmp_path, verifier=None):
    engine = StubEngine(root=tmp_path, seed=42, scenario="happy", speed=400.0)
    engine.verifier = verifier or NullVerifier()
    await engine.start()
    company = await engine.create_company("A refill service for cleaning products")
    return engine, company


# ---------------------------------------------------------------- the catalog
def test_every_field_is_classified() -> None:
    """classify() decides what the publish gate treats as secret. A field it
    has never heard of would be classified secret — safe, but it would also
    block a page that legitimately carries a publishable key."""
    for spec in CATALOG:
        for field in spec.fields:
            assert classify(field.name) is field.kind, field.name


def test_field_names_are_unique_and_vault_safe() -> None:
    seen: set[str] = set()
    for spec in CATALOG:
        for field in spec.fields:
            assert field.name not in seen, f"{field.name} used twice"
            seen.add(field.name)
            assert StubEngine._VAULT_NAME.match(field.name), field.name


def test_every_step_stands_on_its_own_words() -> None:
    """Pictures are a slot, not a dependency: a walkthrough with no screen
    recordings yet must still be followable, or we can't ship until someone
    records six of them."""
    for spec in CATALOG:
        if spec.availability is Availability.MANUAL_SETUP:
            assert spec.manual_note, f"{spec.id} must explain itself"
            continue
        assert spec.steps, f"{spec.id} has no walkthrough"
        for step in spec.steps:
            assert len(step.body) >= 40, f"{spec.id}: {step.title!r} is too thin"
        assert any(s.link for s in spec.steps), f"{spec.id} links nowhere"
        collected = {s.field for s in spec.steps if s.field}
        required = {
            f.name for f in spec.fields if f.required and not f.team_fills_it
        }
        assert required <= collected, f"{spec.id} never asks for {required - collected}"


def test_stripe_takes_test_keys_only() -> None:
    """Test mode first is enforced by the shape of the value, not by a branch
    somewhere that could be forgotten."""
    import re

    field = next(f for f in BY_ID["stripe"].fields if f.name == "STRIPE_RESTRICTED_KEY")
    assert re.match(field.pattern or "", "rk_test_" + "a" * 20)
    assert not re.match(field.pattern or "", "rk_live_" + "a" * 20)
    assert not re.match(field.pattern or "", "sk_live_" + "a" * 20)


def test_the_master_key_is_refused_by_name() -> None:
    assert "SUPABASE_SERVICE_ROLE_KEY" in refused_names()


def test_build_steps_only_need_providers_that_exist() -> None:
    known = {spec.id for spec in CATALOG}
    for step in BACKEND_STEPS:
        assert set(step.needs) <= known, step.id


# ---------------------------------------------------------------- connecting
async def test_connecting_stores_the_value_only_in_the_vault(tmp_path) -> None:
    engine, company = await _engine(tmp_path)
    try:
        state = await engine.connect_integration(
            company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": GOOD_TOKEN}
        )
        assert state.connection.status is ConnectionStatus.CONNECTED
        assert "SUPABASE_ACCESS_TOKEN" in state.connection.fields_present

        # The value is in no response, ever.
        assert GOOD_TOKEN not in json.dumps(state.model_dump(mode="json"))
        listed = await engine.list_integrations(company.id)
        assert GOOD_TOKEN not in json.dumps(
            [s.model_dump(mode="json") for s in listed]
        )
        for item in await engine.list_vault(company.id):
            assert GOOD_TOKEN not in item.model_dump_json()

        # Nor in the append-only log, which can never be edited afterwards.
        root = engine._get(company.id).brain.paths.root
        assert GOOD_TOKEN not in (root / "_state" / "log.jsonl").read_text()
        assert GOOD_TOKEN in (root / "_state" / "vault.json").read_text()
    finally:
        await engine.aclose()


async def test_a_refused_key_is_never_stored(tmp_path) -> None:
    """The whole point of checking first: a key that doesn't work must not be
    sitting in the vault waiting to fail during a shift."""
    engine, company = await _engine(tmp_path, verifier=Refusing())
    try:
        with pytest.raises(CredentialRejected) as caught:
            await engine.connect_integration(
                company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": GOOD_TOKEN}
            )
        assert "didn't recognise" in caught.value.message
        assert await engine.list_vault(company.id) == []

        state = next(
            s
            for s in await engine.list_integrations(company.id)
            if s.spec.id == "supabase"
        )
        assert state.connection.status is ConnectionStatus.NOT_CONNECTED
    finally:
        await engine.aclose()


async def test_a_badly_shaped_value_never_reaches_the_provider(tmp_path) -> None:
    engine, company = await _engine(tmp_path)
    try:
        with pytest.raises(CredentialRejected) as caught:
            await engine.connect_integration(
                company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": "nope"}
            )
        assert "sbp_" in caught.value.message  # tells them what to look for
    finally:
        await engine.aclose()


@pytest.mark.parametrize(
    "entry", ["connect_integration", "set_vault"]
)
async def test_the_master_key_is_refused_from_both_doors(entry, tmp_path) -> None:
    """The raw vault must obey the same rule as the guided flow, or the escape
    hatch quietly becomes the way round the safety rule."""
    engine, company = await _engine(tmp_path)
    try:
        with pytest.raises(ForbiddenCredential):
            if entry == "set_vault":
                await engine.set_vault(
                    company.id, "SUPABASE_SERVICE_ROLE_KEY", "x" * 40
                )
            else:
                await engine.connect_integration(
                    company.id, "supabase", {"SUPABASE_SERVICE_ROLE_KEY": "x" * 40}
                )
    finally:
        await engine.aclose()


async def test_discovered_facts_are_stored_too(tmp_path) -> None:
    """When the check can tell which project to use, the founder shouldn't be
    asked for it."""

    class Discovering:
        async def check(self, provider, values):
            return VerifyResult(
                True,
                "Supabase is connected.",
                facts={"SUPABASE_PROJECT_REF": "abcdefghijklmnopqrst"},
                scope_note="The team will work in your existing project.",
            )

    engine, company = await _engine(tmp_path, verifier=Discovering())
    try:
        state = await engine.connect_integration(
            company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": GOOD_TOKEN}
        )
        assert "SUPABASE_PROJECT_REF" in state.connection.fields_present
        assert state.connection.scope_note
    finally:
        await engine.aclose()


async def test_disconnecting_removes_every_value(tmp_path) -> None:
    engine, company = await _engine(tmp_path)
    try:
        await engine.connect_integration(
            company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": GOOD_TOKEN}
        )
        await engine.disconnect_integration(company.id, "supabase")
        assert await engine.list_vault(company.id) == []
        root = engine._get(company.id).brain.paths.root
        assert GOOD_TOKEN not in (root / "_state" / "vault.json").read_text()
    finally:
        await engine.aclose()


async def test_connection_state_survives_a_restart(tmp_path) -> None:
    """Derived from the vault and the log, so it is true after a cold load
    rather than remembered."""
    engine, company = await _engine(tmp_path)
    await engine.connect_integration(
        company.id, "supabase", {"SUPABASE_ACCESS_TOKEN": GOOD_TOKEN}
    )
    await engine.aclose()

    reloaded = StubEngine(root=tmp_path, seed=42, scenario="happy", speed=400.0)
    reloaded.verifier = NullVerifier()
    await reloaded.start()
    try:
        state = next(
            s
            for s in await reloaded.list_integrations(company.id)
            if s.spec.id == "supabase"
        )
        assert state.connection.status is ConnectionStatus.CONNECTED
        assert state.connection.connected_at is not None
    finally:
        await reloaded.aclose()


# --------------------------------------------------------------------- plans
async def test_a_paid_service_is_refused_on_free(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("WERKHAUS_PLAN", "free")
    engine, company = await _engine(tmp_path)
    try:
        with pytest.raises(IntegrationUnavailable):
            await engine.connect_integration(
                company.id, "stripe", {"STRIPE_RESTRICTED_KEY": "rk_test_" + "a" * 20}
            )
        stripe = next(
            s
            for s in await engine.list_integrations(company.id)
            if s.spec.id == "stripe"
        )
        assert stripe.connection.status is ConnectionStatus.UNAVAILABLE
        assert stripe.connection.unavailable_reason
        # The card still says what it would unlock, and what it blocks.
        assert stripe.spec.unlocks
        assert "Take a payment" in stripe.connection.blocks
    finally:
        await engine.aclose()


async def test_free_gets_the_three_with_real_free_tiers(monkeypatch) -> None:
    monkeypatch.setenv("WERKHAUS_PLAN", "free")
    from werkhaus.contract.plan import current_plan

    assert set(current_plan().integrations) == {"supabase", "netlify", "resend"}
    assert current_plan().external_spend is False


async def test_a_manual_setup_service_is_never_claimed_as_connected(
    tmp_path,
) -> None:
    engine, company = await _engine(tmp_path)
    try:
        moonpay = next(
            s
            for s in await engine.list_integrations(company.id)
            if s.spec.id == "moonpay"
        )
        assert moonpay.connection.status is ConnectionStatus.UNAVAILABLE
        assert moonpay.spec.manual_note
        with pytest.raises(IntegrationUnavailable):
            await engine.connect_integration(company.id, "moonpay", {"X": "y"})
    finally:
        await engine.aclose()
