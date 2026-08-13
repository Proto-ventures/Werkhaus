# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, and which one is primary is decided by conversion speed rather
than by preference — see Product Principles. Both are non-technical about
software and neither will ever see a terminal, a repository, a commit or a
traceback. The abstraction is a company with employees doing shifts.

- **The burned founder.** Has already tried two "AI writes your business plan"
  products. Not skeptical of AI — skeptical of *confident* AI. Would otherwise
  pay an agency for a market scan or lose three weekends doing it badly. Can
  tell a good idea from a bad one; cannot tell a researched number from an
  invented one, and knows it. Higher willingness to pay.
- **The builder subscriber.** Already paying for Lovable, Base44 or similar,
  already has something half-built, and has no defensible answer to whether it
  is worth building. Cheaper to reach, already spending, already in the
  category. This is the audience the live pricing comparison speaks to.

Explicitly not for: anyone who wants the product to *run* the business; a
technical founder who would rather drive the underlying coding agents; anyone
shopping against a $20/month plan generator, since the floor cost of a shift is
real money.

## Product Purpose

Someone describes a business in a sentence. An org of AI employees spends a
shift on the part that cannot be vibe-coded — who else is already selling this
and at what price, one price that can be defended, a money model with every
guess labelled, and where the first customers already are — and hands back a
folder of ordinary markdown the founder owns and can take anywhere.

Success is that the founder leaves with something they can put in front of
another person, and can tell which parts of it to trust.

Werkhaus sits *upstream* of the app builders. It does not build the app. The
brief goes to Lovable, Base44, Cursor or a developer.

## Positioning

**The one that shows its working and tells you what it made up.**

The category is discredited: a dozen tools return a fluent, unfalsifiable plan
with an invented market size and competitors that do not exist. Competing on
"better output" is a losing move, because the buyer cannot evaluate output
quality — that is the entire problem. The bet is that in a category where
nobody can judge the output, the buyer buys the thing that helps them judge the
output.

The mechanism a neighbouring product cannot truthfully copy is that this is
enforced in the schema rather than requested in a prompt:

- Every claim carries `sourced`, `inferred` or `assumption`. A document cannot
  be saved as sourced without the URLs an employee actually opened — a
  validator, not a system prompt. A cited page nobody visited is downgraded out
  loud.
- The money model stores its assumptions and has **no revenue field**. Revenue
  is arithmetic at the point of display, so a figure nobody earned cannot be
  stored as though somebody had.
- A critic is paid to attack the work and has no write access.
- A hard spending cap, and a stop that takes effect in under two seconds and
  keeps what was already done.

House framing, given by the founder: **European ingenuity and engineering,
brought to the wider world** — Europe is where it is built, not the limit of
who it is sold to. USA, Asia and Africa are in scope as markets.

## Operating Context

- A **shift** is one bounded run: an agenda, work, and a write-up, costing real
  money and roughly fourteen minutes.
- The unit of output is a **document** — ordinary markdown in a folder the
  founder owns, openable in front of an investor or a co-founder.
- Employees have names and jobs, never model or agent vocabulary. "Maya is
  reading competitor sites" is a company; "the researcher agent invoked
  browser_navigate" is a log. This is a hard rule in every user-facing surface.
- The company's state is an append-only log; everything else is a projection of
  it that can be deleted and rebuilt. "Nothing was lost" is meant literally.
- Two different kinds of money meet in the product and must never be presented
  as one: what running the company has cost (dollars that actually left, since
  model bills are dollar-denominated) and what the business would earn (a
  projection, in the currency the business would earn in).

## Capabilities and Constraints

**Shipped today.** One employee runs — Maya, the market researcher. She browses
the live web, writes one document, and files it through the company brain with
its provenance checked against the pages she actually loaded. Spending caps, the
stop, the brain, the ledger, provenance marks, the plan/allowance machinery, a
studio for reading output, and the marketing site.

**Designed and not shipped.** The other seven employees, including the critic
and the builder that would put a real page on the internet. A shift ends at the
documents today.

**Never.** Not "validated" — competitor pricing makes a price defensible, only a
customer validates one. Not a launch in an hour. Not a replacement for a
co-founder, an agency or a research team. Never contacts customers: outreach is
drafted, never sent. No invented market-size numbers in Werkhaus's own
marketing, for obvious reasons.

**The fiction ban.** A stub engine that replayed scripted shifts was deleted on
purpose: it was useful for building the interface without spending money, and it
was also a machine for producing convincing fiction — a founder watched a team
read pages nobody opened, about a business they had not described. Nothing may
reintroduce it in any form, including hand-built example output presented as
system output. Illustrative examples are permitted only where they are labelled
as examples.

**Undecided.** Whether the marketing surfaces should keep describing the full
roster in the present tense while one employee runs. The current, deliberate
answer is yes; it is recorded here as a choice rather than an oversight.

## Brand Commitments

- Name: **Werkhaus**. Repository org: Proto-ventures. Contact currently
  `research@euroswarms.eu`.
- Logos, supplied and shipped: `web/src/assets/werkhaus-full.svg` (the wordmark)
  and `web/public/favicon.svg` (the WH mark). Paths only, no live text; the
  fonts they were drawn in are not installable and must never be reintroduced
  as text.
- Voice: plain, specific, unhedged. States limits out loud, because for this
  buyer a stated limit converts better than a claim. No exclamation marks, no
  growth-copy register, no words the founder would not use.
- The "what we will not claim" list above is a brand commitment, not a caveat.
  If a claim would embarrass us in front of a customer who read the shift report
  carefully, it does not ship.

## Evidence on Hand

- **Real shift output exists**: `data/co_501050/workspace/market-research.md`
  and two other companies under `data/` — genuine documents from real runs.
  Local and gitignored, not published.
- **The worked example** on the marketing site is one fictional company in
  `web/src/routes/specimen.ts`, labelled as an example wherever it appears.
- **Competitor pricing** is verified from the vendors' own pages and dated on
  the site. Round-up articles have been wrong about it; do not use them.
- **Absent, and not to be fabricated**: customers, testimonials, case studies,
  logos of users, press, funding, team size, usage numbers, benchmarks, uptime,
  and any claim that a shift has produced a working website for anyone.

## Product Principles

1. **Revenue speed decides the audience.** Which of the two users is primary is
   a commercial question answered by what converts faster and larger, not by
   taste. Both stay in scope until the market answers; copy follows the money.
2. **Show the working.** Anything a buyer cannot check is worth nothing to this
   buyer. Provenance, the ledger, the cap, the stop and the critic's objections
   are the product, not reassurance around it.
3. **Never produce convincing fiction.** The whole position dies the first time
   we overclaim, and it dies silently — the buyer finds out later, in front of
   someone else.
4. **State the limit out loud.** A published boundary is the conversion
   mechanism for a burned buyer, not a cost.
5. **The founder can always stop, and never loses work.** Money and trust are
   both real; caps, the two-second halt and the append-only log exist so that
   walking away is safe.

## Accessibility & Inclusion

Binding, and future work may not regress it:

- **WCAG AA on every text colour, on both grounds, in both themes.** The
  large-text exemption is deliberately refused — almost nothing in the product
  is 18px and leaning on it would be dishonest.
- **Provenance is never carried by colour alone.** Sourced, inferred and
  assumption differ by shape as well as tone, so they survive greyscale, a
  printer, a screenshot pasted into a deck, and colour-blind readers. A number
  that leaves the product without its mark is the most expensive failure the
  product has.
