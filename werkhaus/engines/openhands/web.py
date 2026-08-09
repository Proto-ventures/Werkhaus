"""Reading the web without driving a browser to do it.

Measured on the shift that prompted this, across 79 minutes: the browser spent
**30 seconds** fetching pages and the model spent **77 minutes** thinking. The
browser was never the slow part. What was slow is that reading one page cost
three or four model calls —

    navigate -> get_state -> click -> get_content

— at roughly 92 seconds each, because every step is a round trip through a
model that must look at an indexed DOM and decide what to click next.

These two tools collapse that. ``web_search`` returns ranked results with
snippets in one call, so the search-engine dance disappears; ``web_read`` takes
a *list* of URLs and returns the readable text of all of them in one call, so
five pages cost one round trip instead of fifteen. The browser stays for what
only a browser can do: pages that build themselves with scripts.

Three things this module is strict about, all of which are the reason a plain
``httpx.get`` in the agent's hands would be worse than the browser:

* **Provenance.** A page counts as read only when it actually returned readable
  text, and it is the *final* URL after redirects that gets recorded. The
  brain's "sourced" check is only as honest as this set.
* **Size.** ``browser_get_content`` handed back up to 31KB of one page. Input is
  93.5% of what a shift costs, so every page is trimmed to something a reader
  could actually use.
* **Reach.** An employee reads text strangers wrote, and some of them would
  like it to contain instructions. She must not be talked into fetching the
  cloud metadata endpoint or something on the host's own network.
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from openhands.sdk.tool import (
    Action,
    Observation,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)
from pydantic import Field

from werkhaus.engines.openhands.brain_tool import (
    ShiftContext,
    get_shift_context,
    normalize_url,
)

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

SCRAPED_BACKENDS = (
    ("ddg-html", "https://html.duckduckgo.com/html/"),
    ("ddg-lite", "https://lite.duckduckgo.com/lite/"),
)
"""The keyless fallbacks, tried in order until one returns results.

A weak foundation, and this list is mitigation rather than fix: measured, the
first answered eight clean results in 1.2s and then — after a few shifts' worth
of traffic from one address — began answering every request with a challenge
page. It recovered on its own about forty minutes later, so it is rate-limiting
rather than a ban, and batching plus the per-shift cache is what keeps us under
the limit. Google is absent because it renders itself with scripts a plain
fetch never runs."""


def searxng_url() -> str | None:
    """A SearXNG this company runs, if the operator configured one.

    Worth preferring over everything else here. It is a metasearch front end:
    one query fans out across many upstream engines, so no single one sees
    enough traffic from us to start refusing — which is the exact failure this
    module keeps hitting. It needs no key, and being local it is the only
    option where nobody else learns what the company is researching.

    JSON is off by default in SearXNG. In ``settings.yml``::

        search:
          formats:
            - html
            - json

    Then point WERKHAUS_SEARCH_URL at it (e.g. http://localhost:8888).
    """
    return (os.getenv("WERKHAUS_SEARCH_URL") or "").strip().rstrip("/") or None

_BLOCKED = object()
"""Sentinel: the backend answered, but with a challenge instead of results."""

READER_PROXY = "https://r.jina.ai/"
"""A keyless rendering reader, used only when a plain fetch comes back thin.

This is the one thing that was worth keeping a whole chromium for, and it does
the job better. Measured on three pages a plain fetch handles badly:

    robinhood.com       3,032 chars  ->  21,472
    public.com/pricing  404          ->   5,806   (the pricing page itself)
    acorns.com/pricing 14,202        ->  45,014

It is a third party, so it sees which public pages the company reads — the
pages, never a credential, since an employee holding credentials has no web
tools at all. Set WERKHAUS_NO_READER_PROXY=1 to keep every fetch first-party
and accept that script-rendered pages come back empty.
"""

THIN_PAGE = 300
"""Below this many characters a "successful" fetch is really a shell waiting
for its scripts, and worth a second attempt through the reader.

Deliberately low. A short but genuine page — a terse pricing table — must not
be thrown away and re-fetched through a third party, so this only catches
pages with essentially nothing in them."""

MAX_QUERIES = 4
"""Per ``web_search`` call. Turns are the expensive thing, queries are not."""

_CHALLENGE = re.compile(
    r"captcha|unusual traffic|are you a robot|verify you are|challenge-platform",
    re.IGNORECASE,
)


def _looks_like_a_challenge(html: str) -> bool:
    head = html[:4000]
    if _CHALLENGE.search(head):
        return True
    # A results page always links off-site. One that links nowhere is a wall,
    # however politely it is worded.
    soup = BeautifulSoup(html, "lxml")
    return not any(
        (a.get("href") or "").startswith("http") for a in soup.find_all("a", limit=80)
    )

SEARCH_TIMEOUT = 20.0
READ_TIMEOUT = 20.0
MAX_URLS = 6
"""Per ``web_read`` call. The point is to amortise one model round trip over
several pages; past half a dozen the observation is too big to be worth it."""

MAX_PAGE_CHARS = 6_000
"""Roughly 1,500 tokens per page. A pricing page says what it charges well
inside this; the rest is navigation furniture and legal boilerplate."""

SEARCH_PAGE_CHARS = 2_500
"""Tighter, for the pages ``web_search`` opens on its own initiative.

A search sweep is a guess about what is relevant, and a shift makes many of
them: measured, sixteen searches at the full allowance carried ~96k tokens of
page text. This is enough to see whether a page answers the question — and
``web_read`` is right there, at the full allowance, for the ones that do."""

MAX_BYTES = 3_000_000
"""Nothing readable is bigger than this, and an agent must not be able to pull
a disc image into the shift's memory."""

_STRIP = (
    "script", "style", "noscript", "nav", "header", "footer", "aside",
    "form", "svg", "iframe", "template",
)

_BLANK_LINES = re.compile(r"\n{3,}")


# ------------------------------------------------------------------ safety
def _reachable(url: str) -> str | None:
    """``None`` if this URL is fine to fetch, else why it isn't.

    The employee's reading list is partly written by strangers: a page can
    suggest a link, and she may follow it. So the check is on the resolved
    address, not the name — ``metadata.internal`` resolving to 169.254.169.254
    is exactly the trick this exists to stop.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return "only http and https addresses can be read"
    host = parts.hostname
    if not host:
        return "that isn't a web address"
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return "that address doesn't resolve"
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            return "that address is on a private network, so it isn't public"
    return None


# ------------------------------------------------------------- extraction
def readable_text(html: str) -> str:
    """The part of a page a person would read.

    Deliberately crude — no readability heuristics, no scoring. Everything that
    is definitionally furniture comes out, the rest is collapsed to text. A
    wrong guess by a clever extractor costs a fact; leaving a stray menu in
    costs a few tokens.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(_STRIP):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = main.get_text("\n", strip=True)
    return _BLANK_LINES.sub("\n\n", text).strip()


def _clip(text: str, limit: int = MAX_PAGE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + "\n\n[…rest of the page not shown]"


# ----------------------------------------------------------------- schema
class WebSearchAction(Action):
    queries: list[str] = Field(
        description=(
            "What to search for, in plain words. Pass EVERY angle you want to "
            "cover in one call — three or four queries here cost the same turn "
            "as one, and separate calls cost a turn each."
        )
    )
    limit: int = Field(default=6, ge=1, le=15, description="Results per query.")
    read_top: int = Field(
        default=4,
        ge=0,
        le=MAX_URLS,
        description=(
            "How many of the top results to open and read in this same call. "
            "Leave at 4 unless you only want the list of links."
        ),
    )


class WebReadAction(Action):
    urls: list[str] = Field(
        description=(
            "The pages to read, up to six. Pass every page you want in ONE "
            "call — they are fetched together."
        )
    )


class WebObservation(Observation):
    pass


def _error(text: str) -> WebObservation:
    return WebObservation.from_text(text, is_error=True)


# --------------------------------------------------------------- executors
class SearchExecutor(ToolExecutor):
    def __init__(self, ctx: ShiftContext) -> None:
        self.ctx = ctx
        self.read = ReadExecutor(ctx)

    def __call__(self, action: WebSearchAction, conversation: Any = None):
        ctx = self.ctx
        if ctx.stopped.is_set():
            return _error("This shift is over. Stop working and finish up.")
        queries = [q.strip() for q in action.queries if q and q.strip()][:MAX_QUERIES]
        if not queries:
            return _error("web_search needs at least one query.")

        # Every query in one turn. Measured: a shift ran sixteen separate
        # searches, and because a model's prompt carries the whole history, the
        # forty-third call cost 54,838 tokens against the fifth call's 536.
        # Turns are the quadratic term; queries are free.
        with ThreadPoolExecutor(max_workers=len(queries)) as pool:
            found = list(
                pool.map(lambda q: (q, self._one_query(q, action.limit)), queries)
            )

        blocked = [q for q, r in found if r is _BLOCKED]
        results, seen = [], set()
        for _, r in found:
            if r is _BLOCKED or not r:
                continue
            for item in r:
                if item[1] not in seen:
                    seen.add(item[1])
                    results.append(item)
        if blocked and not results:
            return _error(
                "The search engine is refusing us right now — it answered "
                "with a challenge page, not results. This is not about your "
                "wording, so do not try rephrasing. Go straight to a site you "
                "can name with web_read, or record what you could not check "
                "as an open question."
            )
        if not results:
            return _error(
                f"Nothing came back for {', '.join(repr(q) for q in queries)}. "
                "Try a site you can name instead."
            )
        query = " / ".join(queries)
        # Reading happens here rather than in a tool call the model has to
        # choose to make. Measured across five models: having searched once,
        # every one of them searched *again* rather than opening anything —
        # even when web_search had been removed from the tool list and only
        # web_read was offered, they re-issued the call they had just made.
        # A model mimics its own last action far more reliably than it follows
        # an instruction, so the fix is to make the action it will repeat the
        # one that already does the work.
        reading = results[: action.read_top]
        pages = (
            self.read.fetch([url for _, url, _ in reading], SEARCH_PAGE_CHARS)
            if reading
            else []
        )

        lines = [f"{len(results)} results for {query!r}."]
        if pages:
            lines.append(
                f"The top {len(pages)} are read in full below; the rest are "
                "links you can open with web_read."
            )
        lines.append("")
        for i, (title, url, snippet) in enumerate(results, 1):
            mark = "[read below]" if i <= len(pages) else ""
            lines.append(f"{i}. {title} {mark}\n   {url}\n   {snippet}")
        if pages:
            lines.append("\n" + "\n\n".join(pages))
        lines.append(
            "\nA result you have only seen summarised above is a lead, not a "
            "fact — cite only what you read."
        )
        return WebObservation.from_text("\n".join(lines))

    def _one_query(self, query: str, limit: int):
        """One query, cached for the shift, against each backend in turn.

        Returns the results, ``_BLOCKED`` if every backend answered with a
        challenge instead of results, or ``[]`` if they genuinely had nothing.
        The distinction matters: told "nothing came back", a model rewords and
        tries again — measured, sixteen times in one shift, every one of them
        refused. It cannot tell rewording won't help unless we say so.
        """
        cached = self.ctx.search_cache.get(query)
        if cached is not None:
            return cached

        own = searxng_url()
        if own:
            results = self._ask_searxng(own, query, limit)
            if results:
                self.ctx.search_cache[query] = results
                return results
            # Fall through rather than fail: a SearXNG that is down or
            # mid-restart should cost a slower search, not a failed shift.
            logger.warning("configured search at %s returned nothing", own)

        blocked = False
        for name, url in SCRAPED_BACKENDS:
            try:
                response = httpx.post(
                    url,
                    data={"q": query},
                    headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en"},
                    timeout=SEARCH_TIMEOUT,
                    follow_redirects=True,
                )
            except Exception as exc:
                logger.warning("search backend %s failed: %s", name, exc)
                continue
            results = _parse_results(response.text, limit)
            if results:
                self.ctx.search_cache[query] = results
                return results
            # A challenge page is a 200 or 202 with a body and no results in
            # it. Worth naming: it is the difference between "search harder"
            # and "stop searching".
            if response.status_code == 202 or _looks_like_a_challenge(response.text):
                logger.warning("search backend %s is refusing us", name)
                blocked = True
        out = _BLOCKED if blocked else []
        self.ctx.search_cache[query] = out
        return out

    def _ask_searxng(
        self, base: str, query: str, limit: int
    ) -> list[tuple[str, str, str]]:
        """Query a SearXNG instance over its JSON API."""
        try:
            response = httpx.get(
                f"{base}/search",
                params={"q": query, "format": "json"},
                headers={"User-Agent": USER_AGENT},
                timeout=SEARCH_TIMEOUT,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            # The likeliest cause by far, and worth naming in the log rather
            # than leaving someone to wonder: SearXNG ships with JSON off.
            logger.warning(
                "search at %s did not answer with JSON (%s) — check that "
                "'json' is listed under search.formats in settings.yml",
                base,
                exc,
            )
            return []
        out: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for item in payload.get("results", []):
            url = (item.get("url") or "").strip()
            if not url.startswith("http") or url in seen:
                continue
            seen.add(url)
            out.append((
                (item.get("title") or url).strip(),
                url,
                (item.get("content") or "").strip()[:280],
            ))
            if len(out) >= limit:
                break
        return out


def _parse_results(html: str, limit: int) -> list[tuple[str, str, str]]:
    soup = BeautifulSoup(html, "lxml")
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for result in soup.select("div.result"):
        link = result.select_one("a.result__a")
        if not link:
            continue
        url = (link.get("href") or "").strip()
        if not url.startswith("http") or url in seen:
            continue
        seen.add(url)
        snippet = result.select_one(".result__snippet")
        out.append((
            link.get_text(" ", strip=True),
            url,
            snippet.get_text(" ", strip=True)[:280] if snippet else "",
        ))
        if len(out) >= limit:
            break
    return out


class ReadExecutor(ToolExecutor):
    def __init__(self, ctx: ShiftContext) -> None:
        self.ctx = ctx

    def __call__(self, action: WebReadAction, conversation: Any = None):
        if self.ctx.stopped.is_set():
            return _error("This shift is over. Stop working and finish up.")
        urls = [u.strip() for u in action.urls if u and u.strip()][:MAX_URLS]
        if not urls:
            return _error("web_read needs at least one URL.")
        pages = self.fetch(urls)
        return WebObservation.from_text(
            "\n\n".join(pages),
            is_error=all(page.startswith("Couldn't read") for page in pages),
        )

    def fetch(self, urls: list[str], limit: int = MAX_PAGE_CHARS) -> list[str]:
        """Read several pages at once. Shared with ``web_search``, which reads
        its own top results rather than asking the model to choose to."""
        if not urls:
            return []
        # Concurrent because the whole point is to spend one model round trip
        # on several pages; six slow sites in series would give the saving back.
        with ThreadPoolExecutor(max_workers=len(urls)) as pool:
            return list(pool.map(lambda u: self._one(u, limit), urls))

    def _one(self, url: str, limit: int = MAX_PAGE_CHARS) -> str:
        refused = _reachable(url)
        if refused:
            return f"Couldn't read {url} — {refused}."
        cached = self.ctx.page_cache.get(url)
        if cached is not None:
            return _clip(cached, limit)
        page = self._direct(url) or self._through_reader(url)
        if page is None:
            return (
                f"Couldn't read {url} — it came back empty even through the "
                "reader, so treat it as a page that cannot be read and note "
                "what you wanted from it as an open question."
            )
        self.ctx.page_cache[url] = page
        return _clip(page, limit)

    def _through_reader(self, url: str) -> str | None:
        """Second attempt, for pages that build themselves with scripts."""
        if os.getenv("WERKHAUS_NO_READER_PROXY", "").lower() in ("1", "true", "yes"):
            return None
        try:
            response = httpx.get(
                READER_PROXY + url,
                headers={"User-Agent": USER_AGENT},
                timeout=READ_TIMEOUT * 2,
                follow_redirects=True,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.info("reader proxy could not read %s: %s", url, exc)
            return None
        text = response.text.strip()
        if len(text) < THIN_PAGE:
            return None
        # The proxy already returns readable text, so the URL it reports is the
        # one the content came from — same provenance rule as a direct fetch.
        self.ctx.browsed_urls.add(normalize_url(url))
        return f"--- {url} ---\n{_BLANK_LINES.sub(chr(10) * 2, text)}"

    def _direct(self, url: str) -> str | None:
        """A plain first-party fetch. ``None`` means "try the reader" — which
        covers a refusal, a timeout, and the shell of a page whose content
        arrives by script."""
        try:
            with httpx.Client(
                timeout=READ_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                with client.stream("GET", url) as response:
                    response.raise_for_status()
                    kind = response.headers.get("content-type", "")
                    if "html" not in kind and "text" not in kind:
                        return None
                    body = b""
                    for chunk in response.iter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            break
                    final = str(response.url)
                    html = body.decode(response.encoding or "utf-8", errors="replace")
        except Exception as exc:
            logger.info("could not read %s directly: %s", url, exc)
            return None

        text = readable_text(html)
        if len(text.strip()) < THIN_PAGE:
            return None

        # Provenance, and only now: the final URL, because that is the page the
        # text actually came from, and a citation of the address she typed
        # would be a citation of somewhere she never landed.
        self.ctx.browsed_urls.add(normalize_url(final))
        return f"--- {final} ---\n{text}"


# ------------------------------------------------------------------- tools
SEARCH_DESCRIPTION = """Search the web AND read the best results, in one step.

Takes a LIST of queries and runs them all together. Returns ranked results —
title, address, summary — and the full readable text of the top few, already
fetched. One call gives you both what exists and what it says.

Ask every angle in a single call: four queries here cost one turn, four calls
cost four.

Prefer this over typing a search engine's address into the browser: it is one
step instead of four, and it does not depend on a search page rendering."""

READ_DESCRIPTION = """Read web pages — several at once.

Give it a list of addresses and it returns the readable text of each, with the
address it actually landed on after redirects. Pass every page you want in ONE
call: six pages in one call cost you one turn, six calls cost you six.

This is how you read a page. Use the browser only when a page comes back empty
here, which means it builds itself with scripts."""


class WebSearchTool(ToolDefinition[WebSearchAction, WebObservation]):
    """Auto-derived tool name: ``web_search``."""

    @classmethod
    def create(cls, conv_state=None, **params: Any) -> Sequence[WebSearchTool]:
        ctx = _require_ctx(params)
        return [
            cls(
                description=SEARCH_DESCRIPTION,
                action_type=WebSearchAction,
                observation_type=WebObservation,
                executor=SearchExecutor(ctx),
            )
        ]


class WebReadTool(ToolDefinition[WebReadAction, WebObservation]):
    """Auto-derived tool name: ``web_read``."""

    @classmethod
    def create(cls, conv_state=None, **params: Any) -> Sequence[WebReadTool]:
        ctx = _require_ctx(params)
        return [
            cls(
                description=READ_DESCRIPTION,
                action_type=WebReadAction,
                observation_type=WebObservation,
                executor=ReadExecutor(ctx),
            )
        ]


def _require_ctx(params: dict[str, Any]) -> ShiftContext:
    company_id = params["company_id"]
    ctx = get_shift_context(company_id)
    if ctx is None:
        raise RuntimeError(f"no shift context registered for {company_id}")
    return ctx


register_tool("web_search", WebSearchTool)
register_tool("web_read", WebReadTool)
