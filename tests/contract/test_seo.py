"""The generated pages have to be different from each other.

Programmatic SEO fails in exactly one way: a template gets spun over a list of
nouns, and the result is a hundred pages that a reader — and by now a search
engine — can tell were written by nobody about nothing. That is the same
failure as the scripted-shift engine this project deleted, wearing a different
hat, so it gets the same treatment: a test that makes the cheap version fail
loudly rather than ship quietly.

Everything here is read out of ``web/src/routes/seo.ts`` because the page is
static and the data file is the whole product. There is no build output to
inspect on a fresh checkout, and a test that needs one is a test that does not
run.
"""

from __future__ import annotations

import re
from pathlib import Path

SEO = Path(__file__).resolve().parents[2] / "web/src/routes/seo.ts"

# What a search result actually shows before truncating.
TITLE_MAX = 60
DESCRIPTION_MIN = 110
DESCRIPTION_MAX = 165


def guides() -> list[dict[str, object]]:
    source = SEO.read_text(encoding="utf-8")
    start = source.index("export const GUIDES")
    block = source[start : source.index("/** The site's own address")]
    entry = re.compile(
        r"\{\s*\n\s*slug: '(?P<slug>[^']+)',(?P<body>.*?)\n  \},", re.DOTALL
    )
    found: list[dict[str, object]] = []

    def one(slug: str, body: str, field: str) -> str:
        match = re.search(rf"{field}:\s*\n?\s*'([^']*)'", body)
        assert match, f"{slug}: no {field}"
        return match.group(1)

    for slug, body in entry.findall(block):
        checks = re.search(r"checks: \[(.*?)\],\n", body, re.DOTALL)
        assert checks, f"{slug}: no checks"
        found.append(
            {
                "slug": slug,
                "title": one(slug, body, "title"),
                "description": one(slug, body, "description"),
                "audience": one(slug, body, "audience"),
                "money": one(slug, body, "money"),
                "idea": one(slug, body, "idea"),
                "checks": re.findall(r"'([^']+)'", checks.group(1)),
            }
        )
    return found


def test_there_are_pages_to_check() -> None:
    """A parser that silently matches nothing would pass every test below."""
    assert len(guides()) >= 10


def test_every_slug_is_unique_and_is_a_url() -> None:
    slugs = [g["slug"] for g in guides()]
    assert len(set(slugs)) == len(slugs), "a duplicate slug overwrites a page"
    for slug in slugs:
        assert re.fullmatch(r"[a-z0-9-]+", str(slug)), f"{slug} is not url-safe"


def test_titles_are_unique_and_fit_a_result() -> None:
    titles = [str(g["title"]) for g in guides()]
    assert len(set(titles)) == len(titles), "two pages competing for one result"
    for title in titles:
        assert len(title) <= TITLE_MAX, f"truncated in the result: {title!r}"


def test_descriptions_are_written_rather_than_omitted() -> None:
    for guide in guides():
        text = str(guide["description"])
        assert DESCRIPTION_MIN <= len(text) <= DESCRIPTION_MAX, (
            f"{guide['slug']}: description is {len(text)} characters"
        )


def test_no_two_pages_share_a_check() -> None:
    """The doorway-page smell, caught mechanically.

    If two trades are handed the same sentence about what to look at first,
    the page was produced by swapping a noun, and one of them is not true.
    """
    seen: dict[str, str] = {}
    for guide in guides():
        for check in guide["checks"]:  # type: ignore[union-attr]
            assert check not in seen, (
                f"{guide['slug']} and {seen[check]} share a check: {check!r}"
            )
            seen[check] = str(guide["slug"])


def test_every_page_carries_its_own_specifics() -> None:
    """Three fields that cannot be templated, present and distinct."""
    for field in ("audience", "money", "idea"):
        values = [str(g[field]) for g in guides()]
        assert len(set(values)) == len(values), f"a repeated {field}"
        for value in values:
            assert len(value) > 25, f"{field} too thin to be about anything: {value!r}"
