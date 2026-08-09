# The front page, walked through

A behavioural and heuristic evaluation of `web/src/routes/Landing.tsx`, done against the
method in the behavioural UI/UX skill: classify the task first, optimise ability before
motivation, and treat every persuasive mechanism as something that has to be justified rather
than assumed.

**This document is hypothesis generation, not findings.** Research on model-driven UX
evaluation is clear that it misses a substantial share of what human experts find and invents
problems that are not there. Nothing below has been watched happening to a real person. Every
item carries the evidence tier it actually rests on, and the last section says what would
settle it. The user's behaviour outranks anything asserted here.

Nothing in this document asks for a visual change. The design is not the problem.

---

## Who is reading, and what they are trying to do

From `positioning.md`, the buyer worth winning is the burned one. They have already tried two
of these. They are not skeptical of AI. They are skeptical of *confident* AI, and ordinary
marketing bounces off them.

That fixes the task. It is not "understand the product". It is:

> Decide whether this thing is honest enough to be worth describing my business to.

In Fogg's terms this is a one-time initiation of an unfamiliar behaviour, which is the
expensive corner of the grid. It also means motivation is not the lever. Somebody who arrived
here already wants what the page sells. What stops them is doubt, and doubt is an ability
problem: reduce uncertainty and the behaviour gets more likely without a single persuasive
device being added.

The page already understands this. Showing the output rather than describing it is the
correct strategy, and it is executed unusually well.

---

## Walkthrough

### Task 1 — understand what this is

Hero, `Landing.tsx:175-256`. Headline, lede, prompt box, three facts, live demo beside it.

Works. The h1 states the transaction in seven words, the facts row underneath is three
concrete proofs rather than three adjectives, and the demo is labelled `a recording · three
shifts, sped up` before it plays. A reader knows what they are looking at within one screen.

**Severity 0.**

### Task 2 — judge whether to trust it

Report section, `Landing.tsx:272-320`. A finished shift, rendered at the size it arrives,
labelled `a finished example · yours will be about your idea`.

This is the whole strategy and it is right. Describing the output would ask the reader to take
our word for it, and that is the one thing this product cannot ask for. Vera's objections
appearing inside the example is the strongest single element on the page: a product that
publishes its own critic is making a claim that cannot be faked cheaply.

One gap. `positioning.md` keeps a list titled *What we will not claim* — never "validated",
never "launch your startup in an hour", never "finds you customers". That list is the wedge,
and it appears nowhere on the page. For this specific buyer, stating limits is not a cost
paid against conversion. It is the conversion mechanism.

**Severity 2 — see F3.**

### Task 3 — act

The box, `Landing.tsx:190-236`, and the closing pair, `Landing.tsx:368-375`.

Three problems, in descending order of how much they cost.

---

## Findings

Severity: 0 none · 1 cosmetic · 2 minor friction · 3 major · 4 task-blocking.

### F1 — The only button on the page had no stated price · **3** · FIXED

`landing-page.md` specifies `free while we are testing` under the box before typing. The
shipped page had dropped it, so the footer row showed only `show another example`.

```
unpriced primary action
  → the reader cannot rule out being charged
  → hesitation at the exact moment of commitment
  → fewer companies started, by people who wanted one
```

Uncertainty is an interaction cost in the same way a click is, and it lands hardest on a
first-time irreversible-feeling action. Evidence: **heuristically recommended**, and it is
also simply restoring the page's own specification.

Fixed. The line is back in the empty state. `show another example` gives way below `sm`,
because the two do not fit on a narrow row and of the two, the price is the one that decides
whether anybody acts.

### F2 — "look at one that already ran" leads to "No companies yet" · **3**

`Landing.tsx:372` offers `look at one that already ran`. It links to `/companies`, which is
titled **Your companies** (`CompanyList.tsx:28`) and empty-states with **No companies yet**
(`CompanyList.tsx:42`).

```
link promises an example to inspect
  → reader expects evidence of other people's completed work
  → lands on their own empty list
  → the page's only social proof turns into a dead end
```

This is the clearest mismatch on the page between what a control promises and where it goes.
It matters more than its size suggests, because it is the secondary action for exactly the
reader who is not yet convinced by the example above it. That reader is the buyer.

Evidence: **empirically observed** in the code, and it is a straight violation of match
between system and real world.

Two ways out. Relabel the link to what it does. Or make it true by publishing one finished
example company through the existing share machinery (`werkhaus/share/snapshot.py`, which
already builds an immutable public snapshot behind the publish gate). The second is more work
and worth much more, because it turns a claim into an artefact a stranger can open.

### F3 — The limits are missing · **2**

Covered above. `positioning.md:65-78` exists and is good. None of it is on the page.

```
stated limits
  → reader updates towards "this one is not overclaiming"
  → skepticism stops being a reason to leave
  → higher trust at the same conversion, or higher both
```

Evidence: **theoretically plausible**. The dark-pattern literature shows manipulation costs
trust even when it converts; it does not directly show that volunteering limits raises
conversion. Worth an A/B rather than a redesign.

### F4 — The referral loop is invisible · **3**

`outreach.md` names the growth mechanic plainly: every delivered report should end with a
share link the founder can post, and a share page that hides the criticism is worth nothing to
us. The product implements it. The page never mentions it.

```
visible "you can publish this"
  → reader models the output as something shareable, not private
  → the artefact gets posted where other founders are
  → new visitors arrive with a worked example already in hand
```

This is the mechanism that answers "has them come back and bring more users in", and right
now a visitor cannot know it exists. Evidence: **theoretically plausible** for the effect,
**empirically observed** for the absence.

Cheapest honest version: the report section already carries an eyebrow. It could say the
example is a real share page. Nothing else on the page needs to move.

### F5 — Dev-time failure copy is user-facing · **4 if published**

`Landing.tsx:78-80` renders *We couldn't reach Werkhaus.* / *The server may not be running.*
That is exactly right on a laptop and wrong in front of a stranger, who cannot act on it and
will read it as the product being broken.

Not fixed, because it should not be fixed in isolation. It is correct until the day there is a
backend to reach, and on that day the whole pre-launch question changes. Recorded as a launch
blocker below.

### F6 — The closing CTA moves the reader instead of acting · **1**

`Landing.tsx:369` is `<a href="#top" className="btn btn-primary">start a company</a>`. It
scrolls to the hero and stops. The reader who has just finished the report, decided, and
pressed the button now has to find the box again and start typing.

Focusing the textarea after the scroll would close the gap. It is interaction-only, changes no
pixel, and is a small ability gain at the exact point where intent is highest. Not implemented
here because it was outside the approved scope; recommended next.

Evidence: **heuristically recommended**.

---

## What is already right, and should survive contact with future edits

Recorded because these are the things a well-meaning cleanup removes.

- **Everything is labelled as what it is.** `a recording · three shifts, sped up`. `a
  finished example · yours will be about your idea`. The museum captions on the paintings,
  because an unattributed background is decoration and this is a choice. This page tells you
  what you are looking at every single time. Very few do.
- **The placeholder does not type itself.** The comment at `Landing.tsx:52-55` gets this
  exactly right: an animated placeholder is indistinguishable from a pre-filled box, which
  makes one example business look like the only business Werkhaus can build.
- **The failure message stays on screen.** `Landing.tsx:58-60` refuses a toast, because a
  toast that fades is the wrong shape for "the only button on the page did not work".
- **Vera is in the example.** A product that shows its critic attacking its own demo is
  making the one claim competitors cannot cheaply copy.
- **Three facts, not six.** `three / one / every` reads in about a second.

---

## Counterfactuals

- **Remove the report section.** The page collapses to a claim about honesty with no evidence,
  which is the exact thing the target buyer has already been burned by twice. It is the most
  load-bearing section, not the hero.
- **Remove the collage.** The page still works and becomes forgettable. The paintings are what
  make an austere grid feel like it was made by people with taste, which is itself a trust
  signal for a product whose pitch is judgement.
- **Make `start the company` bigger.** Nothing improves. Salience is not the binding constraint
  here; doubt is. This is the trap the skill warns about, where persuasion gets used to paper
  over an ability problem.
- **Add a countdown or a signup counter.** Conversion might move. The position dies, because
  the entire wedge is being the one that does not do that.

---

## What would actually settle any of this

Everything above is a hypothesis. Ranked by how cheaply it can be killed:

| Question | Instrument |
|---|---|
| Does anyone reach the box? | Scroll depth to `#top` box vs. to the report section |
| Does the price line change anything? | A/B the empty-state microcopy, measure box focus rate |
| Is F2 real? | Click-through on `look at one that already ran`, then bounce rate on `/companies` |
| Do people describe a business and stop? | Textarea focus → characters typed → submit, as a funnel |
| Which ideas do people bring? | The text itself, once there is anywhere to put it |
| Does the example convince? | Time on the report section against submit rate |

Five founders watched using it beats all six rows.

---

## Before this page can be published

Not copy problems. Product ones.

1. There is no authentication anywhere in `werkhaus/api/`. The only dependency is
   `get_engine`.
2. `_WORK_SLOT = asyncio.Semaphore(1)` in `shift.py:69` is process-wide, so shifts are
   single-tenant by construction.
3. F5, which is only wrong once a stranger can see it.

Until those are answered, a public deploy hands any visitor the ability to spend the founder's
model budget and read every company's vault. The decision to hold the page is the right one,
and `outreach.md` already says why: a launch you can only do once should not be spent on a
stub.

## Domain groundwork, verified and banked

For whenever that day comes. `werkhaus.eu.cc` is delegated and controlled through GNAME.
`eu.cc` is on the Public Suffix List, so the domain behaves as a real registrable one: its own
cookie scope, and its own Let's Encrypt rate limit rather than a share of everybody else's.
Cloudflare accepts it as a full zone on the free plan. Cloudflare Pages builds from private
repositories, so no second public repository is needed to host anything.

No DNS record has been created. The domain resolves to nothing, deliberately.
