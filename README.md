# Werkhaus

Describe a business. An org of AI employees builds it, one shift at a time.

The user is non-technical. They never see a terminal, a repo, a commit, or a
traceback — the abstraction is **a company with employees doing shifts**.

## Architecture rules

These three are load-bearing. Breaking any of them quietly undoes the design.

1. **`werkhaus/contract/` is the only vocabulary the dashboard knows.** Nothing
   under `contract/`, `api/`, `brain/` or `share/` may import `openhands.*`.
   All SDK imports live under `werkhaus/engines/openhands/`.
   Enforced by `tests/contract/test_no_sdk_imports.py`.
2. **`software-agent-sdk/` is a read-only reference checkout, never a dependency.**
   We pin `openhands-sdk==1.41.0` from PyPI. The SDK ships ~6 commits/day; a path
   dependency would turn every upgrade into a merge. The clone is for grepping and
   for reading `examples/01_standalone_sdk/*`.
3. **`workspace=` is always a Workspace object, never a `str` path.** The SDK's
   `Conversation.__new__` dispatches on workspace type, so sandboxing agents in
   Docker later stays a config change instead of a rewrite.

## Layout

```
werkhaus/contract/   the interface both engines implement. Zero SDK imports.
werkhaus/api/        FastAPI REST + WS. Depends on contract only.
werkhaus/engines/    null, stub, openhands (M3+)
werkhaus/brain/      BrainStore — durable cross-conversation company state
werkhaus/share/      snapshot builder + secret scanner
web/                 Vite + React + Tailwind + shadcn/ui
```

## The company brain

`_state/log.jsonl` is the source of truth. Everything else — `backlog.yaml`,
`decisions.md`, `metrics.json`, `artifacts.json` — is a projection of it, and can
be deleted and rebuilt. No fact exists only in a projection, which is what makes
"nothing was lost" literal rather than hopeful.

```
companies/{cid}/
  charter.md  brief.md          engine-written, agent-readable
  notes/{role}/                 free-form, namespaced so employees never collide
  artifacts/                    deliverables: written freehand, REGISTERED via the store
  workspace/                    the agent CWD; the site builds here
  _state/                       ENGINE ONLY, 0700, outside the agent workspace
    log.jsonl                   source of truth, append-only, fsynced
    projections/                generated; safe to delete
  shifts/{0007.json,0007.md}    the .md is engine-generated — agents never write
                                their own report card
```

Writes go through `BrainStore` under an `RLock` and a `FileLock`. Task claims are
compare-and-set, so two employees running in parallel cannot both take the same
task. Artifacts have one owning role per shift, enforced in the store rather than
requested in a prompt.

Operator commands:

```bash
uv run werkhaus facts    data/co_abc123     # summarise a brain
uv run werkhaus rebuild  data/co_abc123     # replay the log, rewrite projections
uv run werkhaus digest   data/co_abc123 --role researcher
uv run werkhaus scan     some/directory     # the publish gate, standalone
```

## Development

Two processes. The frontend only ever talks to its own origin — Vite proxies
`/api` and `/ws` to uvicorn — so there is no build-time backend URL.

```bash
uv sync
uv run uvicorn werkhaus.api.app:app --reload --port 8000
cd web && npm install && npm run dev        # http://localhost:5173
```

Engine selection is one environment variable:

```bash
WERKHAUS_ENGINE=null       # empty everywhere, heartbeats only
WERKHAUS_ENGINE=stub       # scripted scenarios, no LLM calls (use this)
WERKHAUS_ENGINE=openhands  # M3+: real agents, real money
```

### Demoing the stub

```bash
WERKHAUS_ENGINE=stub WERKHAUS_DATA=./data \
  uv run uvicorn werkhaus.api.app:app --reload --port 8000
```

Pick how a shift goes by putting a tag in the company description — the whole
failure matrix is one click away, on purpose:

| Scenario | What happens |
|---|---|
| `happy` | Six documents, two decisions, three objections, page ships |
| `budget_blowup` | Cap is hit mid-shift; company halts with work saved |
| `role_failure` | Kit's build fails; the shift finishes without him |
| `needs_attention` | Ines stops and asks you a question; company blocks |
| `firehose` | ~2,700 events in a minute — the load test |

```
A subscription box for ceramics [scenario:budget_blowup]
```

**Shifts run at real speed by default** (~15 minutes). That is deliberate: if the
team only ever sees a 20-second shift, nobody builds resumability, coalescing or
"leave and come back", and those are the three things that break at real latency.
To speed one up:

```bash
curl -X PUT localhost:8000/api/v1/_dev/speed \
  -H 'Content-Type: application/json' -d '{"speed":300}'
```

### Checks

```bash
uv run pytest                 # contract + AST guards + sdk seams
uv run ruff check .
cd web && npm run build       # tsc -b && vite build
```

### Regenerating frontend types

The OpenAPI schema is part of the contract, not a debugging convenience. With the
API running:

```bash
cd web && npm run types:gen   # -> src/api/types.gen.ts
```

CI should assert regeneration is a no-op.

## Notes

- `OPENHANDS_SUPPRESS_BANNER=1` is set in `werkhaus/api/app.py` — the SDK prints an
  ASCII ad to stderr on import.
- `~/.openhands/SOUL.md`, if it exists, silently replaces the identity paragraph of
  every agent system prompt. The engine asserts it is absent at startup.
- The SDK is MIT. Werkhaus is proprietary, which is fine; the obligation is
  retaining the notice in anything we distribute (`THIRD_PARTY_LICENSES.txt`, M6).
