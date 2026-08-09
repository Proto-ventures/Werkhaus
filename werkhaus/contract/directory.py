"""Every MCP server we know about, and the one way to connect any of them.

Built from two sources, deduplicated by repository to 13,329 servers:

* the **official MCP registry** (40,000 records, 11,595 distinct servers), which
  is machine-readable — remotes with their transport, packages with their
  install identifier, and environment variables each publisher declared with a
  description and a secret flag;
* **`punkpeye/awesome-mcp-servers`** (3,375 entries) for the 2,574 the registry
  does not carry, and for the categories the registry has no field for.

The registry is what makes this usable rather than merely long. Parsing install
hints out of the curated list's prose found connection details for 498 servers;
the registry's own fields provide them for 10,394, and the env-var declarations
mean the connect form is *generated* from what a publisher said they need
rather than guessed at.

Only spirituality and esoterica were dropped — a game studio, a clinic and a law
firm are all businesses, so "could appear in a business" excludes almost
nothing.

**These are a directory, not a catalog, and the difference is the whole point.**
A catalog entry in `catalog.py` carries walkthrough prose written against the
provider's actual sign-up flow, a credential pattern, and a probe that proves
the key works before it is stored. That is roughly an afternoon of research per
entry, and it is why there are six of them. A directory entry carries what its
publisher said about it. Nobody here has run these, and nobody has read their
code. Dressing them up as catalog cards would make the six verified ones
worthless, because a founder could no longer tell which was which.

So the directory is a search over what exists, and the generic connection is
what makes any of them usable: an address or a command, plus whatever
environment it needs. That path also covers every server written after this
file was generated, which a hand-maintained list never would.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pydantic import Field

from werkhaus.contract.models import Base

DATA = Path(__file__).parent / "data" / "mcp_directory.json"


class EnvField(Base):
    """A value a server says it needs, in its own words.

    Taken from the server's registry entry, which is why the connect form can
    be generated rather than written: the label below is the publisher's own
    description of what they want.
    """

    name: str
    description: str = ""
    required: bool = True
    secret: bool = True


class DirectoryEntry(Base):
    """One server someone published. Unverified by us, and labelled as such."""

    name: str
    url: str
    category: str
    description: str
    official: bool = False
    """Published by the service it talks to."""

    remote: bool = False
    """Reachable over the network. The rest need their command run on the
    machine the shift runs on, which a hosted Werkhaus cannot promise."""

    url_hint: str | None = None
    cmd_hint: str | None = None
    """How to reach it, from its own registry entry where there is one and
    from its description otherwise. A hint, not a guarantee."""

    transport: str | None = None
    env: list[EnvField] = Field(default_factory=list)
    """What it says it needs. Empty means it declared nothing, which is not
    the same as needing nothing."""

    source: str = "awesome-mcp-servers"


@lru_cache(maxsize=1)
def _entries() -> list[DirectoryEntry]:
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    return [
        DirectoryEntry(
            name=e["n"],
            url=e["u"],
            category=e["c"],
            description=e["d"],
            official=bool(e.get("o")),
            remote=bool(e.get("r")),
            url_hint=e.get("url_hint"),
            cmd_hint=e.get("cmd_hint"),
            transport=e.get("t"),
            env=[
                EnvField(
                    name=v["n"],
                    description=v.get("d", ""),
                    required=bool(v.get("req", 1)),
                    secret=bool(v.get("sec", 1)),
                )
                for v in e.get("env", [])
            ],
            source=e.get("src", "awesome-mcp-servers"),
        )
        for e in raw
    ]


@lru_cache(maxsize=1)
def categories() -> list[str]:
    return sorted({e.category for e in _entries()})


def search(
    q: str = "",
    category: str | None = None,
    official_only: bool = False,
    remote_only: bool = False,
    limit: int = 40,
) -> list[DirectoryEntry]:
    """Ranked by how well the words match, then by official and reachable.

    Deliberately not fuzzy. A founder looking for "stripe" wants the thing
    called Stripe, and a search that helpfully offers something else has made
    the directory less trustworthy rather than more helpful.
    """
    words = [w for w in q.lower().split() if w]
    found: list[tuple[int, DirectoryEntry]] = []
    for entry in _entries():
        if category and entry.category != category:
            continue
        if official_only and not entry.official:
            continue
        if remote_only and not entry.remote:
            continue
        if words:
            name = entry.name.lower()
            haystack = f"{name} {entry.description.lower()} {entry.category.lower()}"
            if not all(w in haystack for w in words):
                continue
            score = 0
            for w in words:
                if name.split("/")[-1].startswith(w):
                    score += 4
                elif w in name:
                    score += 2
            found.append((score, entry))
        else:
            found.append((0, entry))
    found.sort(
        key=lambda pair: (
            -pair[0],
            not pair[1].official,
            not pair[1].remote,
            pair[1].name.lower(),
        )
    )
    return [entry for _, entry in found[:limit]]


def count() -> int:
    return len(_entries())


class McpConnection(Base):
    """A server this company has been connected to by hand.

    Values live in the vault like every other credential; this is the shape of
    what is stored beside them, and what the studio shows back.
    """

    name: str
    """Short slug the founder gave it. Also the key the agent's tools are
    prefixed with when more than one server is connected."""

    label: str
    transport: str = "stdio"
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env_names: list[str] = Field(default_factory=list)
    """Names only. The values are in the vault and never come back."""

    directory_url: str | None = None
    """Where it came from, if it was picked out of the directory."""

    added_at: str | None = None
    verified: bool = False
    """True once the server has answered a tools listing. Until then the
    studio says so, because an unreachable server fails a whole shift."""

    note: str | None = None
