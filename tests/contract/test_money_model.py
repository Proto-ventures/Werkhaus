"""The company's own money, as opposed to what running it costs us.

Two different kinds of money meet in the dashboard and confusing them is the
expensive mistake: the ledger is dollars that have actually left our account,
and the money model is what the *business* would earn if its assumptions hold.
One is a receipt, the other is arithmetic over guesses.

So these tests pin the two properties that keep them apart: a money model
carries marks on every number, and there is nowhere in it to store revenue.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from werkhaus.brain.store import BrainStore
from werkhaus.contract.models import Charter, MoneyModel


def make(tmp_path: Path) -> BrainStore:
    store = BrainStore(tmp_path / "co_money", "co_money")
    store.set_charter(
        Charter(
            idea="A booking tool for mobile dog groomers",
            one_liner="Plans the day as a route, not a list.",
            audience="one-van groomers across the EU",
            success_looks_like="Five groomers using it weekly",
        ),
        "Booking Tool",
    )
    return store


ASSUMPTIONS = [
    {
        "key": "price",
        "label": "what one customer pays a month",
        "value": "29",
        "unit": "money",
        "confidence": "inferred",
        "note": "reasoned from the four rivals in the table",
    },
    {
        "key": "customers",
        "label": "customers at the end of month one",
        "value": "12",
        "unit": "count",
        "confidence": "assumption",
        "note": "nobody has been asked",
    },
    {
        "key": "variable_cost",
        "label": "what serving one customer costs a month",
        "value": "10.55",
        "unit": "money",
        "confidence": "assumption",
    },
]


def test_a_money_model_survives_a_restart(tmp_path: Path) -> None:
    store = make(tmp_path)
    store.record_money_model(ASSUMPTIONS, role_id="analyst", shift_id="co_money/0001")

    reopened = BrainStore(tmp_path / "co_money", "co_money")
    model = reopened.state.money
    assert model is not None
    assert model.role_id == "analyst"
    assert model.currency == "EUR"
    assert {a.key for a in model.assumptions} == {"price", "customers", "variable_cost"}
    assert model.assumptions[0].value == Decimal("29")


def test_every_number_arrives_with_a_mark(tmp_path: Path) -> None:
    """A price with no provenance is the whole failure this product is against."""
    store = make(tmp_path)
    with pytest.raises(ValueError, match="not a mark"):
        store.record_money_model(
            [
                {
                    "key": "price",
                    "value": "29",
                    "unit": "money",
                    "confidence": "obviously",
                }
            ],
            role_id="analyst",
            shift_id="co_money/0001",
        )
    assert store.state.money is None


def test_there_is_nowhere_to_put_revenue() -> None:
    """Revenue is derived at the point of display, never stored.

    If this ever fails because somebody added the field, the thing to fix is the
    field, not the test: a stored revenue number is indistinguishable from a
    remembered one, and a company with no customers has no revenue to remember.
    """
    assert "revenue" not in MoneyModel.model_fields
    assert "earned" not in MoneyModel.model_fields


def test_a_later_model_replaces_the_earlier_one(tmp_path: Path) -> None:
    """Half of last shift's model merged with half of this one is nobody's."""
    store = make(tmp_path)
    store.record_money_model(ASSUMPTIONS, role_id="analyst", shift_id="co_money/0001")
    store.record_money_model(
        [{"key": "price", "label": "price", "value": "24", "unit": "money",
          "confidence": "sourced", "note": "five groomers said so"}],
        role_id="analyst",
        shift_id="co_money/0002",
    )
    model = store.state.money
    assert model is not None
    assert [a.key for a in model.assumptions] == ["price"]
    assert model.assumptions[0].value == Decimal("24")
    assert model.shift_id == "co_money/0002"


def test_nothing_modelled_differs_from_modelled_to_nothing(tmp_path: Path) -> None:
    store = make(tmp_path)
    assert store.state.money is None
