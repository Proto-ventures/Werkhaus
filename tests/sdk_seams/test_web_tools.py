"""Reading the web in batches, and the three ways that can go wrong.

No network here: the search endpoint and the page fetches are stubbed, because
what these tests are for is the contract around the fetch — what counts as a
source, what an employee is allowed to reach, and how much of a page rides
along into the next model call.
"""

from __future__ import annotations

import os
import threading

import pytest

os.environ.setdefault("OPENHANDS_SUPPRESS_BANNER", "1")

from werkhaus.engines.openhands import web  # noqa: E402
from werkhaus.engines.openhands.brain_tool import ShiftContext  # noqa: E402

SEARCH_HTML = """
<html><body>
  <div class="result">
    <a class="result__a" href="https://alpha.example/pricing">Alpha pricing</a>
    <a class="result__snippet">Plans from $10 a month.</a>
  </div>
  <div class="result">
    <a class="result__a" href="https://beta.example/pricing">Beta pricing</a>
    <a class="result__snippet">Two per cent and no minimum.</a>
  </div>
  <div class="result">
    <a class="result__a" href="https://alpha.example/pricing">Alpha again</a>
  </div>
  <div class="result"><span>an ad with no link</span></div>
</body></html>
"""

PAGE_HTML = """
<html><head><title>Alpha</title><style>.x{color:red}</style></head>
<body>
  <nav>Home Pricing About Careers</nav>
  <script>window.tracking = 1;</script>
  <main><h1>Pricing</h1><p>Alpha costs $10 a month with no minimum.</p>
  <p>%s</p></main>
  <footer>© Alpha, all rights reserved</footer>
</body></html>
""" % ("Every plan includes fractional shares and no account fee. " * 12)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """These tests describe the contract, not the internet.

    The reader proxy is a real third-party call, so it is off by default here —
    a unit test that quietly reaches r.jina.ai is both slow and a lie about
    what it is testing. The one test that exercises the fallback stubs it.
    """
    monkeypatch.setenv("WERKHAUS_NO_READER_PROXY", "1")


@pytest.fixture
def ctx() -> ShiftContext:
    class _Bus:
        def emit_threadsafe(self, *a, **k) -> None: ...

    return ShiftContext(
        company_id="co_x",
        shift_id="co_x/0001",
        role_id="researcher",
        shift_number=1,
        brain=None,  # type: ignore[arg-type]
        bus=_Bus(),  # type: ignore[arg-type]
        stopped=threading.Event(),
    )


# ------------------------------------------------------------------- search
def test_search_returns_ranked_results_in_one_call(ctx, monkeypatch) -> None:
    """The whole reason this tool exists: navigate -> get_state -> click ->
    get_content was four model calls to learn what one call now returns."""

    class _Response:
        text = SEARCH_HTML

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response())
    out = web.SearchExecutor(ctx)(
        web.WebSearchAction(queries=["alpha pricing"], read_top=0)
    )

    assert not out.is_error
    assert "https://alpha.example/pricing" in out.text
    assert "Plans from $10 a month." in out.text
    # The duplicate and the linkless ad are dropped, so two results, not four.
    assert out.text.count("https://") == 2

    # With read_top=0 nothing was opened, so nothing may count as a source —
    # otherwise a snippet could be cited as a page she read.
    assert ctx.browsed_urls == set()


def test_search_reads_its_own_top_results(ctx, monkeypatch) -> None:
    """Measured across five models: having searched once, every one of them
    searched *again* rather than opening anything — even when web_search had
    been removed from the tool list and only web_read was offered, they
    re-issued the call they had just made. A model repeats its own last action
    far more reliably than it follows an instruction, so the action it repeats
    has to be the one that already does the work.
    """

    class _Response:
        text = SEARCH_HTML

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response())
    monkeypatch.setattr(web, "_reachable", lambda url: None)
    monkeypatch.setattr(web.httpx, "Client", _FakeClient)

    out = web.SearchExecutor(ctx)(web.WebSearchAction(queries=["alpha pricing"]))

    assert not out.is_error
    # The list AND the page text, from one call and one turn.
    assert "https://beta.example/pricing" in out.text
    assert "Alpha costs $10 a month" in out.text
    # And the pages it read really count as read, at their final address.
    assert ctx.browsed_urls == {
        "https://www.alpha.example/pricing",  # followed its redirect
        "https://beta.example/pricing",
    }


def test_search_that_finds_nothing_says_so_rather_than_looking_empty(
    ctx, monkeypatch
) -> None:
    class _Response:
        status_code = 200
        # Genuinely empty, but with an off-site link so it is not a wall.
        text = '<html><body>no results <a href="https://x.example">x</a></body></html>'

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response())
    out = web.SearchExecutor(ctx)(web.WebSearchAction(queries=["nothing at all"]))
    assert out.is_error
    assert "site you can name" in out.text


def test_being_blocked_reads_differently_from_finding_nothing(ctx, monkeypatch):
    """The distinction that cost a whole shift.

    DuckDuckGo answered every one of sixteen searches with a challenge page.
    The tool called that "nothing came back", so the model did the sensible
    thing for that message — reworded and tried again, sixteen times. It cannot
    know rephrasing is futile unless the tool says so.
    """

    class _Challenge:
        status_code = 202
        text = "<html><body>Please verify you are human</body></html>"

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Challenge())
    out = web.SearchExecutor(ctx)(web.WebSearchAction(queries=["anything"]))
    assert out.is_error
    assert "refusing us" in out.text
    assert "do not try rephrasing" in out.text


def test_a_query_is_only_ever_run_once_a_shift(ctx, monkeypatch) -> None:
    """Models reword and circle back to queries they have already run."""
    calls = []

    class _Response:
        status_code = 200
        text = SEARCH_HTML

        def raise_for_status(self) -> None: ...

    def post(*a, **k):
        calls.append(k.get("data", {}).get("q"))
        return _Response()

    monkeypatch.setattr(web.httpx, "post", post)
    executor = web.SearchExecutor(ctx)
    executor(web.WebSearchAction(queries=["alpha pricing"], read_top=0))
    executor(web.WebSearchAction(queries=["alpha pricing"], read_top=0))
    assert calls == ["alpha pricing"]


def test_several_queries_cost_one_turn(ctx, monkeypatch) -> None:
    """Turns are the quadratic term: measured, the 40th model call of a shift
    carried 54,838 tokens against the 5th call's 536. Queries are not."""

    class _Response:
        status_code = 200
        text = SEARCH_HTML

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Response())
    out = web.SearchExecutor(ctx)(
        web.WebSearchAction(
            queries=["alpha pricing", "beta pricing", "gamma pricing"], read_top=0
        )
    )
    assert not out.is_error
    # Three queries, one observation, and the duplicate results merged.
    assert out.text.count("https://alpha.example/pricing") == 1


# --------------------------------------------------------------------- read
class _FakeStream:
    def __init__(self, html: str, url: str, kind: str = "text/html") -> None:
        self.text_bytes = html.encode()
        self.url = url
        self.headers = {"content-type": kind}
        self.encoding = "utf-8"

    def raise_for_status(self) -> None: ...
    def iter_bytes(self):
        yield self.text_bytes

    def __enter__(self): return self
    def __exit__(self, *a): return False


class _FakeClient:
    """Redirects alpha.example to its www host, like a real site would."""

    def __init__(self, *a, **k) -> None: ...
    def __enter__(self): return self
    def __exit__(self, *a): return False

    def stream(self, method, url):
        if "broken" in url:
            raise RuntimeError("connection reset")
        if "empty" in url:
            return _FakeStream("<html><body></body></html>", url)
        final = url.replace("https://alpha.", "https://www.alpha.")
        return _FakeStream(PAGE_HTML, final)


def test_read_takes_several_pages_and_strips_the_furniture(ctx, monkeypatch) -> None:
    monkeypatch.setattr(web, "_reachable", lambda url: None)
    monkeypatch.setattr(web.httpx, "Client", _FakeClient)

    out = web.ReadExecutor(ctx)(
        web.WebReadAction(
            urls=["https://alpha.example/pricing", "https://beta.example/pricing"]
        )
    )
    assert not out.is_error
    assert "Alpha costs $10 a month" in out.text
    # Scripts, styles, nav and footer are not what a person reads, and input is
    # 93.5% of what a shift costs.
    assert "window.tracking" not in out.text
    assert "Careers" not in out.text
    assert "all rights reserved" not in out.text


def test_a_page_counts_as_read_at_the_address_it_actually_landed_on(
    ctx, monkeypatch
) -> None:
    """Provenance is the one thing that makes "sourced" mean anything. A
    redirect means the text came from somewhere other than what she typed, and
    citing the address she typed would cite a page she never saw."""
    monkeypatch.setattr(web, "_reachable", lambda url: None)
    monkeypatch.setattr(web.httpx, "Client", _FakeClient)

    web.ReadExecutor(ctx)(web.WebReadAction(urls=["https://alpha.example/pricing"]))
    assert ctx.browsed_urls == {"https://www.alpha.example/pricing"}


def test_pages_that_fail_never_become_sources(ctx, monkeypatch) -> None:
    monkeypatch.setattr(web, "_reachable", lambda url: None)
    monkeypatch.setattr(web.httpx, "Client", _FakeClient)

    out = web.ReadExecutor(ctx)(
        web.WebReadAction(
            urls=["https://broken.example/x", "https://empty.example/y"]
        )
    )
    assert ctx.browsed_urls == set()
    assert out.is_error  # every page failed
    assert "Couldn't read https://broken.example/x" in out.text
    # A page that is empty even through the reader is genuinely unreadable, so
    # she is told to stop trying and write down what she wanted from it.
    assert "open question" in out.text


def test_one_dead_page_does_not_lose_the_others(ctx, monkeypatch) -> None:
    monkeypatch.setattr(web, "_reachable", lambda url: None)
    monkeypatch.setattr(web.httpx, "Client", _FakeClient)

    out = web.ReadExecutor(ctx)(
        web.WebReadAction(
            urls=["https://broken.example/x", "https://alpha.example/pricing"]
        )
    )
    assert not out.is_error
    assert "Alpha costs $10 a month" in out.text
    assert ctx.browsed_urls == {"https://www.alpha.example/pricing"}


def test_a_long_page_is_clipped(ctx, monkeypatch) -> None:
    long_html = "<html><body><main>" + ("word " * 40_000) + "</main></body></html>"
    monkeypatch.setattr(web, "_reachable", lambda url: None)

    class _Client(_FakeClient):
        def stream(self, method, url):
            return _FakeStream(long_html, url)

    monkeypatch.setattr(web.httpx, "Client", _Client)
    out = web.ReadExecutor(ctx)(web.WebReadAction(urls=["https://alpha.example/"]))
    assert len(out.text) < web.MAX_PAGE_CHARS + 500
    assert "rest of the page not shown" in out.text


# ------------------------------------------------------------------- safety
@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://127.0.0.1:8000/api/v1/companies",  # werkhaus itself
        "http://192.168.1.1/admin",
        "file:///etc/passwd",
        "ftp://example.com/x",
    ],
)
def test_an_employee_cannot_be_talked_into_reading_the_inside(url) -> None:
    """She reads text strangers wrote, and a page can suggest a link. The
    check is on the resolved address rather than the name, so a hostname that
    resolves to the metadata endpoint is refused too."""
    assert web._reachable(url) is not None


def test_a_public_address_is_allowed() -> None:
    assert web._reachable("https://example.com/pricing") is None


def test_a_stopped_shift_reads_nothing(ctx) -> None:
    ctx.stopped.set()
    assert web.SearchExecutor(ctx)(web.WebSearchAction(queries=["x"])).is_error
    assert web.ReadExecutor(ctx)(web.WebReadAction(urls=["https://a.example"])).is_error


# ------------------------------------------------------------------ wiring
def test_the_tools_are_registered_under_the_names_maya_asks_for() -> None:
    from openhands.sdk.tool.registry import list_registered_tools

    registered = list_registered_tools()
    assert "web_search" in registered and "web_read" in registered
    assert web.WebSearchTool.name == "web_search"
    assert web.WebReadTool.name == "web_read"


def test_a_script_rendered_page_falls_back_to_the_reader(ctx, monkeypatch) -> None:
    """The one thing a whole chromium was being kept for.

    Measured against a plain fetch on three real pages:
        robinhood.com        3,032 chars  ->  21,472
        public.com/pricing   404          ->   5,806  (the pricing page itself)
        acorns.com/pricing  14,202        ->  45,014
    """
    monkeypatch.delenv("WERKHAUS_NO_READER_PROXY", raising=False)
    monkeypatch.setattr(web, "_reachable", lambda url: None)

    class _Shell:
        """What a script-rendered page gives a plain fetch: a husk."""

        def __init__(self, *a, **k) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def stream(self, method, url):
            return _FakeStream("<html><body><div id=root></div></body></html>", url)

    class _Rendered:
        status_code = 200
        text = "Public.com pricing\n\n" + ("No commission on stocks. " * 40)

        def raise_for_status(self) -> None: ...

    monkeypatch.setattr(web.httpx, "Client", _Shell)
    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Rendered())

    out = web.ReadExecutor(ctx)(web.WebReadAction(urls=["https://public.com/pricing"]))
    assert not out.is_error
    assert "No commission on stocks" in out.text
    # It really was read, so it may be cited.
    assert ctx.browsed_urls == {"https://public.com/pricing"}


def test_the_reader_can_be_switched_off(ctx, monkeypatch) -> None:
    """It is a third party that sees which public pages the company reads.
    Someone who would rather keep every fetch first-party can say so, and gets
    an honest failure instead of a silent proxy call."""
    monkeypatch.setenv("WERKHAUS_NO_READER_PROXY", "1")
    monkeypatch.setattr(web, "_reachable", lambda url: None)

    def _boom(*a, **k):
        raise AssertionError("the reader proxy was called after being disabled")

    monkeypatch.setattr(web.httpx, "get", _boom)

    class _Shell:
        def __init__(self, *a, **k) -> None: ...
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def stream(self, method, url):
            return _FakeStream("<html><body><div id=root></div></body></html>", url)

    monkeypatch.setattr(web.httpx, "Client", _Shell)
    out = web.ReadExecutor(ctx)(web.WebReadAction(urls=["https://public.com/pricing"]))
    assert out.is_error
    assert ctx.browsed_urls == set()


def test_a_self_hosted_searxng_is_preferred_over_scraping(ctx, monkeypatch) -> None:
    """A SearXNG fans one query across many upstream engines, so no single one
    sees enough of our traffic to start refusing — which is exactly how the
    scraped fallbacks failed. It is tried first and, when it answers, the
    scrapers are never touched."""
    scraped = []
    monkeypatch.setenv("WERKHAUS_SEARCH_URL", "http://localhost:8888/")
    monkeypatch.setattr(
        web.httpx, "post", lambda *a, **k: scraped.append(a) or _unused()
    )

    class _Json:
        def raise_for_status(self) -> None: ...
        def json(self):
            return {
                "results": [
                    {"title": "Alpha", "url": "https://alpha.example/pricing",
                     "content": "Plans from $10."},
                    {"title": "dupe", "url": "https://alpha.example/pricing"},
                ]
            }

    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Json())
    out = web.SearchExecutor(ctx)(
        web.WebSearchAction(queries=["alpha pricing"], read_top=0)
    )
    assert not out.is_error
    assert "https://alpha.example/pricing" in out.text
    assert out.text.count("https://alpha.example/pricing") == 1  # deduped
    assert scraped == [], "fell through to scraping despite a working SearXNG"


def test_a_searxng_without_json_enabled_does_not_kill_the_shift(
    ctx, monkeypatch
) -> None:
    """JSON is off in a stock SearXNG, so this is the likeliest way someone
    misconfigures it. It must cost a slower search, not a failed one."""
    monkeypatch.setenv("WERKHAUS_SEARCH_URL", "http://localhost:8888")

    class _Html:
        status_code = 200
        text = SEARCH_HTML

        def raise_for_status(self) -> None: ...
        def json(self):
            raise ValueError("not json")

    monkeypatch.setattr(web.httpx, "get", lambda *a, **k: _Html())
    monkeypatch.setattr(web.httpx, "post", lambda *a, **k: _Html())
    out = web.SearchExecutor(ctx)(
        web.WebSearchAction(queries=["alpha pricing"], read_top=0)
    )
    # Fell through to the keyless fallback and still got results.
    assert not out.is_error
    assert "https://alpha.example/pricing" in out.text


def _unused():
    raise AssertionError("should not be reached")
