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
WERKHAUS_ENGINE=openhands  # real employees, real money (M3: Maya only)
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

### Running the real engine (M3: one employee)

Maya, the market researcher, works for real: she browses the live web with a
headless browser, writes `market-research.md`, and files it through the company
brain. Her "sourced" labels are checked against the pages she actually loaded —
a cited URL she never visited is downgraded to "inferred", out loud.

```bash
export WERKHAUS_ENGINE=openhands
export WERKHAUS_DATA=./data-real
# Any litellm model string works. House preference: open-weight models first.
export WERKHAUS_MODEL="openrouter/qwen/qwen3-235b-a22b-2507"
export OPENROUTER_API_KEY=sk-or-...
# Or NVIDIA NIM: WERKHAUS_MODEL="nvidia_nim/moonshotai/kimi-k2-instruct"
#                NVIDIA_NIM_API_KEY=...
# Open-weight models are often missing from the cost tables, so tell the
# meters your provider's prices (dollars per million tokens):
export WERKHAUS_INPUT_COST_PER_MTOK=0.20
export WERKHAUS_OUTPUT_COST_PER_MTOK=0.60

uv run uvicorn werkhaus.api.app:app --port 8000   # run from a dir with no .env
```

Then create a company in the studio and start a shift, ideally with a focus
("Who sells ceramics subscription boxes in Germany and what do they charge?").
Knobs: `WERKHAUS_MODEL_KEY` / `WERKHAUS_MODEL_BASE_URL` override the provider
defaults; `WERKHAUS_BUDGET_CAP` (default 20.00) and `WERKHAUS_SHIFT_CAP`
(default 2.00) set new-company budgets; `WERKHAUS_NO_BROWSER=1` removes the
browser (research is then honest about being inferred). Maya's per-run cap is
$1.50 on top of a 5-second cost watchdog; one real shift runs at a time —
the browser is shared.

What to verify after a real shift: `data-real/co_*/workspace/market-research.md`
has real URLs; the artifact is `sourced` only for visited pages; the ledger has
a nonzero cost; `GET /api/v1/companies/{id}/events` reads like an employee, not
a model; halt mid-shift returns in under two seconds and nothing is lost.

#### Free-tier providers that can carry a shift

A shift is 30–80 model calls. Measured/verified against provider docs, Aug 2026
— these change often, re-check before relying on them:

| Provider (litellm prefix) | Key env | Free allowance | Shifts/day, roughly |
|---|---|---|---|
| Google AI Studio (`gemini/`) | `GEMINI_API_KEY` | ~1,500 req/day, 15/min | ~15–20 |
| Groq (`groq/`) | `GROQ_API_KEY` | 30/min, ~1k–14.4k/day by model | ~10–30 |
| Cerebras (`cerebras/`) | `CEREBRAS_API_KEY` | 30/min, 14.4k/day, 1M tok/day | ~10–20 |
| Mistral (`mistral/`) | `MISTRAL_API_KEY` | ~1B tok/month (opt-in training) | many |
| OpenRouter `:free` (`openrouter/`) | `OPENROUTER_API_KEY` | 50 req/day; 1,000/day after a one-time $10 | 0–1, then ~10 |
| NVIDIA NIM (`nvidia_nim/`) | `NVIDIA_NIM_API_KEY` | per-minute throttle; hot models saturated | varies |

On a free tier set `WERKHAUS_INPUT_COST_PER_MTOK=0 WERKHAUS_OUTPUT_COST_PER_MTOK=0`:
the ledger then reads $0.00 because the shift really was free, not because
litellm had no price for the model. Leave the rates at their defaults and the
meter estimates from token counts, so the budget watchdog still guards a model
the price map has never heard of.

Free tiers throttle by the minute; `WERKHAUS_LLM_RETRIES` /
`WERKHAUS_LLM_RETRY_MIN_WAIT` / `WERKHAUS_LLM_RETRY_MAX_WAIT` make the engine
wait out a window instead of failing the shift. Free usually also means the
provider trains on the traffic — say so anywhere a user brings their own key.

#### Plans and the free trial

`WERKHAUS_PLAN` selects a row of `werkhaus/contract/plan.py`. The default is
`pro` — self-hosted and development runs are ungated, because a local demo
should not hit someone else's paywall.

| | free | studio | pro |
|---|---|---|---|
| Shifts to start | 3 | 30 | uncounted |
| Refill | 1 every 7 days | 30 every 30 days | — |
| Bring your own key | no | no | **yes** |
| Autonomy | balanced ±1 | all five | all five |

Three rules make the numbers work, and each is a test:

- **The grant is the arc, not a round number.** Free has to reach something the
  founder can show someone, or they leave believing the product doesn't work.
  Re-measure the integer when the full roster lands; the arc is what's fixed.
- **The allowance is a projection.** Nothing decrements — usage is counted from
  the shifts in the brains, account-wide. A per-company allowance is one you
  refill by pressing "new company", and a counter is one that drifts.
- **A shift that produced nothing is not charged.** A shift that filed no
  document was our failure; billing a trial for it is how a bad day becomes a
  lost user. Same rule the employees work under, applied to the bill.

Bring-your-own-key is a vault entry named `WERKHAUS_MODEL_KEY` (plus
`WERKHAUS_MODEL` where model choice is included). Off-plan it is ignored rather
than rejected: upgrading should make a saved key start working, and downgrading
should move the company back onto ours instead of breaking it.

#### Connections

A company needs accounts of its own — a database, somewhere to be hosted, a way
to send email, a way to take money. **Every provider requires a human to create
the account and mint the first credential**; there is no automated path from
nothing to a working backend, and there never will be, because signing up is an
agreement a person makes. So the guided walkthrough in
`werkhaus/contract/catalog.py` is not a wrapper around the feature, it *is* the
feature, and its prose is the part a competitor can't copy from a docs page.

| | what it does | free | studio | pro |
|---|---|---|---|---|
| Supabase | database, accounts, storage | ✓ | ✓ | ✓ |
| Netlify | puts the site on the internet | ✓ | ✓ | ✓ |
| Resend | sends customers email | ✓ | ✓ | ✓ |
| Stripe | takes card payments (test mode) | | ✓ | ✓ |
| x402 | stablecoin payments (in testing) | | | ✓ |
| MoonPay | card-to-crypto — manual setup | | | ✓ |

Free gets the three with genuine free tiers, so a trial can reach a working
product without anyone entering card details. Deliberately absent: **Vercel**
(its MCP server only accepts an allowlist of approved clients, so an autonomous
agent can't use it), **Clerk** and **Twilio** (documentation search only — they
cannot touch a live instance). Listing them would be a lie.

Four rules, each with a test:

- **Checked before stored.** `werkhaus/engines/verify.py` calls the provider's
  cheapest read at the moment the key is pasted. A key that fails costs a shift,
  and the free plan has three — so a value that doesn't pass is never written
  anywhere.
- **Test mode first is a regex, not a branch.** Stripe's field only matches
  `rk_test_`, so a live key cannot be stored by a code path that forgot to check.
- **The database master key is refused by name**, from the guided flow *and* the
  raw vault. Handing a service-role key to an agent is the specific mistake
  behind the best-known leak of this kind, so it is unreachable rather than
  discouraged.
- **Connection state is derived** from the vault, the log and the plan. There is
  no stored flag to disagree with reality, and values never enter the append-only
  log — a secret written there could never be deleted.

Walkthrough pictures are a slot (`web/public/walkthroughs/`): every step must be
followable from its words alone, so screen recordings can be added later without
touching code.

#### The autonomy dial

Onboarding asks "how much should the team do on its own?" —
`full_auto | semi_auto | balanced | limited | full_control`, stored on the
charter, changeable in settings. Both ends spend faster: the auto end on
unattended shifts (finished shifts chain the next one, bounded by
`AUTO_CHAIN_LIMIT` and the money caps), the control end on questions and
planning. `balanced` is the default. The ask-before-deciding thresholds land
with the full roster in M4; today the dial controls chaining and the
onboarding depth.

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
- `~/.openhands/SOUL.md`, if it exists, would silently replace the identity
  paragraph of every agent system prompt. The engine neutralises it by always
  passing its own identity (`soul_content`) explicitly.
- The SDK is MIT. Werkhaus is proprietary, which is fine; the obligation is
  retaining the notice in anything we distribute (`THIRD_PARTY_LICENSES.txt`, M6).
