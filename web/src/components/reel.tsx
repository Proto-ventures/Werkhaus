import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { HEADER, MONEY, MONEY_AT, PANELS, REEL } from '@/routes/specimen'
import { amount, project } from '@/lib/finance'
import { cn } from '@/lib/utils'

/**
 * One shift, played back once.
 *
 * The page can say "fourteen minutes and four documents" in a sentence, and a
 * reader skims straight past it, because a sentence about a process is the
 * cheapest thing on the internet. So this plays the process instead: the clock
 * runs, pages get opened, documents land in the workspace with the marks they
 * earned, and the money goes up in front of you.
 *
 * It runs once when it comes into view and then stops on the finished shift,
 * which is the state worth looking at. Replay is a button, because past that
 * first pass the rule the whole product keeps is that nothing moves unless the
 * user moved it.
 *
 * Every number is read off `specimen.ts`, so the replay cannot disagree with
 * the spec sheet printed beside it.
 */

/** Fourteen minutes, compressed to something nobody has to sit through. */
const RUN_MS = 7600
const MINUTES = REEL[REEL.length - 1].at

const PHASES: { id: string; label: string }[] = [
  { id: 'planning', label: 'planning' },
  { id: 'working', label: 'working' },
  { id: 'closing', label: 'closing' },
]

/** Minutes into the shift, as a clock reads it. */
function clock(minutes: number) {
  const total = Math.round(minutes * 60)
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}

/** Spend at a moment, straight-lined between the beats either side of it. */
function spentAt(minutes: number) {
  let prev = REEL[0]
  for (const beat of REEL) {
    if (beat.at > minutes) {
      const span = beat.at - prev.at || 1
      const along = (minutes - prev.at) / span
      return prev.spent + (beat.spent - prev.spent) * along
    }
    prev = beat
  }
  return prev.spent
}

function markClass(mark: string | null) {
  if (mark === 'assumption') return 'mark mark-ring border-assumption'
  if (mark === 'sourced') return 'mark mark-square bg-sourced'
  return 'mark mark-square bg-inferred'
}

/**
 * The money model being built, while it is being built.
 *
 * The other half of "the money goes up where you can see it", and the half that
 * is about the *business* rather than about us. The meter in the bar above is
 * dollars leaving our account; this is euros the company would take, and the
 * two are never put in the same column.
 *
 * It assembles a number at a time. There is nothing to project until a price
 * and a customer count are both in, and the figure moves every time another
 * assumption lands — which is the honest shape of a model: it is not a fact
 * that arrives, it is a stack of guesses that gets deep enough to be useful.
 *
 * Bars are drawn hollow, the same way an assumption mark is drawn hollow
 * everywhere else in the product, because none of this has happened.
 */
function Model({ now }: { now: number }) {
  const landed = MONEY.assumptions.filter((a) => (MONEY_AT[a.key] ?? 99) <= now)
  const shown = project(landed, 12)
  // The scale is the finished model's, so the curve visibly fills out as the
  // numbers land instead of always touching the top of its own box.
  const full = project(MONEY.assumptions, 12)
  const last = shown.months[shown.months.length - 1]
  const costed = landed.some((a) => a.key === 'variable_cost' || a.key === 'fixed_cost')

  return (
    <div className="border-rule-soft grid border-t sm:grid-cols-[1fr_auto]">
      <div className="border-rule-soft border-b px-4 py-3 sm:border-r sm:border-b-0">
        <p className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] uppercase">
          the money model · {landed.length} of {MONEY.assumptions.length} numbers in
        </p>
        <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
          {MONEY.assumptions.map((a) => {
            const inYet = landed.includes(a)
            if (!inYet) return null
            return (
              <li key={a.key} className="flex items-baseline gap-1.5">
                <span
                  aria-hidden
                  className={cn(markClass(a.confidence), '!size-2 translate-y-[1px]')}
                />
                <span className="text-ink-soft text-[0.8125rem]">{a.key.replace('_', ' ')}</span>
                <span className="numeric text-[0.8125rem]">
                  {a.unit === 'money'
                    ? amount(a.value, MONEY.currency, a.value % 1 !== 0)
                    : a.value}
                </span>
              </li>
            )
          })}
          {landed.length === 0 && (
            <li className="text-ink-faint font-mono text-[0.75rem]">
              nia has not put a number in yet
            </li>
          )}
        </ul>
      </div>

      <div className="flex items-center gap-4 px-4 py-3 sm:min-w-[15rem]">
        {last ? (
          <>
            <svg viewBox="0 0 96 34" className="h-9 w-24 shrink-0" aria-hidden>
              {shown.months.map((m, i) => {
                const h = (m.revenue / (full.peak || 1)) * 30
                return (
                  <rect
                    key={m.month}
                    x={i * 8 + 1}
                    y={32 - h}
                    width={5}
                    height={Math.max(1, h)}
                    fill="none"
                    stroke="var(--ink)"
                    strokeWidth={1}
                  />
                )
              })}
            </svg>
            <span>
              <span className="numeric block text-[1.35rem] leading-none">
                {amount(last.revenue, MONEY.currency)}
              </span>
              <span className="text-ink-faint block font-mono text-[0.625rem] tracking-[0.08em] uppercase">
                a month by month 12, if it holds
              </span>
              {/* Only once a cost is in. Before that "after costs" would be the
                  same number as revenue, which reads as a business with no
                  costs rather than as one nobody has costed yet. */}
              {costed && (
                <span className="text-ink-soft mt-1 block font-mono text-[0.6875rem]">
                  {amount(last.profit, MONEY.currency)} of it left after costs
                </span>
              )}
            </span>
          </>
        ) : (
          <span className="text-ink-faint font-mono text-[0.75rem] leading-relaxed">
            nothing to project until a price and a customer count are both in
          </span>
        )}
      </div>
    </div>
  )
}

export function ShiftReel({ className }: { className?: string }) {
  const reduced = useReducedMotion()
  const box = useRef<HTMLDivElement>(null)
  // Progress through the shift, 0 to 1. Everything on screen is derived from
  // it, so there is one clock and nothing can drift out of step with anything
  // else.
  const [t, setT] = useState(0)
  const [playing, setPlaying] = useState(false)

  // Reduced motion gets the finished shift, immediately. That is not a
  // degraded version — it is the state the replay ends on anyway.
  useEffect(() => {
    const el = box.current
    if (!el || reduced) {
      setT(1)
      return
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setPlaying(true)
          io.disconnect()
        }
      },
      { threshold: 0.35 },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [reduced])

  useEffect(() => {
    if (!playing) return
    let raf = 0
    let start = 0
    const step = (now: number) => {
      if (!start) start = now
      const p = Math.min(1, (now - start) / RUN_MS)
      setT(p)
      if (p < 1) raf = requestAnimationFrame(step)
      else setPlaying(false)
    }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
  }, [playing])

  const now = t * MINUTES
  const done = t >= 1
  const past = REEL.filter((b) => b.at <= now)
  const head = past[past.length - 1] ?? REEL[0]
  const phase = head.phase
  const filed = past.filter((b) => b.filed)
  // The address bar shows a page only while she is on it. Leaving the last URL
  // up for the rest of the shift would say she is still reading it, which is a
  // small lie of exactly the kind this product is against.
  const open = past.filter((b) => b.read).pop()
  const reading = open && now - open.at < 1.5 ? open.read : null
  const spend = spentAt(now)

  return (
    <div ref={box} className={cn('panel', className)}>
      {/* The studio's own bar, so what is being played back is recognisably
          the thing you get rather than an illustration of it. */}
      <div className="border-rule-soft flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-3">
        <span className="flex min-w-0 items-center gap-2">
          <span className="bg-blue size-2.5 shrink-0" aria-hidden />
          <span className="truncate font-mono text-[0.75rem] tracking-[0.08em] uppercase">
            {HEADER.company}
          </span>
        </span>
        <span className="flex gap-1.5" aria-hidden>
          {PHASES.map((p) => (
            <span
              key={p.id}
              className={cn(
                'px-2 py-[3px] font-mono text-[0.625rem] tracking-[0.06em] uppercase',
                p.id === phase ? 'bg-ink text-paper' : 'text-ink-faint',
              )}
            >
              {p.label}
            </span>
          ))}
        </span>
        <span className="ml-auto flex items-baseline gap-4">
          <span className="numeric text-[1.35rem] leading-none tabular-nums">
            {clock(now)}
          </span>
          <span className="numeric text-ink-soft text-[1.35rem] leading-none tabular-nums">
            ${spend.toFixed(2)}
          </span>
        </span>
      </div>

      <div className="grid lg:grid-cols-[1.25fr_1fr]">
        {/* The workspace, filling up. This is the whole promise of a shift in
            one pane: at the start it is an empty folder, at the end it is four
            files with your name on the folder. */}
        <div className="border-rule-soft flex min-h-[13rem] lg:min-h-[19rem] flex-col border-b lg:border-r lg:border-b-0">
          <div className="border-rule-soft flex items-center gap-3 border-b px-4 py-2">
            <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] uppercase">
              workspace
            </span>
            {reading && (
              <span className="bg-secondary text-ink-soft min-w-0 truncate px-2 py-[2px] font-mono text-[0.6875rem]">
                {reading}
              </span>
            )}
            <span className="text-ink-faint ml-auto shrink-0 font-mono text-[0.6875rem]">
              {filed.length} of {PANELS.length}
            </span>
          </div>

          <div className="flex-1 px-4 py-3">
            {filed.length === 0 ? (
              <p className="text-ink-faint font-mono text-[0.75rem]">
                empty. she is still reading.
              </p>
            ) : (
              <ul>
                {filed.map((beat) => {
                  const panel = PANELS.find((p) => p.id === beat.filed)
                  if (!panel) return null
                  return (
                    <li
                      key={panel.id}
                      className="border-rule-soft grid grid-cols-[auto_1fr_auto] items-baseline gap-x-3 border-b py-2.5"
                    >
                      <span
                        aria-hidden
                        className={cn(markClass(panel.mark), 'translate-y-[1px]')}
                      />
                      <span className="min-w-0">
                        <span className="block truncate font-mono text-[0.8125rem]">
                          {panel.file}
                        </span>
                        <span className="text-ink-soft block text-[0.8125rem] leading-snug">
                          {panel.what}
                        </span>
                      </span>
                      <span className="numeric text-ink-faint text-[0.6875rem]">
                        {clock(beat.at)}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        </div>

        {/* What the studio said while it did it. Names, not roles: "Maya filed
            the market overview" is a company, "the researcher agent returned"
            is a log. */}
        <div className="flex min-h-[13rem] lg:min-h-[19rem] flex-col">
          <div className="border-rule-soft flex items-center border-b px-4 py-2">
            <span className="text-ink-faint font-mono text-[0.6875rem] tracking-[0.08em] uppercase">
              what happened
            </span>
          </div>
          <ul className="flex-1 px-4 py-3">
            {past.slice(-5).map((beat, i, shown) => (
              <li
                key={beat.at}
                className="grid grid-cols-[2.75rem_1fr] gap-x-2 py-[5px]"
              >
                <span className="numeric text-ink-faint pt-[2px] text-[0.6875rem]">
                  {clock(beat.at)}
                </span>
                <span
                  className={cn(
                    'text-[0.875rem] leading-snug',
                    i === shown.length - 1 ? 'text-ink' : 'text-ink-soft',
                  )}
                >
                  {beat.said}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <Model now={now} />

      {/* The shift on one axis: where the money went, where the documents
          landed, and how much of the fourteen minutes each phase took. */}
      <div className="border-rule-soft border-t px-4 pt-4 pb-3">
        <div className="relative h-9">
          <div className="border-rule-soft absolute inset-x-0 top-4 border-t" />
          <div
            className="bg-ink absolute top-4 left-0 h-px"
            style={{ width: `${t * 100}%` }}
          />
          {/* Only the documents that have landed. A mark drawn faint and then
              filled in would be prettier and would also mean the plate lies
              about what exists when the animation does not run. */}
          {filed.map((beat) => {
            const panel = PANELS.find((p) => p.id === beat.filed)
            if (!panel) return null
            return (
              <span
                key={beat.at}
                aria-hidden
                className={cn(markClass(panel.mark), 'absolute top-[11px] -translate-x-1/2')}
                style={{ left: `${(beat.at / MINUTES) * 100}%` }}
              />
            )
          })}
          <span
            aria-hidden
            className="bg-ink absolute top-1 h-6 w-px -translate-x-1/2"
            style={{ left: `${t * 100}%` }}
          />
          <span className="text-ink-faint absolute top-6 left-0 font-mono text-[0.625rem]">
            0:00
          </span>
          <span className="text-ink-faint absolute top-6 right-0 font-mono text-[0.625rem]">
            {clock(MINUTES)}
          </span>
        </div>

        <div className="mt-1 flex items-center justify-between gap-4">
          <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.08em] uppercase">
            one finished shift · yours will be about your idea
          </p>
          <button
            type="button"
            onClick={() => {
              setT(0)
              setPlaying(true)
            }}
            className="text-link -m-3 inline-flex min-h-11 shrink-0 items-center p-3 font-mono text-[0.6875rem] underline"
          >
            {done ? 'play it again' : 'playing'}
          </button>
        </div>
      </div>
    </div>
  )
}
