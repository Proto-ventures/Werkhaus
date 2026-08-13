import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { HEADER, OBJECTIONS, PANELS } from '@/routes/specimen'
import { cn } from '@/lib/utils'

/**
 * The studio, as a deck of its own pages.
 *
 * Five real screens, built out of the same markup and tokens as the studio
 * itself: the page everyone sees on top, then the code behind it, the
 * documents, the team, and connections and keys at the bottom. They are
 * miniatures, not diagrams — the browser chrome is the browser chrome, the
 * file list is the file list, and the copy is the same worked example the rest
 * of this page uses, from `specimen.ts`.
 *
 * The deck lives on a real 3D plane. Apart, the pages are separated along the
 * plane's normal; together, they close to a hand's width and read as one solid
 * object seen from above. It never flattens — a stack that resolves into a flat
 * rectangle stops being a stack, and the whole point is that these five things
 * are layers of one window.
 *
 * It closes when you reach it and opens again on hover. It never loops, which
 * keeps the promise `dash.tsx` makes for the whole product: nothing moves
 * unless the user moved it.
 */

/** The plane, in scene units. Everything else is measured off these. */
const PAGE_W = 420
const PAGE_H = 272

/**
 * How far apart the pages sit, open and closed. Open is set by how much of
 * each page has to stay uncovered: at this tilt a unit of depth lifts a page
 * `sin(TILT)` on screen, and anything less than about a hundred leaves four of
 * the five pages showing nothing but their left edge. Closed is never zero.
 */
const OPEN = 116
const SHUT = 15
const MID = 2

/** The deck's attitude. */
const TILT = 60
const SPIN = -38

/**
 * The scene box the deck is drawn into, before it is scaled to the column. It
 * is wider than the deck's flat projection because perspective magnifies the
 * nearest page: at this depth the top of an open deck renders about five per
 * cent large, and without the margin it is clipped on a phone.
 */
const SCENE_W = 545
const SCENE_H = 660
const MAX_SCALE = 1.3

const TABS = ['plan & files', 'website', 'code', 'connections']

/** What a company is called before anyone has described one. */
const NOBODY = 'your company'

/** A typed idea, cut to something that fits in a chat bubble at this size. */
function clip(text: string, max = 78) {
  const t = text.trim().replace(/\s+/g, ' ')
  return t.length > max ? `${t.slice(0, max - 1)}…` : t
}

/**
 * A company name out of a sentence: the first few words, which is close enough
 * to what a founder would have called it and never claims to be more.
 */
function nameFrom(idea: string) {
  const words = idea.trim().replace(/\s+/g, ' ').split(' ').slice(0, 3).join(' ')
  return words ? clip(words, 22) : NOBODY
}

/** The address the studio shows for a preview, from whatever it is called. */
function slug(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 18) || 'yourcompany'
}

/**
 * What the deck is showing. With no idea typed it plays back the worked
 * example; the moment the reader describes a business it becomes their studio,
 * empty, which is exactly what they get when they press the button. Their own
 * sentence is the first thing in the chat, because it is.
 */
type Ctx = { company: string; idea: string }

type Page = {
  label: string
  /** Which studio tab is lit while this page is on screen. */
  tab: string
  body: (props: Ctx) => React.ReactNode
}

/* ------------------------------------------------------------------ marks */

/** Provenance, small enough to sit in a miniature. Never colour alone. */
function Mk({ mark }: { mark: 'sourced' | 'inferred' | 'assumption' | null }) {
  if (mark === null) return null
  return (
    <span
      aria-hidden
      className={cn(
        'size-[5px] shrink-0',
        mark === 'sourced' && 'bg-blue',
        mark === 'inferred' && 'bg-ink',
        mark === 'assumption' && 'border-blue border',
      )}
    />
  )
}

/* ------------------------------------------------------------------ pages */

/** The studio's own empty state: a mark, a line, and what fills it. */
function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <span className="bg-rule size-[5px]" aria-hidden />
      <p className="display mt-2 text-[11px] leading-snug">{title}</p>
      <p className="text-ink-soft mt-1 max-w-[210px] text-[7px] leading-[1.6]">{body}</p>
    </div>
  )
}

/**
 * The website tab, in the state it is actually in.
 *
 * It used to render a finished customer site here. Kit is not built, so a shift
 * does not produce one, and drawing a page the system cannot make is the same
 * lie whether it is on a landing page or in a screenshot. This is the tab's own
 * empty state, copy included, straight out of `website.tsx`.
 */
function WebsitePage({ company }: Ctx) {
  return (
    <div className="flex h-full flex-col p-2">
      <div className="border-rule flex min-h-0 flex-1 flex-col border">
        <div className="border-rule-soft flex items-center gap-1.5 border-b px-1.5 py-1">
          <span className="flex gap-1" aria-hidden>
            <span className="bg-rule-soft size-[5px] rounded-full" />
            <span className="bg-rule-soft size-[5px] rounded-full" />
            <span className="bg-rule-soft size-[5px] rounded-full" />
          </span>
          <span className="bg-secondary text-ink-soft min-w-0 flex-1 truncate px-2 py-[2px] text-center font-mono text-[7px]">
            {slug(company)}.example — preview
          </span>
        </div>
        <div className="flex min-h-0 flex-1 flex-col items-center justify-center px-6 text-center">
          <span className="flex items-center gap-[3px]" aria-hidden>
            <span className="bg-blue size-[5px] rounded-full" />
            <span className="bg-yellow size-[5px]" />
            <span className="border-red size-0 border-x-[3px] border-b-[5px] border-x-transparent" />
          </span>
          <p className="display mt-2 text-[11px] leading-snug">
            Kit builds this during the first shift
          </p>
          <p className="text-ink-soft mt-1 max-w-[200px] text-[7px] leading-[1.6]">
            When it exists, this tab shows the real page, live — served from the
            files under the code tab, not a mock-up.
          </p>
        </div>
      </div>
    </div>
  )
}

/** The code tab: the file list, and the file. */
function CodePage({ idea }: Ctx) {
  if (idea)
    return (
      <Empty
        title="No files yet"
        body="When the team builds something, the actual files land here. Ordinary code you own and can take anywhere."
      />
    )
  // The files a shift actually leaves: markdown, not a website. The code tab
  // is where the ownership claim gets checked, so what it shows has to be what
  // is really in the folder.
  const files = [
    ['market-research.md', '9.4 kB'],
    ['positioning.md', '3.2 kB'],
    ['unit-economics.md', '2.8 kB'],
    ['channels.md', '4.6 kB'],
  ]
  const source = [
    '# Market research',
    '',
    'Nine rivals, read this shift. Prices are from the',
    'pricing page on the date below.',
    '',
    '| App     | Price / mo | Plans a route? |',
    '| ------- | ---------- | -------------- |',
    '| Groomly | €29        | no             |',
    '| Pawmap  | €39        | yes            |',
  ]
  return (
    <div className="flex h-full min-h-0">
      <nav className="border-rule-soft w-[112px] shrink-0 border-r py-1">
        <p className="text-ink-faint px-2 pb-1 font-mono text-[6.5px]">
          {files.length} files · all yours
        </p>
        {files.map(([path, size], i) => (
          <span
            key={path}
            className={cn(
              'flex items-baseline gap-1 px-2 py-[2px]',
              i === 0 && 'bg-ink text-paper',
            )}
          >
            <span className="min-w-0 flex-1 truncate font-mono text-[7px]">{path}</span>
            <span
              className={cn(
                'shrink-0 font-mono text-[6px]',
                i === 0 ? 'text-paper/70' : 'text-ink-faint',
              )}
            >
              {size}
            </span>
          </span>
        ))}
      </nav>
      <div className="min-h-0 flex-1">
        <p className="border-rule-soft bg-panel border-b px-2 py-1 font-mono text-[6.5px]">
          workspace/market-research.md
        </p>
        <ol className="py-1">
          {source.map((line, i) => (
            <li key={i} className="flex px-1 leading-[1.45]">
              <span
                aria-hidden
                className="text-ink-faint w-4 shrink-0 pr-1.5 text-right font-mono text-[6px]"
              >
                {i + 1}
              </span>
              <code className="font-mono text-[7px] whitespace-pre">{line}</code>
            </li>
          ))}
        </ol>
      </div>
    </div>
  )
}

/** The plan & files tab: the nav, and the documents with their marks. */
function DocumentsPage({ idea }: Ctx) {
  const sections = [
    'the plan',
    'documents',
    'what vera flagged',
    'decisions',
    'money',
    'past shifts',
    'settings & keys',
  ]
  return (
    <div className="flex h-full min-h-0">
      <nav className="border-rule-soft w-[92px] shrink-0 border-r py-1">
        {sections.map((label, i) => (
          <span
            key={label}
            className={cn(
              'flex items-baseline gap-1 px-2 py-[3px]',
              i === 1 && 'bg-ink text-paper',
            )}
          >
            <span className="display min-w-0 flex-1 truncate text-[7.5px]">{label}</span>
            <span
              className={cn(
                'font-mono text-[6px]',
                i === 1 ? 'text-paper/70' : 'text-ink-faint',
              )}
            >
              {i === 1 ? PANELS.length : ''}
            </span>
          </span>
        ))}
      </nav>
      <div className="min-h-0 flex-1">
        {idea ? (
          <Empty
            title="Nothing filed yet"
            body="The first shift fills this. Every document that lands here carries the mark it earned."
          />
        ) : (
          <div className="px-3 py-2.5">
        <p className="display text-[12px] leading-none">Documents</p>
        <p className="text-ink-faint mt-1 font-mono text-[6px] tracking-[0.1em] uppercase">
          shift {HEADER.shift} · {HEADER.minutes} minutes · ${HEADER.cost}
        </p>
        <ul className="border-rule-soft mt-2 border-t">
          {PANELS.map((panel) => (
            <li
              key={panel.id}
              className="border-rule-soft flex items-baseline gap-1.5 border-b py-[3px]"
            >
              <Mk mark={panel.mark} />
              <span className="font-mono text-[7px]">{panel.file}</span>
              <span className="text-ink-faint truncate text-[6.5px]">{panel.what}</span>
              <span className="text-ink-faint ml-auto shrink-0 font-mono text-[6px]">
                {panel.by}
              </span>
            </li>
          ))}
        </ul>

        {/* The page above covers this one's top third, so what identifies the
            screen has to keep going down the page. Vera's objections are the
            right thing to fill it with — they are the reason this screen is
            worth opening at all. */}
        <p className="text-ink-faint mt-2.5 font-mono text-[6px] tracking-[0.1em] uppercase">
          what vera flagged
        </p>
        <ul className="mt-1 space-y-1.5">
          {OBJECTIONS.slice(0, 2).map((o) => (
            <li key={o.about} className="border-red border-l pl-1.5">
              <span className="text-ink-faint font-mono text-[6px]">
                {o.severity} · against {o.about}
              </span>
              <p className="mt-[1px] text-[6.5px] leading-[1.45]">{o.text}</p>
            </li>
          ))}
        </ul>
          </div>
        )}
      </div>
    </div>
  )
}

/** The chat rail: what you asked, and what the team said back. */
function TeamPage({ idea }: Ctx) {
  return (
    <div className="flex h-full min-h-0">
      <div className="border-rule-soft min-h-0 flex-1 border-r px-3 py-2.5">
        {idea ? (
          <>
            <p className="display text-[12px] leading-none">The plan</p>
            <p className="text-ink-soft mt-2 text-[7px] leading-[1.6]">
              Ada writes it in the first minutes of the shift, out of what you
              just said.
            </p>
          </>
        ) : (
          <>
        <p className="display text-[12px] leading-none">The plan</p>
        <p className="text-ink-faint mt-2 font-mono text-[6px] tracking-[0.1em] uppercase">
          still missing
        </p>
        <ul className="mt-1 space-y-[3px]">
          {['churn', 'a real address to take signups at', 'what a groomer would pay'].map(
            (line) => (
              <li key={line} className="flex items-baseline gap-1.5">
                <span className="border-blue size-[5px] shrink-0 border" aria-hidden />
                <span className="text-ink-soft text-[7px]">{line}</span>
              </li>
            ),
          )}
        </ul>

        {/* Spend against cap, which the studio keeps in front of you at all
            times. It is what makes a running company safe to walk away from. */}
        <p className="text-ink-faint mt-3 font-mono text-[6px] tracking-[0.1em] uppercase">
          this shift
        </p>
        <div className="border-rule-soft mt-1 h-[6px] border">
          <div className="bg-blue h-full" style={{ width: '46%' }} />
        </div>
        <p className="text-ink-soft mt-1 font-mono text-[6.5px]">
          ${HEADER.cost} of $20.00 · {HEADER.minutes} minutes
        </p>
          </>
        )}
      </div>
      <div className="flex w-[150px] shrink-0 flex-col">
        <div className="min-h-0 flex-1 space-y-2 px-2 py-2">
          {!idea && (
            <div>
              <p className="text-ink-faint flex items-center gap-1 font-mono text-[6px] tracking-[0.1em] uppercase">
                <span className="bg-ink-faint size-[4px]" aria-hidden />
                maya
              </p>
              <p className="mt-[3px] pl-[9px] text-[7px] leading-[1.5]">
                Nine rival apps, €12 to €49. Only two plan a route, and both
                charge over €35.
              </p>
            </div>
          )}
          {/* Their own words, where their own words will be. Nothing is put in
              anyone else's mouth: the team says nothing until the shift runs. */}
          <div className="flex justify-end">
            <p className="bg-secondary border-rule-soft max-w-[88%] border px-1.5 py-1 text-[7px] leading-[1.5]">
              {idea ? clip(idea) : 'Price it under thirty.'}
            </p>
          </div>
          {!idea && (
            <div>
              <p className="text-ink-faint flex items-center gap-1 font-mono text-[6px] tracking-[0.1em] uppercase">
                <span className="bg-ink-faint size-[4px]" aria-hidden />
                vera
              </p>
              <p className="mt-[3px] pl-[9px] text-[7px] leading-[1.5]">
                Then contribution only works if support stays under fifteen
                minutes.
              </p>
            </div>
          )}
        </div>
        <div className="border-rule-soft flex items-end gap-1 border-t p-1">
          <span className="text-ink-faint flex-1 px-1 py-1 text-[7px]">
            Ask them something
          </span>
          <span className="bg-ink text-paper flex size-4 items-center justify-center font-mono text-[7px]">
            ↑
          </span>
        </div>
      </div>
    </div>
  )
}

/** The connections tab: the accounts the business runs on. */
function ConnectionsPage({ idea }: Ctx) {
  const cards = [
    ['Supabase', 'the database', !idea],
    ['Netlify', 'where it lives', !idea],
    ['Resend', 'the emails', false],
    ['Stripe', 'taking money', false],
  ] as const
  return (
    <div className="h-full px-3 py-2.5">
      <p className="display text-[12px] leading-none">What it&rsquo;s connected to</p>
      <p className="text-ink-faint mt-1.5 font-mono text-[6px] tracking-[0.1em] uppercase">
        what it runs on
      </p>
      <div className="bg-rule border-rule mt-1 grid grid-cols-2 gap-px border">
        {cards.map(([name, what, done]) => (
          <div key={name} className="bg-panel flex flex-col p-1.5">
            <span className="flex items-baseline gap-1">
              <span
                aria-hidden
                className={cn('size-[5px] shrink-0', done ? 'bg-blue' : 'border-rule border')}
              />
              <span className="display text-[8px]">{name}</span>
              <span className="text-ink-faint ml-auto font-mono text-[6px]">
                {done ? 'connected' : 'not yet'}
              </span>
            </span>
            <span className="text-ink-soft mt-1 text-[6.5px] leading-snug">{what}</span>
            <span
              className={cn(
                'mt-1.5 w-fit px-1.5 py-[2px] font-mono text-[6px]',
                done ? 'border-rule border' : 'bg-ink text-paper',
              )}
            >
              {done ? 'change key' : 'connect'}
            </span>
          </div>
        ))}
      </div>
      <p className="text-ink-faint mt-2 font-mono text-[6px] tracking-[0.1em] uppercase">
        other keys
      </p>
      <div className="border-rule-soft mt-1 flex items-center gap-1.5 border px-1.5 py-1">
        <span className="font-mono text-[6.5px]">OPENAI_API_KEY</span>
        <span className="text-ink-faint font-mono text-[6.5px]">••••••••</span>
      </div>
    </div>
  )
}

const PAGES: Page[] = [
  { label: 'the page everyone sees', tab: 'website', body: WebsitePage },
  { label: 'the code behind it', tab: 'code', body: CodePage },
  { label: 'the documents, and their marks', tab: 'plan & files', body: DocumentsPage },
  { label: 'the team, and what you asked', tab: 'plan & files', body: TeamPage },
  { label: 'connections and keys', tab: 'connections', body: ConnectionsPage },
]

/** Every page wears the studio's own bar, so the closed deck reads as one app. */
function StudioPage({ page, ctx }: { page: Page; ctx: Ctx }) {
  const Body = page.body
  return (
    <div className="bg-panel border-rule flex h-full flex-col overflow-hidden border">
      <div className="border-rule-soft flex h-[26px] shrink-0 items-center gap-1.5 border-b px-2">
        <span className="bg-blue size-[7px] shrink-0" aria-hidden />
        <span className="min-w-0 truncate font-mono text-[7px] tracking-[0.1em] uppercase">
          {ctx.company}
        </span>
        <span className="ml-auto flex gap-[3px]">
          {TABS.map((tab) => (
            <span
              key={tab}
              className={cn(
                'px-1.5 py-[2px] font-mono text-[6.5px]',
                tab === page.tab ? 'bg-ink text-paper' : 'text-ink-faint',
              )}
            >
              {tab}
            </span>
          ))}
        </span>
      </div>
      <div className="min-h-0 flex-1">
        <Body {...ctx} />
      </div>
    </div>
  )
}

/* ----------------------------------------------------------------- deck */

/** Whether the pointer can hover, so the one line of instruction is true. */
function useHover() {
  const [can, setCan] = useState(true)
  useEffect(() => {
    const q = window.matchMedia('(hover: hover)')
    const sync = () => setCan(q.matches)
    sync()
    q.addEventListener('change', sync)
    return () => q.removeEventListener('change', sync)
  }, [])
  return can
}

export function ShiftDiagram({
  className,
  idea = '',
}: {
  className?: string
  /** What the reader typed in the box, if anything. Their studio, not ours. */
  idea?: string
}) {
  const reduced = useReducedMotion()
  const canHover = useHover()
  const wrap = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  const [shut, setShut] = useState(false)
  const [open, setOpen] = useState(false)

  // The deck is drawn at a fixed size and scaled to whatever column it lands
  // in, so the miniatures keep their real proportions at every width.
  useLayoutEffect(() => {
    const el = wrap.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => {
      const w = entry.contentRect.width
      // Wider than the column it sits in: the deck runs out past the text,
      // under the canvas and off the edge. The hero clips the overflow rather
      // than scrolling it. On a phone there is no margin to spend, so it stops
      // at the column.
      const bleed = window.innerWidth < 640 ? 1.0 : 1.4
      setScale(Math.min(MAX_SCALE, (w * bleed) / SCENE_W))
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    const el = wrap.current
    if (!el || reduced) {
      setShut(true)
      return
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShut(true)
          io.disconnect()
        }
      },
      { threshold: 0.25 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [reduced])

  const apart = !shut || open
  // With nothing typed the deck plays the worked example; with something typed
  // it is the reader's own studio, waiting.
  const ctx: Ctx = {
    company: idea ? nameFrom(idea) : HEADER.company.toLowerCase(),
    idea: idea.trim(),
  }
  const gap = apart ? OPEN : SHUT

  return (
    <div className={className}>
      <div
        ref={wrap}
        role="img"
        tabIndex={0}
        aria-label={`The studio as a deck of five pages: ${PAGES.map((p) => p.label).join(', ')}. Closed, they are one window.`}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        // The caption says "tap to take it apart" and only mouse and focus
        // were bound, so a phone could open the deck and then had no way to
        // close it again.
        onClick={() => setOpen((o) => !o)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="focus-visible:ring-ring relative w-full focus-visible:ring-2 focus-visible:outline-none"
        style={{ height: SCENE_H * scale }}
      >
        <div
          aria-hidden
          // Left-aligned, so the slack the scale leaves goes to the right,
          // where the hero's canvas comes in over the column.
          // print:hidden because a tilted 3D deck of miniatures is decoration
          // on paper, and the print stylesheet no longer removes everything
          // marked aria-hidden — that rule was also deleting the marks.
          className="absolute top-0 left-0 origin-top-left print:hidden"
          style={{
            width: SCENE_W,
            height: SCENE_H,
            transform: `scale(${scale})`,
            perspective: '2400px',
          }}
        >
          <div
            className="absolute inset-0"
            style={{
              transformStyle: 'preserve-3d',
              transform: `rotateX(${TILT}deg) rotateZ(${SPIN}deg)`,
            }}
          >
            {PAGES.map((page, i) => {
              const z = (MID - i) * gap
              // Opening runs outward from the middle, closing inward to it.
              const delay = reduced ? 0 : Math.abs(i - MID) * 80
              return (
                <div
                  key={page.label}
                  className="absolute top-1/2 left-1/2"
                  style={{
                    width: PAGE_W,
                    height: PAGE_H,
                    marginLeft: -PAGE_W / 2,
                    marginTop: -PAGE_H / 2,
                    transform: `translateZ(${z}px)`,
                    transition: reduced
                      ? 'none'
                      : `transform 520ms cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`,
                    boxShadow: '0 18px 40px -24px rgb(0 0 0 / 0.35)',
                  }}
                >
                  <StudioPage page={page} ctx={ctx} />
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* No caption list. The pages are the studio's own screens and they say
          what they are; naming them underneath was the timid version, and it
          was what kept the deck small enough to fit a label column beside it.
          The names survive in the label the screen reader reads. */}
      <p className="text-ink-faint mt-2 font-mono text-[0.625rem] tracking-[0.1em] uppercase">
        {!apart
          ? `${canHover ? 'hover' : 'tap'} to take it apart`
          : idea
            ? 'your studio, before the first shift'
            : 'an example · yours will be about your idea'}
      </p>
    </div>
  )
}
