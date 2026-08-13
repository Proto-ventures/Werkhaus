"""The price on the site and the price in the engine are the same price.

The front page is served as static files and has to quote a price with no API
behind it, so the number is written twice: once in ``plan.py``, where billing
reads it, and once in ``web/src/routes/specimen.ts``, where the page reads it.
Two copies of a number drift. This is the thing that notices.

It is a cheap test guarding an expensive failure: a site advertising €39 while
the engine charges €99 is not a bug report, it is a chargeback.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

from werkhaus.contract.plan import PLANS

SPECIMEN = Path(__file__).resolve().parents[2] / "web/src/routes/specimen.ts"


def quoted() -> dict[str, Decimal | None]:
    """The price list as the front page states it, read out of the source."""
    source = SPECIMEN.read_text(encoding="utf-8")
    start = source.index("export const PRICING")
    block = source[start : source.index("export const RIVALS")]
    found: dict[str, Decimal | None] = {}
    for entry in re.finditer(
        r"plan:\s*'(?P<plan>\w+)'.*?price:\s*(?P<price>null|[\d.]+)",
        block,
        re.DOTALL,
    ):
        raw = entry.group("price")
        found[entry.group("plan")] = None if raw == "null" else Decimal(raw)
    return found


def test_the_site_quotes_every_plan() -> None:
    assert set(quoted()) == set(PLANS)


def test_the_site_and_the_engine_agree_on_the_price() -> None:
    for plan, price in quoted().items():
        assert price == PLANS[plan].price_eur, (
            f"{plan}: the page says {price}, plan.py says {PLANS[plan].price_eur}"
        )


def test_free_is_free_rather_than_unpriced() -> None:
    """"Contact us" is a price. Refusing to print one is how a page loses a
    reader who has been burned twice already."""
    assert quoted()["free"] is None
    assert all(p is not None for k, p in quoted().items() if k != "free")
