"""A company belongs to the founder who described it.

This file exists because it once didn't. The stub engine took the company name,
one-liner, audience, success criteria and constraints from its demo scenario, so
every founder who typed their own idea got a company called Northwind Ceramics
whose customers were somebody else's — and no answer to any interview question
could dislodge it. The product looked hardwired to one example business.
"""

from __future__ import annotations

import pytest

from tests.contract.conftest import make_engine
from werkhaus.engines.common import name_from_idea

IDEAS = [
    "A booking tool for mobile dog groomers who run everything through WhatsApp",
    "A refill service for cleaning products, delivered by cargo bike",
    "Software that reads council planning applications and emails you nearby ones",
]


@pytest.mark.parametrize("idea", IDEAS)
async def test_the_company_is_the_founders_not_the_demos(idea, tmp_path) -> None:
    engine = make_engine(tmp_path)
    await engine.start()
    try:
        company = await engine.create_company(idea)
        blob = " ".join(
            [
                company.name,
                company.charter.idea,
                company.charter.one_liner,
                company.charter.audience,
                company.charter.success_looks_like,
                *company.charter.constraints,
            ]
        ).lower()

        assert company.charter.idea == idea
        # Every word of the name came out of the founder's own sentence.
        assert company.name != "New Company"
        for word in company.name.split():
            assert word.lower() in idea.lower()
        # Nothing from the demo scenario may leak into a described company.
        for leak in ("northwind", "ceramic", "potter", "hand-thrown"):
            assert leak not in blob, f"{leak!r} leaked from the scenario into {blob!r}"
    finally:
        await engine.aclose()


async def test_two_companies_are_two_companies(tmp_path) -> None:
    """The obvious check that would have caught it: same engine, two ideas,
    two different names."""
    engine = make_engine(tmp_path)
    await engine.start()
    try:
        first = await engine.create_company(IDEAS[0])
        second = await engine.create_company(IDEAS[1])
        assert first.id != second.id
        assert first.name != second.name
        assert first.charter.one_liner != second.charter.one_liner
    finally:
        await engine.aclose()


def test_a_name_stops_where_the_description_starts() -> None:
    assert name_from_idea("A booking tool for mobile dog groomers") == "Booking Tool"
    assert name_from_idea("the ultimate platform") == "Ultimate Platform"
    assert name_from_idea("") == "New Company"
