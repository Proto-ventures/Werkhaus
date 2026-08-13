---
target: the landing page
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 2
timestamp: 2026-08-13T12-08-30Z
slug: web-src-routes-landing-tsx
---
Method: dual-agent (A: design review, isolated · B: detector + browser evidence, isolated)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Reel, deck and busy states signal well; the textarea has no ceiling and no counter, so the 400-char cut is discovered at submit |
| 2 | Match System / Real World | 3 | Employee names and "shift"/"folder" are exemplary; broken by mixing $ and € in one price column |
| 3 | User Control and Freedom | 2 | The highest-intent click (`take the founding price`) opens an unannounced mailto and leaves the browser |
| 4 | Consistency and Standards | 2 | The provenance alphabet is spent as decoration — the hollow "guessed" ring labels the five claims the product is most certain about |
| 5 | Error Prevention | 2 | Disabled primary CTA gives no reason; no input ceiling; 15 of 18 tap targets under 44px |
| 6 | Recognition Rather Than Recall | 3 | The billing toggle silently rewrites a table five screens below; "€29 later" collides with Pro at €29/mo |
| 7 | Flexibility and Efficiency | 3 | Real accelerators exist (ctrl+enter, `?idea=` prefill) but ctrl+enter only appears after you type |
| 8 | Aesthetic and Minimalist Design | 3 | Section composition is beautiful; Pricing is six distinct blocks under one heading |
| 9 | Error Recovery | 4 | `describeFailure` tells three causes apart in plain language, persists inline, and says "Nothing you typed was lost" |
| 10 | Help and Documentation | 3 | The five nevers and the three objection tiles are the documentation, placed where the question arises; nothing explains what happens after the button |
| **Total** | | **28/40** | **Good — solid foundation, weak areas worth fixing** |

Both mode-optional heuristics (7 and 10) were scored rather than marked n/a: this page has genuine accelerators and genuine in-place documentation, so a number is more honest than an exemption.

## Design Specificity Verdict

**Authored, unusually so — but the authorship is concentrated in four objects, and the three sections carrying the money are the generic ones.**

The visual alphabet *is the product schema*. Three provenance states as filled square / filled square / hollow ring, one accent hue reserved for evidence, everything measured in a pixel mono and everything argued in a serif. A competitor pasting this template would be printing a legend for a validator they do not run.

Genuinely authored: the **Marks triptych** (one claim, three shapes, teaching the alphabet in three seconds against the same €29 that appears in the papers above); the **Field sections** (painting as ground, content as opaque sheets, theme toggle changing the hour rather than the art direction); the **Reel** (fourteen minutes played rather than claimed); the **Papers** (four documents whose mark density is legible from across a room).

Category-interchangeable: the **Pricing cards** are a stock three-column SaaS table with a billing pill — and they are what the page drives toward. The **Roster** is a stock 4x2 icon grid with no hierarchy between the employee that runs and the seven that do not.

**Structural sameness:** six of eight sections use the identical bar — left h2 at 2.1rem clamped to ~20ch (always breaking to exactly two lines), one soft paragraph, then a hairline grid of panels. Section eight looks exactly as important as section two.

**Missed character:** the money model having *no revenue field* is the only structurally impossible claim on the page, and it appears nowhere. The append-only log never shows. "Upstream of the app builders" — the entire wedge — is a hero sub-paragraph and a 10px footnote.

**Deterministic scan:** `detect.mjs` returned **exit 0, zero findings** across all seven assigned files. Verified as a real pass, not a silent one: a control scan of `web/src/` returns exit 2 with 6 `side-tab` findings, all outside this target (`dash.tsx:204`, `studio/planwork.tsx:527`, `studio/rail.tsx:465`, `lib/display.ts:24,30,38`). No rule suppression is configured.

**Browser evidence:** 0 console errors or warnings at both viewports. 0 horizontal overflow. 0 images missing alt (6 imgs: 1 meaningful, 5 explicitly decorative). Clean heading outline, exactly one h1, no skipped levels. **All 16 desktop / 14 mobile focusable elements have a visible focus indicator** — verified by dispatching real Tab presses and reading computed style, not by inspecting markup.

**Visual overlays:** script injection succeeded mechanically and an overlay node was appended, but the browser is headless — **no overlay is visible to a human**. There is no tab to look at.

## Overall Impression

This page is better than its score, and the score is dragged down by a handful of mechanical defects rather than by taste. The craft in the middle — marks, papers, paintings as ground, the replay — is category-leading and genuinely uncopyable. The problem is that the page is beautiful in the sections that persuade and generic in the sections that convert, and that its two most severe faults both attack the one thing it is selling: the disabled CTA fails the accessibility standard PRODUCT.md calls binding, and the print stylesheet deletes every provenance mark from the printed page.

The single biggest opportunity: **make the conversion sections as authored as the evidence sections.**

## What's Working

**1. The provenance triptych teaches an alphabet that survives leaving the page.** The three states differ by *shape* first, so the distinction survives greyscale, a printer and a screenshot pasted into a deck. The accessibility commitment and the commercial wedge are satisfied by one decision — which is what makes it worth more than either.

**2. The paintings are load-bearing, not decorative.** Content sits on canvas as opaque sheets rather than through a scrim, so the paint runs at full strength and every word sits on 4.5:1 stock; the contrast problem is avoided rather than half-solved. The dark palette is re-derived from the night canvases rather than dimmed from the day ones, which is why dark reads as a different hour instead of a filter.

**3. The failure copy is better than the success copy.** `describeFailure` distinguishes three causes and writes a different true sentence for each, including "You are looking at a preview" for the static build where "our server may be down" would be frightening and false. Almost nobody does this.

## Priority Issues

### [P0] The only button on the page is illegible and mute in its resting state
`.btn:disabled` sets `text-ink-faint`, but `.btn-primary` keeps `bg-ink`, so the hero CTA at rest is **3.14:1 in light and 2.06:1 in dark** (measured, not estimated). AA needs 4.5:1; dark fails even the 3:1 UI-component floor. It looks like a working primary button, and clicking it does nothing and says nothing — `begin()` returns early in silence. Every visitor sees this state first, and it breaks a standard PRODUCT.md records as binding.
**Fix:** keep the button enabled; on empty submit write into the existing `failed` panel ("Describe the business first — a sentence is enough.") and focus the textarea. If it must stay disabled, give `.btn-primary:disabled` a transparent ground with `border-rule-soft` so it reads as not-yet-available and clears contrast.
**Command:** `/impeccable harden`

### [P0] The print stylesheet deletes every provenance mark
`index.css:422` is a bare `[aria-hidden='true'] { display: none !important }`. Every `.mark` span carries `aria-hidden`. Printed, the papers become unattributed claims and the Marks triptych becomes three captions with nothing above them. PRODUCT.md: marks must survive "a printer, a screenshot pasted into a deck", and "a number that leaves the product without its mark is the most expensive failure the product has."
**Fix:** scope to the decoration it was written for — `[aria-hidden='true'] img` and the canvas wrappers — never bare `[aria-hidden='true']`.
**Command:** `/impeccable harden`

### [P1] Every path back to the input fails, including the last one on the page
Masthead `start one` is `<Link to="/">` — a no-op on the landing route. `start free` and Close's `start a company` are `href="#top"`, landing ~500px above the textarea without focusing it. `look at one that already ran` sends a stranger to "No companies yet", or hangs on `loading...` forever since `api.listCompanies()` has no `.catch`. The page builds intent for 7,269px and then has no working door.
**Fix:** one shared `startHere()` that scrolls the hero in and focuses the textarea, wired to all four. Point the proof link at a real published shift or cut it — a broken proof link on a page selling provenance costs more than the click it wins.
**Command:** `/impeccable clarify`

### [P1] The price and the cost instrument contradict each other inside one section
Studio is €8/month for "12 shifts a month". Three hundred pixels below: "$4 — what one shift spends on thinking", "$10 worst case". The reader multiplies, gets $48 of stated cost against €8 of revenue, and the page's own thesis turns against it. The rival table compounds it by putting $21, $16 and €8 in one column headed "a month, paid yearly".
**Fix:** state included model spend per card, and reframe the instrument as *the reader's* money — it is already titled "a cap you set", so label the bar "your shift, against your cap". Quote all three rivals in one currency, dated.
**Command:** `/impeccable clarify`

### [P2] The mark alphabet is spent as decoration three sections after it is taught
Pricing bullets are `mark mark-square bg-inferred`. The five nevers use `mark mark-ring` — the *assumption* glyph, "this is a guess" — to label the claims the product is most certain about. The page teaches "filled means read, hollow means guessed" at position 4 and contradicts it at 6, 7 and 8.
**Fix:** reserve square and ring exclusively for provenance page-wide. Pricing bullets become a rule or en-dash; the nevers get their own glyph.
**Command:** `/impeccable polish`

### [P2] The section order argues to the wrong reader in the wrong order
Papers uses ~22 marks before Marks explains what one is. The rival table — the object PRODUCT.md says exists for the builder subscriber — sits at position 7 of 8 with its decisive line ("they build what you tell them to build. we are the part that works out what to tell them") set as a 10px mono footnote *below* the table.
**Fix:** swap Marks above Leaves. Promote the footnote to the h3 above the table. Move Roster below Pricing and split it into "running today" and "designed, not shipped".
**Command:** `/impeccable layout`

## Persona Red Flags

**Jordan (first-timer):** "the part you cannot vibe code" is the fifth word of the value proposition and he does not know the phrase. The CTA at rest looks enabled, he taps, nothing happens and nothing is said — he assumes the site is broken. "START THE COMPANY" reads as incorporating a company. "TAP TO TAKE IT APART" names no object. He meets ~22 marks in the Papers before the legend one screen later. The hero's "employees paid to attack the rest — 1" is unparseable: attack what, who are the rest?

**Riley (stress tester):** twenty seconds with a calculator turns €8/mo × 12 shifts against $4/shift into either a fabricated $4 or a bait €8. "€29 once a shift ends with a live page" sits above a Pro card at €29/month. Three tenses about Kit in one viewport: hero says eight employees work, roster card 7 says not shipped, and inside the hero deck "Kit builds this during the first shift" sits directly above "When it exists". **The rival table cites no URLs** — the one page selling the rule that a sourced claim carries its page enforces it everywhere except on itself.

**Casey (one-handed mobile):** the deck eats a full screen height rendering 6–7px type that is unreadable at 390px, sitting exactly where momentum matters. `ShiftDiagram` binds only mouse and focus handlers, so a tap may open it with no way to close. "another example" is `hidden lg:inline`, so the one example he ever sees is the ceramics box and he cannot cycle it. Three full-height pricing cards stack to ~3 screens with Free first, burying the founding offer mid-stack. **Measured:** 13 of 18 interactive elements are under 44×44 on mobile — the theme toggle at 28×28, every primary CTA at 36px tall.

**Priya (builder subscriber, derived from PRODUCT.md):** her section is at position 7, after she has scrolled past a hero, a reel, four documents, a legend, three objections, eight employees and three pricing cards. Her one-line argument is styled as fine print. The table gives her three sentences to read where she needs one axis to see. She is anchored at $25/mo and the page will not do the one conversion that shows her what switching costs. "Every autonomy setting, including unattended" is internal vocabulary. And the upstream position — the whole wedge for her — is never drawn, while the page's one diagram shows a stack of studio screens.

## Minor Observations

- **Payload is 924.8 KB across 9 unique assets**, with `index.js` at 444.7 KB and `wheat.webp` at 269.3 KB — 87% of the page. No responsive image switching: mobile downloads the same 269 KB painting it never shows at full size.
- A **focusable non-semantic div** (the reel panel) sits in the tab order between "another example" and "playing".
- **Double error reporting:** `setFailed()` and `toast.error()` both fire, so the message appears inline *and* bottom-right — after a comment correctly arguing a toast is the wrong shape here.
- The Reel's replay control is a button that does nothing while reading "playing".
- **The hero art vanishes between 1024 and 1279px** (`hidden xl:block`), so a common laptop width gets a plain white hero and loses the art direction entirely.
- The cap bar loses its three zones in dark — spent, hatched worst case and headroom collapse to roughly two readable values.
- "No card" is stated four times in one section.
- No `maxLength` on the textarea; the 400-char cut applies only to the `?idea=` param.
- The `Sigil` icons are the one place the page reaches for stock iconography instead of its own three shapes.

## Questions to Consider

1. **If a shift costs $4 and Studio is €8/month for twelve, what is the page actually selling — and would printing that arithmetic *on purpose* be the most persuasive object on it?** A product built on "show your working" that publishes its own unit economics, including the part where the founding price loses money, is doing to itself exactly what it does to the customer.
2. **What if the five nevers included "never eight employees — one runs today, seven are designed"?** The limit is currently disclosed in the weakest position (card 7 of 8) instead of the strongest — the list whose entire purpose is stated limits.
3. **The money model has no revenue field. Why is that not the hero?** It is the only claim on the page that is a structural impossibility rather than a promise. Everything else asks to be believed; that one can be checked.
4. **What if the hero's primary object were the handoff rather than the studio?** The purchase decision is about what leaves the building — a folder that goes to Lovable. The one diagram is drawing the wrong noun.
5. **Is the mailto a bridge or the design?** The most valuable click on the page is converted into homework, on a surface that just spent 4,000px earning it.
