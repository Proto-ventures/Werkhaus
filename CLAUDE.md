# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Tests — the fast loop. ~10s for the whole suite; no offline mode exists, so
# this is how you develop against the engine without spending money.
uv run pytest tests/ -q
uv run pytest tests/contract/test_brain.py -q                    # one file
uv run pytest tests/contract/test_brain.py::test_the_log_is_the_source_of_truth
uv run ruff check werkhaus/ tests/

# Web (cd web)
npm run build         # tsc -b && vite build — the type check runs here too
npm run types:check   # tsc -b --noEmit
npm run lint          # oxlint. Pre-existing only-export-components warnings are noise
npm run dev           # :5173, proxies /api /ws /openapi.json to :8000

# Running it for real needs a model and a key — see README "Running it".
uv run uvicorn werkhaus.api.app:app --port 8000   # from a dir with no .env
uv run werkhaus reset ./data                      # start from nothing
```

`npm run types:gen` regenerates `web/src/api/types.gen.ts` from a **running**
API on :8000. Every new or changed contract model needs it, or the front end
codes against a stale schema.

## The three rules that hold the design together

1. **`werkhaus/contract/` is the only vocabulary the dashboard knows.** Nothing
   under `contract/`, `api/`, `brain/` or `share/` may import `openhands.*` —
   all SDK imports live under `werkhaus/engines/openhands/`. Pinned by
   `tests/contract/test_no_sdk_imports.py`.
2. **`software-agent-sdk/` is a read-only reference checkout, never a
   dependency.** We pin `openhands-sdk` from PyPI; the clone is for grepping.
3. **Every path handed to the SDK is absolute.** `file_editor` rejects relative
   paths and echoes the CWD into its own tool description, so a relative
   `WERKHAUS_DATA` costs a shift its whole turn budget. `tests/sdk_seams` pins it.

## Architecture

**One engine, and it calls real models.** A stub that replayed scripted shifts
was deleted on purpose: it was a machine for producing convincing fiction. Tests
drive the real engine with the SDK's scripted model instead. Never reintroduce a
fake engine, and never hand-build example output and present it as system
output — that is the same failure wearing a different hat.

**The brain is an append-only log.** `data/{cid}/_state/log.jsonl` is the source
of truth; `backlog.yaml`, `metrics.json`, `artifacts.json` and everything else
are projections that can be deleted and rebuilt (`werkhaus/brain/store.py`). No
fact may exist only in a projection — that is what makes "nothing was lost"
literal after a crash. Adding state means adding an op plus an `_on_<op>`
handler, never a field somebody sets directly.

**Provenance is structural, not a prompt request.** Every claim carries
`sourced` / `inferred` / `assumption`. A `sourced` artifact with no sources
fails a pydantic validator; a cited URL nobody visited is downgraded out loud.
In the UI the three are told apart by *shape* as well as colour — filled square,
plain square, hollow ring — because the expensive failure is a number leaving
the app in a screenshot without its mark.

**Two kinds of money, deliberately never mixed.** The ledger is dollars that
actually left our account (`LedgerEntry`, the studio's "what this costs"). The
`MoneyModel` is what the *business* would earn — and it has **no revenue
field**: it stores assumptions, and revenue is arithmetic done at display time
(`web/src/lib/finance.ts`), so a number nobody earned can never be stored as
though somebody had. `tests/contract/test_money_model.py` fails if the field
reappears.

**Prices live in `werkhaus/contract/plan.py`** next to what they buy. The
landing page is served as static files and quotes them from
`web/src/routes/specimen.ts`; `tests/contract/test_pricing.py` reads both and
fails if they drift.

**Names, not roles, in anything a user sees.** "Maya is reading competitor
sites" is a company; "the researcher agent invoked browser_navigate" is a log.
The eight employees live in `werkhaus/engines/roster.py`.

**Today one employee runs.** `shift.py` is Maya (`ROLE_ID = "researcher"`)
reading pages and filing one document. There is no critic module — Vera is a
roster row. The marketing page describes the finished product; that gap is a
known, deliberate decision, so check before "fixing" a claim.

## Front end

- **Tailwind v4 with `@theme inline`.** Dark mode works by redefining tokens in
  `.dark`, so `text-ink` / `bg-panel` / `border-rule` follow automatically.
  Do not add `dark:` utilities — a component author cannot forget the theme.
- **Three faces, one job each**: Newsreader for prose, Departure Mono for
  anything *measured* (money, ids, labels, buttons), IBM Plex Sans only for
  dense studio controls.
- **Motion**: ease `[0.22, 1, 0.36, 1]`, ~0.5s, honour `useReducedMotion()`, and
  **never animate opacity for visibility** — an element that starts invisible is
  missing when the animation does not run. Nothing loops; nothing moves unless
  the user moved it.
- **`specimen.ts` is the single source for the worked example** on the landing
  page, so the copy, the deck and the replay cannot drift.
- **The landing page must work with no backend.** `describeFailure` in
  `Landing.tsx` tells "the engine refused", "nothing is listening" and "this is
  a static preview" apart using the request id the API stamps on every response.

## Deploying

Netlify builds **from `main`** and serves it at `werkha.us`. There is no
`netlify.toml` — the site is linked from the Netlify dashboard, so nothing in
the repo reveals it. Pushing a feature branch deploys nothing.

`vite.config.ts` takes `base` from `WERKHAUS_BASE` (default `/`, which is what
Netlify and FastAPI both serve); the router reads `import.meta.env.BASE_URL` so
it cannot disagree with the asset paths.

## Verifying UI work

Headless Chromium is at
`~/.cache/ms-playwright/chromium-1223/chrome-linux64/chrome`. Two traps found
the hard way: it reports `window.innerWidth === 500` at narrower window sizes,
so drive device metrics over CDP rather than trusting `--window-size` for mobile
checks; and `--virtual-time-budget` does not advance CSS transitions or
`requestAnimationFrame`, so verify end states with
`--force-prefers-reduced-motion` or by driving a real page over the DevTools
protocol.
