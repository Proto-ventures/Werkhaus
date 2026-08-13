import { useRef, useState } from 'react'
import { useTheme } from 'next-themes'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ApiError } from '@/api/client'
import { ShiftDiagram } from '@/components/diagram'
import { Papers } from '@/components/papers'
import { ShiftReel } from '@/components/reel'
import { Sigil, type SigilName } from '@/components/sigil'
import { cn } from '@/lib/utils'
import {
  FOUNDING,
  HEADER,
  MARK_EXAMPLES,
  OBJECTIONS,
  PRICING,
  RIVALS,
  RIVALS_CHECKED,
} from '@/routes/specimen'
import dandelions from '@/assets/dandelions.webp'
import milletNight from '@/assets/millet-night.webp'
import starryNight from '@/assets/starry-night.webp'
import wheat from '@/assets/wheat.webp'

/**
 * The front page, ordered by what the reader is actually doing.
 *
 * Their task is not "understand the product". The buyer worth winning has been
 * burned by two of these already and is skeptical of *confident* AI, so the
 * task is: decide whether this one is honest enough to describe a business to.
 *
 * That fixes the order. Evidence outranks the box — someone who types before
 * they trust bounces at the first number they cannot check — so a real finished
 * shift sits beside the headline rather than below the fold. The price sits on
 * the box, not in a footer. And the page says one thing Werkhaus will not do,
 * because for this reader a stated limit is the conversion mechanism rather
 * than a cost.
 *
 * Below the hero it is built out of things to look at rather than things to
 * read: a shift playing back, the documents as objects with their marks
 * showing, eight drawings, and one instrument for the money. The prose that
 * survived is there to caption a picture, never to carry the argument on its
 * own — a page of dense justified text is a page the reader's eye slides off,
 * however true every sentence in it is.
 */
export function Landing() {
  return (
    <>
      {/* The order is the order the questions arrive in: what is it, what
          happens if I press it, what do I get, who checks it, who are they,
          what does it cost and what won't it do. */}
      <Hero />
      <Reel />
      <Marks />
      <Leaves />
      <Objections />
      <Roster />
      <Pricing />
      <Close />
    </>
  )
}

/**
 * The one way back to the box.
 *
 * Four separate controls promised to start a company and none of them worked:
 * the masthead button was a Link to the route it was already on, and the two
 * `#top` anchors landed half a screen above the textarea without focusing it.
 * A page that spends seven thousand pixels building intent has to have a door.
 */
export function startHere() {
  const box = document.getElementById('idea-box')
  if (!box) return false
  box.scrollIntoView({ block: 'center', behavior: 'smooth' })
  // After the scroll, or the browser fights the focus and jumps twice.
  window.setTimeout(() => box.focus({ preventScroll: true }), 320)
  return true
}

const IDEAS = [
  'A monthly subscription box for hand-thrown ceramics, one object a month from a named potter.',
  'A booking tool for mobile dog groomers who currently run everything through WhatsApp.',
  'A refill service for cleaning products, delivered by cargo bike.',
]

/**
 * The canvases, and which hour it is.
 *
 * Light and dark are not two moods. They are the same two painters at the same
 * place at different hours: Van Gogh's Wheat Field with Cypresses and his
 * Starry Night are both Saint-Rémy, 1889, the second painted from the window of
 * his room there. Millet is the elder painter he revered, and Millet's own
 * Starry Night is one he may have seen in Paris in 1873-75.
 *
 * So the toggle changes the hour, not the art direction, and the captions can
 * say so. An unattributed background is decoration; a labelled one is a choice.
 */
function useCanvases() {
  const { resolvedTheme } = useTheme()
  const night = resolvedTheme === 'dark'
  return night
    ? {
        wide: starryNight,
        wideCaption: 'the starry night · van gogh · 1889',
        narrow: milletNight,
        narrowCaption: 'starry night · millet · c.1850',
      }
    : {
        wide: wheat,
        wideCaption: 'wheat field with cypresses · van gogh · 1889',
        narrow: dandelions,
        narrowCaption: 'dandelions · millet · 1868',
      }
}

/**
 * A section standing on a painting.
 *
 * The canvases used to sit in a column *beside* the words, which makes them
 * illustrations of a paragraph — decoration, and the first thing an eye learns
 * to skip. Here the painting is the ground the whole section is built on and
 * the content is laid on top of it as opaque sheets, the way paper sits on a
 * table. The paint runs at full strength because nothing is asked to be legible
 * through it: every word on this page is on solid ink-on-paper, and the margin
 * around the sheets is where the painting does its work.
 */
function Field({
  which,
  focus,
  children,
  className,
}: {
  which: 'wide' | 'narrow'
  focus: string
  children: React.ReactNode
  className?: string
}) {
  const canvas = useCanvases()
  const src = which === 'wide' ? canvas.wide : canvas.narrow
  return (
    <section className={`border-rule-soft relative border-b ${className ?? ''}`}>
      <img
        src={src}
        alt=""
        aria-hidden
        loading="lazy"
        style={{ objectPosition: focus }}
        className="absolute inset-0 size-full object-cover"
      />
      <div className="relative mx-auto max-w-6xl px-4 py-12 sm:px-8 sm:py-20 lg:py-28">
        {children}
      </div>
    </section>
  )
}

/** A heading and at most a sentence, on a sheet, so it can sit on paint. */
function Placard({
  title,
  children,
  className,
}: {
  title: string
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div className={`panel max-w-xl p-6 sm:p-8 ${className ?? ''}`}>
      <h2 className="display max-w-[20ch] text-2xl leading-tight sm:text-[2.1rem]">
        {title}
      </h2>
      {children && (
        <p className="text-ink-soft mt-4 text-[1.0625rem] leading-[1.6]">{children}</p>
      )}
    </div>
  )
}

function Hero() {
  const navigate = useNavigate()
  const canvas = useCanvases()
  // Arriving from a guide page means the idea has already been chosen, so the
  // box is not empty. Read once into state rather than held in the URL: the
  // first keystroke is theirs, and it should not be fighting a query string.
  const [params] = useSearchParams()
  const [idea, setIdea] = useState(() => params.get('idea')?.slice(0, 400) ?? '')
  const box = useRef<HTMLTextAreaElement>(null)
  const [busy, setBusy] = useState(false)
  // A placeholder that types itself is indistinguishable from a box that came
  // pre-filled, which makes one example business look like the only business
  // Werkhaus can build. It says "for example", it doesn't move, and you change
  // it by asking.
  const [example, setExample] = useState(0)
  const placeholder = `For example: ${IDEAS[example % IDEAS.length]}`

  // A toast that fades is the wrong shape for "the only button on the page
  // didn't work": the reason has to stay on screen next to the button.
  const [failed, setFailed] = useState<{ message: string; hint?: string } | null>(
    null,
  )

  async function begin() {
    // An empty box is not an error, it is an unfinished sentence — so the
    // button stays live and says what is missing, in the panel that already
    // exists for the other three ways this can fail. It used to sit disabled
    // instead, which read as a working button, said nothing when pressed, and
    // was the first thing every visitor saw.
    if (!idea.trim()) {
      setFailed({
        message: 'Tell it what the business is first.',
        hint: 'One sentence is enough — what it sells, and who to.',
      })
      box.current?.focus()
      return
    }
    setBusy(true)
    setFailed(null)
    try {
      const company = await api.createCompany(idea.trim())
      navigate(`/c/${company.id}`)
    } catch (e) {
      const failure = describeFailure(e)
      setFailed(failure)
      setBusy(false)
    }
  }

  return (
    // `overflow-x-clip` rather than `hidden`: the diagram is drawn wider than
    // its column on purpose and runs off the right edge, and clip cuts it
    // without turning the section into a scroll container.
    <section id="top" className="border-rule-soft relative overflow-x-clip border-b">
      {/* The canvases carry the ground. Both hang full height, one either side,
          meeting behind a clear band down the middle where the words live. The
          band is solid rather than a scrim: text on top of oil paint is a
          contrast problem you can only ever half-solve, and this way the
          paintings can run at full strength instead of being turned down to
          make room. Below xl there is no room for a margin, so they go. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 hidden lg:block">
        <img
          src={canvas.wide}
          alt=""
          loading="eager"
          className="absolute inset-y-0 left-0 h-full w-[42%] object-cover"
        />
        <img
          src={canvas.narrow}
          alt=""
          loading="eager"
          className="absolute inset-y-0 right-0 h-full w-[42%] object-cover"
        />
        {/* The clear band, with its edges dissolved into the paint so the
            middle reads as a lit clearing rather than a pasted rectangle. */}
        <div
          className="absolute inset-y-0 left-1/2 w-[70%] -translate-x-1/2"
          style={{
            background:
              'linear-gradient(to right, transparent, var(--paper) 5%, var(--paper) 95%, transparent)',
          }}
        />
      </div>

      <div className="relative mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] gap-10 px-5 py-14 sm:px-8 lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] lg:gap-12 lg:py-20 xl:max-w-5xl xl:py-24">
        <div>
          <h1 className="display text-[1.85rem] leading-[1.06] sm:text-[2.4rem] lg:text-[3.1rem]">
            Describe a business.
            <br />
            Find out if it&rsquo;s worth building.
          </h1>

          {/* The offer, in the order it is wanted: what you get, how long it
              takes, and where it goes afterwards. The hand-off is said out
              loud because the alternative is letting a reader assume we build
              the app and discover otherwise — which is the one mistake on this
              page we cannot take back. */}
          <p className="text-ink-soft mt-6 max-w-[47ch] text-[1.0625rem] leading-[1.65]">
            Eight employees spend fourteen minutes on the part you cannot vibe
            code: the rivals and what they charge, one price you can defend, a
            money model with every guess labelled, and where your first
            customers already are. Every claim says where it came from.
          </p>

          <p className="text-ink-soft mt-3 max-w-[47ch] text-[1.0625rem] leading-[1.65]">
            You leave with a folder of ordinary files. Build it in Lovable,
            Base44, Cursor, or hand it to a developer.
          </p>

          <div className="border-rule mt-9 border">
            <textarea
              id="idea-box"
              ref={box}
              value={idea}
              onChange={(e) => {
                setIdea(e.target.value)
                // The complaint was "you have not said what it is". The first
                // keystroke answers it, so the panel goes then rather than
                // sitting there contradicting the box above it.
                if (failed) setFailed(null)
              }}
              rows={3}
              placeholder={placeholder}
              className="placeholder:text-ink-faint bg-panel block w-full resize-none px-4 py-4 text-[0.9375rem] leading-relaxed outline-none focus-visible:ring-ring focus-visible:ring-2"
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) void begin()
              }}
            />
            <div className="border-rule-soft bg-panel flex flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t px-4 py-3">
              {idea.trim() ? (
                <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] whitespace-nowrap uppercase">
                  ctrl + enter
                </span>
              ) : (
                // What the only button on the page costs, said before it is
                // pressed. An unpriced action is a reason not to press it, and
                // the example link gives way below sm because of the two, the
                // price is what decides whether anybody acts.
                <span className="flex items-center gap-3">
                  <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] whitespace-nowrap uppercase">
                    no card needed
                  </span>
                  <button
                    type="button"
                    onClick={() => setExample((n) => n + 1)}
                    className="text-link -m-3 inline-flex min-h-11 items-center p-3 font-mono text-[0.6875rem] whitespace-nowrap underline"
                  >
                    another example
                  </button>
                </span>
              )}
              <button
                type="button"
                className="btn btn-primary ml-auto"
                // Only while a company is actually being created. Disabling on
                // an empty box is what made the page's one button mute.
                disabled={busy}
                onClick={begin}
              >
                {busy ? 'setting up' : 'start the company'}
              </button>
            </div>
            {failed && (
              <div className="border-rule-soft bg-panel border-t px-4 py-3">
                <p className="text-red text-[0.875rem] leading-snug">
                  {failed.message}
                </p>
                {failed.hint && (
                  <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
                    {failed.hint}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* The facts as a reading off an instrument rather than three
              headlines. They are measurements, and measurements are set in
              the mono face everywhere else in the product. */}
          <dl className="mt-9 max-w-[30rem]">
            <div className="spec">
              <dt>one shift takes</dt>
              <dd>14 min</dd>
            </div>
            <div className="spec">
              <dt>free to start</dt>
              <dd>3 shifts</dd>
            </div>
            <div className="spec">
              <dt>employees paid to attack the rest</dt>
              <dd>1</dd>
            </div>
          </dl>
        </div>

        {/* Evidence, beside the headline rather than below it. Labelled,
            because an unlabelled demo of one example business is how a product
            comes to look like it only builds that business. */}
        <div className="lg:pt-6">
          <ShiftDiagram idea={idea} />
        </div>
      </div>
    </section>
  )
}

/**
 * Three ways starting a company can fail, and they are not the same sentence.
 *
 * The engine answered and refused: it wrote prose for this, so use it. Nothing
 * answered at all: on a laptop that means the server is not running, which is
 * a thing the person reading it can actually fix. Something answered but it
 * was not the engine: this build is being served without one, which is what
 * the public page is until there is somewhere to put a company. Telling a
 * stranger our server may be down would be alarming, and it would also be
 * false.
 *
 * The three are told apart without a build flag or a configured URL, because
 * the client is origin-relative on purpose and should stay that way. Every
 * reply from the engine carries a request id (``attach_request_id`` in
 * ``api/app.py`` sets one on every response), so ``req_unknown`` means the
 * reply came from something else — a static host answering with its own 404,
 * or an index.html served in place of an API.
 */
function describeFailure(e: unknown): { message: string; hint?: string } {
  const detail = (e as { detail?: ApiError }).detail
  if (detail && detail.request_id !== 'req_unknown') {
    return { message: (e as Error).message, hint: detail.hint ?? undefined }
  }
  // fetch rejects with a TypeError when it cannot connect at all. Its message
  // is "Failed to fetch", which is true and useless to the person reading it.
  if (e instanceof TypeError) {
    return {
      message: "We couldn't reach Werkhaus.",
      hint: 'The server may not be running. Nothing you typed was lost.',
    }
  }
  return {
    message: 'Werkhaus is not open yet.',
    hint: 'You are looking at a preview. Nothing you typed was lost, and the recording above is a real shift.',
  }
}

/**
 * A shift, played rather than described.
 *
 * This section used to be a paragraph explaining what happens in fourteen
 * minutes. Nobody reads a paragraph about a process. Watching an empty folder
 * fill up, with the clock and the meter running beside it, is the same
 * information in a form the eye will actually stay on.
 */
function Reel() {
  return (
    <section className="border-rule-soft border-b">
      <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
        <h2 className="display max-w-[22ch] text-2xl leading-tight sm:text-[2.1rem]">
          Fourteen minutes, from an empty folder.
        </h2>
        <p className="text-ink-soft mt-4 max-w-[54ch] text-[1.0625rem] leading-[1.6]">
          Not a progress bar. Pages get opened, documents land with the mark
          they earned, what it costs us climbs, and what the business would earn
          fills in one defensible number at a time.
        </p>
        <ShiftReel className="mt-10" />
      </div>
    </section>
  )
}

/**
 * What a shift leaves behind, as four things rather than four filenames.
 *
 * The list of names told you the documents existed. The pages show you what is
 * inside them and which marks they carry, which is the only part a reader
 * cannot take on trust — and they are laid straight onto the painting, because
 * a sheet of paper on a table is what they are.
 */
function Leaves() {
  return (
    <Field which="wide" focus="30% 70%">
      <Placard title="Four documents you can open in front of someone.">
        Ordinary markdown in a folder you own. Every claim carries a mark saying
        where it came from, because you cannot check a hundred pages of research
        and you can check a mark.
      </Placard>
      <Papers className="mt-8 sm:mt-10" />
    </Field>
  )
}

/**
 * The wedge, shown rather than described.
 *
 * Everything else on this page is a claim about honesty, which is exactly what
 * this reader has been burned by twice. This is the mechanism: one sentence
 * about one rival, three times, under the three marks — so the difference
 * between "we read this" and "we made this up" is a shape you can see rather
 * than a policy you have to believe.
 */
function Marks() {
  return (
    <section className="border-rule-soft border-b">
      <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
        <h2 className="display max-w-[24ch] text-2xl leading-tight sm:text-[2.1rem]">
          Filled means read. Hollow means guessed.
        </h2>

        <ul className="mt-10 grid gap-px sm:grid-cols-3 sm:bg-rule-soft">
          {MARK_EXAMPLES.map((r) => (
            <li key={r.mark} className="bg-panel border-rule-soft border p-6 sm:border-0">
              <span
                aria-hidden
                className={
                  r.mark === 'assumption'
                    ? 'mark mark-ring border-assumption !size-5 border-[3px]'
                    : r.mark === 'sourced'
                      ? 'mark mark-square bg-sourced !size-5'
                      : 'mark mark-square bg-inferred !size-5'
                }
              />
              <p className="text-ink-faint mt-4 font-mono text-[0.6875rem] tracking-[0.12em] uppercase">
                {r.mark}
              </p>
              <p className="display mt-2 text-[1.25rem] leading-tight">{r.claim}</p>
              <p className="text-ink-soft mt-3 text-[0.875rem] leading-relaxed">
                {r.behind}
              </p>
            </li>
          ))}
        </ul>

        <p className="text-ink-faint mt-5 font-mono text-[0.6875rem] leading-relaxed">
          the shape survives a screenshot, a printer, and being pasted into a deck
        </p>
      </div>
    </section>
  )
}

/**
 * Vera, at the end of every shift.
 *
 * The strongest thing the product does. Each objection is a card with a torn
 * edge of its own severity, because three of them in a column of prose read as
 * a disclaimer and a disclaimer is the one thing this cannot be: she names a
 * claim, and she names what would settle it.
 */
function Objections() {
  return (
    <Field which="narrow" focus="60% 40%">
      <Placard title="Then someone is paid to pull it apart.">
        Vera runs at the end of every shift, including the ones that ran out of
        budget. She has no write access, and every objection names what would
        settle it.
      </Placard>

      <ul className="mt-8 grid gap-4 sm:mt-10 lg:grid-cols-3">
        {OBJECTIONS.map(({ severity, about, text, settled }) => (
          <li key={about} className="panel flex flex-col p-5 sm:p-6">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                className={
                  severity === 'serious'
                    ? 'mark mark-triangle text-red'
                    : 'mark mark-square bg-ink-faint'
                }
              />
              <span
                className={
                  severity === 'serious'
                    ? 'text-red font-mono text-[0.6875rem] tracking-[0.12em] uppercase'
                    : 'text-ink-faint font-mono text-[0.6875rem] tracking-[0.12em] uppercase'
                }
              >
                {severity}
              </span>
              <span className="text-ink-faint ml-auto truncate font-mono text-[0.625rem]">
                {about}
              </span>
            </div>

            <p className="mt-3 text-[1.0625rem] leading-snug">{text}</p>

            <p className="border-rule-soft text-ink-soft mt-auto border-t pt-3 text-[0.8125rem] leading-relaxed">
              <span className="text-ink-faint block font-mono text-[0.625rem] tracking-[0.1em] uppercase">
                settled by
              </span>
              {settled}
            </p>
          </li>
        ))}
      </ul>
    </Field>
  )
}

/** The eight, and what each one is for. */
const PEOPLE: { id: SigilName; name: string; job: string; does: string }[] = [
  {
    id: 'chief',
    name: 'ada',
    job: 'chief of staff',
    does: 'Sets what the company works on, and writes up what happened.',
  },
  {
    id: 'researcher',
    name: 'maya',
    job: 'market researcher',
    does: 'Reads real competitor sites. Reports only what she can source.',
  },
  {
    id: 'strategist',
    name: 'ines',
    job: 'strategist',
    does: 'One audience, one price. Commits to an answer, not a menu.',
  },
  {
    id: 'brand',
    name: 'otto',
    job: 'brand & copy',
    does: "Writes the words, in the customer's language rather than the company's.",
  },
  {
    id: 'growth',
    name: 'rafa',
    job: 'growth',
    does: 'Finds where the audience already is. Drafts outreach — never sends it.',
  },
  {
    id: 'analyst',
    name: 'nia',
    job: 'numbers',
    does: 'Builds the money model and labels every assumption in it.',
  },
  {
    id: 'engineer',
    name: 'kit',
    job: 'builder',
    does: 'Will build the landing page. Not shipped yet — today a shift stops at the documents.',
  },
  {
    id: 'critic',
    name: 'vera',
    job: "devil's advocate",
    does: 'Paid to be wrong-proof, not agreeable. Files objections you can check.',
  },
]

function Roster() {
  return (
    <section className="border-rule-soft border-b">
      <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
        <h2 className="display max-w-[18ch] text-2xl leading-tight sm:text-[2.1rem]">
          Eight of them, and what each one is for.
        </h2>

        {/* A hairline grid, drawn once by the gap, the way a spec sheet rules
            a table. Eight cards with eight borders is eight boxes; this is one
            plate divided up. */}
        <ul className="bg-rule-soft border-rule-soft mt-10 grid gap-px border sm:grid-cols-2 lg:grid-cols-4">
          {PEOPLE.map((p) => (
            <li key={p.name} className="bg-panel flex flex-col p-5">
              <Sigil name={p.id} className="text-ink size-8" />
              <p className="mt-4 font-mono text-[0.8125rem] tracking-[0.1em] uppercase">
                {p.name}
              </p>
              <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.06em] uppercase">
                {p.job}
              </p>
              <p className="text-ink-soft mt-2.5 text-[0.875rem] leading-relaxed">
                {p.does}
              </p>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}

/**
 * What Werkhaus will not claim, kept beside what it charges.
 *
 * Taken from positioning.md, which holds this list precisely so the temptation
 * to overclaim has somewhere to break against. The first entry is the one that
 * matters against a builder: they ship an app, we do not.
 */
const NOTS: [string, string][] = [
  ['a builder', 'It works out what to build. Building it is Lovable, Base44, Cursor, or a developer.'],
  ['validated', 'Competitor pricing makes a price defensible. Only a customer validates one.'],
  ['a launch in an hour', 'A shift gets you something to show. That is not the same as a business.'],
  ['a replacement for a co-founder', 'It does groundwork. It does not do judgement.'],
  ['customers', 'Rafa drafts outreach. Nothing is ever sent on your behalf.'],
]

/** Where the money goes, drawn to scale. */
const CAP = 20

/**
 * The price, printed, and sold.
 *
 * The page had a cost section with no prices in it, which is the shape of a
 * product that is not for sale — and this one is, on purpose, before it is
 * finished. So every lever that is honestly available is pulled: the number is
 * under what a reader is already paying elsewhere, the annual saving is stated
 * in euros rather than in a percentage nobody converts, the reason it is cheap
 * is the same reason to take it now, and the row that would stop a burned buyer
 * (what happens to the price later) is answered before they can ask it.
 *
 * The comparison table is the part that does the work. It is not there to say
 * we are cheaper — it is there to say we are cheaper *and doing the other
 * half of the job*, which is the only argument that survives someone who
 * already has a Lovable subscription.
 */
function Pricing() {
  // Yearly first. It is the better price for them and it is cash now for us,
  // and a toggle that opens on the worse number is a toggle nobody moves.
  const [yearly, setYearly] = useState(true)
  const founding = PRICING.find((t) => t.featured)
  const mail = (tier: string) =>
    `mailto:${FOUNDING.contact}?subject=${encodeURIComponent(
      `Werkhaus ${tier} — a founding place`,
    )}&body=${encodeURIComponent(
      'The business I would describe first:\n\n\nHow soon I would want to start:\n',
    )}`

  return (
    <section id="pricing" className="border-rule-soft border-b">
      <div className="mx-auto max-w-6xl px-5 py-16 sm:px-8 lg:py-24">
        <div className="flex flex-wrap items-end justify-between gap-x-8 gap-y-6">
          <div>
            <h2 className="display max-w-[20ch] text-2xl leading-tight sm:text-[2.1rem]">
              Less than the thing that builds it.
            </h2>
            <p className="text-ink-soft mt-4 max-w-[54ch] text-[1.0625rem] leading-[1.6]">
              Deciding what to build should not be the expensive half of your
              stack. Start free, with no card. Keep the folder either way.
            </p>
          </div>

          {/* The saving in euros, on the control that produces it. A percentage
              is a number the reader has to do arithmetic on before it means
              anything, and they will not. */}
          <div className="border-rule flex shrink-0 border">
            {(['yearly', 'monthly'] as const).map((mode) => (
              <button
                key={mode}
                type="button"
                onClick={() => setYearly(mode === 'yearly')}
                aria-pressed={yearly === (mode === 'yearly')}
                className={cn(
                  'focus-visible:ring-ring inline-flex min-h-11 items-center px-4 font-mono text-[0.6875rem] tracking-[0.08em] uppercase focus-visible:ring-2 focus-visible:outline-none',
                  yearly === (mode === 'yearly')
                    ? 'bg-ink text-paper'
                    : 'text-ink-soft hover:bg-secondary',
                )}
              >
                {mode}
                {mode === 'yearly' && founding?.price && founding.year
                  ? ` · save €${founding.price * 12 - founding.year}`
                  : ''}
              </button>
            ))}
          </div>
        </div>

        <ul className="bg-rule-soft border-rule-soft mt-10 grid gap-px border lg:grid-cols-3">
          {PRICING.map((tier) => {
            const monthly = yearly && tier.year ? tier.year / 12 : tier.price
            return (
              <li key={tier.plan} className="bg-panel flex flex-col p-6 sm:p-7">
                {/* A full strip rather than a corner tab: a tab on the right
                    edge of the middle card sits on the seam with the next one
                    and reads as labelling either. */}
                {tier.featured && (
                  <span className="bg-ink text-paper -mx-6 -mt-6 mb-5 block px-6 py-1.5 font-mono text-[0.625rem] tracking-[0.1em] uppercase sm:-mx-7 sm:-mt-7 sm:px-7">
                    founding price
                  </span>
                )}
                <p className="font-mono text-[0.8125rem] tracking-[0.12em] uppercase">
                  {tier.label}
                </p>
                <p className="text-ink-soft mt-1.5 max-w-[26ch] text-[0.875rem] leading-snug">
                  {tier.pitch}
                </p>

                <p className="mt-6 flex items-baseline gap-2">
                  <span className="numeric text-[2.5rem] leading-none">
                    {monthly === null || monthly === undefined
                      ? 'Free'
                      : `€${monthly % 1 === 0 ? monthly : monthly.toFixed(2)}`}
                  </span>
                  {monthly != null && (
                    <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] uppercase">
                      a month
                    </span>
                  )}
                </p>
                <p className="text-ink-faint mt-1.5 font-mono text-[0.625rem] leading-relaxed">
                  {monthly == null
                    ? 'no card, no trial clock'
                    : yearly
                      ? `€${tier.year} once a year`
                      : 'billed monthly, cancel whenever'}
                </p>

                <ul className="mt-6 flex-1 space-y-2.5">
                  {tier.gets.map((line) => (
                    <li key={line} className="flex items-baseline gap-2.5">
                      {/* A rule, not a mark. Square and ring mean sourced and
                          guessed; spending them on feature bullets three
                          sections after the page teaches that is how an
                          alphabet stops meaning anything. */}
                      <span
                        aria-hidden
                        className="bg-rule mt-[0.6em] h-px w-2 shrink-0"
                      />
                      <span className="text-ink-soft text-[0.875rem] leading-snug">
                        {line}
                      </span>
                    </li>
                  ))}
                </ul>

                <a
                  onClick={(e) => {
                    if (tier.price === null && startHere()) e.preventDefault()
                  }}
                  href={tier.price === null ? '#top' : mail(tier.label)}
                  className={cn('btn mt-7 w-full', tier.featured ? 'btn-primary' : '')}
                >
                  {tier.price === null
                    ? 'start free'
                    : tier.featured
                      ? 'take the founding price'
                      : 'ask about pro'}
                </a>
              </li>
            )
          })}
        </ul>

        {/* The two objections a reader has at this exact point, answered where
            they have them rather than in a FAQ nobody opens. */}
        <div className="border-rule-soft mt-6 grid gap-px bg-rule-soft border sm:grid-cols-3">
          {[
            ['the price later', `€${FOUNDING.then} once ${FOUNDING.until}. Join before then and you keep yours.`],
            ['a shift that filed nothing', 'Not charged. Our failure, not your bill.'],
            ['getting your work out', 'Ordinary markdown in a folder. Nothing is locked in ours.'],
          ].map(([term, answer]) => (
            <div key={term} className="bg-panel p-4">
              <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.08em] uppercase">
                {term}
              </p>
              <p className="text-ink-soft mt-1.5 text-[0.875rem] leading-snug">{answer}</p>
            </div>
          ))}
        </div>

        <p className="text-ink-faint mt-4 font-mono text-[0.6875rem] leading-relaxed">
          no card is taken on this page · a founding place is arranged by email
          until there is a checkout worth pointing you at
        </p>

        {/* ------------------------------------------------ against the others */}
        <h3 className="display mt-16 max-w-[30ch] text-xl leading-tight sm:text-2xl">
          They build what you tell them to build. We are the part that works
          out what to tell them.
        </h3>
        <p className="text-ink-soft mt-3 max-w-[52ch] text-[1rem] leading-relaxed">
          You are probably already paying for one of these.
        </p>
        <table className="mt-6 w-full border-collapse text-left">
          <thead>
            <tr className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
              <th scope="col" className="border-rule-soft border-b py-2 font-normal">
                tool
              </th>
              <th scope="col" className="border-rule-soft border-b py-2 font-normal">
                {yearly ? 'a month, paid yearly' : 'a month'}
              </th>
              <th scope="col" className="border-rule-soft border-b py-2 font-normal">
                what it does
              </th>
            </tr>
          </thead>
          <tbody>
            {RIVALS.map((rival) => (
              <tr key={rival.name} className={cn(rival.ours && 'bg-secondary')}>
                <th
                  scope="row"
                  className="border-rule-soft border-b py-3 pr-4 font-mono text-[0.8125rem] font-normal tracking-[0.06em] uppercase"
                >
                  {rival.name}
                </th>
                {/* Like for like. Holding the table on one billing mode while
                    the cards show the other is how a fair comparison turns
                    into a rigged one by accident. */}
                <td className="border-rule-soft numeric border-b py-3 pr-4 text-[0.875rem] whitespace-nowrap">
                  {yearly ? rival.yearly : rival.monthly}
                  {rival.derived && !yearly && (
                    <span className="text-ink-faint" aria-hidden>
                      *
                    </span>
                  )}
                </td>
                <td className="border-rule-soft text-ink-soft border-b py-3 text-[0.875rem] leading-snug">
                  {rival.does}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-ink-faint mt-3 font-mono text-[0.625rem] leading-relaxed">
          {RIVALS_CHECKED}
        </p>

        {/* ------------------------------------------------------ the cap, and
            the five things it will never do. Kept under the price because a
            stated limit is what makes the number above believable. */}
        <div className="mt-16 grid gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div>
            <h3 className="display max-w-[18ch] text-xl leading-tight sm:text-2xl">
              And a cap you set, not one we promise.
            </h3>
            {/* Without this the page invites an arithmetic it then loses:
                twelve shifts at four dollars against twelve euros a month.
                Whose money the meter is showing is the whole answer. */}
            <p className="text-ink-soft mt-4 max-w-[46ch] text-[0.9375rem] leading-relaxed">
              That is what the thinking costs, not what you pay. On Studio the
              model bill is ours and the cap is yours — it exists so a shift you
              walked away from cannot surprise you. On Pro the bill is yours, at
              cost, which is what the lower price buys.
            </p>

            <div className="mt-6">
              <div className="flex items-baseline gap-3">
                <span className="numeric text-[2.25rem] leading-none">$4</span>
                <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.1em] uppercase">
                  a typical shift, against the cap you set
                </span>
              </div>

              <div className="border-rule relative mt-5 h-7 border">
                <div
                  className="bg-ink absolute inset-y-0 left-0"
                  style={{ width: `${(4 / CAP) * 100}%` }}
                />
                <div
                  className="border-ink hatch absolute inset-y-0 border-r"
                  style={{
                    left: `${(4 / CAP) * 100}%`,
                    width: `${(6 / CAP) * 100}%`,
                  }}
                />
              </div>

              <div className="text-ink-faint relative mt-1.5 h-4 font-mono text-[0.625rem]">
                <span className="absolute left-0">$0</span>
                <span
                  className="absolute -translate-x-1/2 whitespace-nowrap"
                  style={{ left: `${(10 / CAP) * 100}%` }}
                >
                  $10 worst case
                </span>
                <span className="text-ink absolute right-0">${CAP} your cap</span>
              </div>
            </div>

            <ul className="mt-8 grid gap-px bg-rule-soft border-rule-soft border sm:grid-cols-3">
              {[
                ['< 2s', 'stop takes effect in'],
                ['nothing', 'a shift that filed nothing costs'],
                ['yours', 'the folder, on any plan'],
              ].map(([value, label]) => (
                <li key={label} className="bg-panel p-4">
                  <p className="numeric text-[1.25rem] leading-none">{value}</p>
                  <p className="text-ink-faint mt-1.5 font-mono text-[0.625rem] tracking-[0.08em] uppercase">
                    {label}
                  </p>
                </li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="display max-w-[18ch] text-xl leading-tight sm:text-2xl">
              And five things it will never do.
            </h3>

            {/* The list nobody else publishes. This reader has been burned by
                confident AI twice, and the only claim worth anything to them is
                one that costs us something to make. */}
            <dl className="mt-6">
              {NOTS.map(([term, why]) => (
                <div key={term} className="border-rule-soft border-t py-4">
                  <dt className="flex items-baseline gap-2.5">
                    {/* Not the assumption ring: these are the claims the
                        product is most certain about. */}
                    <span aria-hidden className="bg-rule mt-[0.55em] h-px w-2.5 shrink-0" />
                    <span className="font-mono text-[0.75rem] tracking-[0.08em] uppercase">
                      never {term}
                    </span>
                  </dt>
                  <dd className="text-ink-soft mt-1.5 pl-[1.4rem] text-[0.9375rem] leading-relaxed">
                    {why}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>
      </div>
    </section>
  )
}

function Close() {
  const canvas = useCanvases()
  return (
    <Field which="narrow" focus="40% 55%" className="border-b-0">
      <div className="panel mx-auto max-w-2xl p-8 text-center sm:p-12">
        <h2 className="display mx-auto max-w-[18ch] text-2xl leading-tight sm:text-[2.1rem]">
          Then you go and build it.
        </h2>
        <p className="text-ink-soft mx-auto mt-4 max-w-[46ch] text-[1.0625rem] leading-[1.6]">
          {HEADER.company} took {HEADER.minutes} minutes and ${HEADER.cost}. Yours
          will be about your idea, and the folder is yours to take anywhere.
        </p>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-5">
          <a
            href="#top"
            onClick={(e) => startHere() && e.preventDefault()}
            className="btn btn-primary"
          >
            start a company
          </a>
          <Link
            to="/companies"
            className="link -m-3 inline-flex min-h-11 items-center p-3 font-mono text-[0.75rem]"
          >
            look at one that already ran
          </Link>
        </div>

        {/* Every painting on the page, credited once, here. An unattributed
            background is decoration; a labelled one is a choice — but a label
            under each of them is a stutter. */}
        <p className="border-rule-soft text-ink-faint mt-10 border-t pt-4 font-mono text-[0.5625rem] leading-relaxed tracking-[0.1em] uppercase">
          {canvas.wideCaption} · {canvas.narrowCaption}
        </p>
      </div>
    </Field>
  )
}
