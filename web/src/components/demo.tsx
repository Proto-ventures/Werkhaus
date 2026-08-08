import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

/**
 * Three shifts, sped up, on the front page.
 *
 * The old version showed a team writing documents, which was the product a year
 * ago. What Werkhaus does now is build a working business — a database, a page
 * at a real address, confirmation emails, a checkout — so the page shows that
 * being built instead of describing it.
 *
 * The shape of the animation is the offer: three shifts is exactly what the free
 * plan grants, and by the end of the third one there is something a stranger can
 * open and pay for. Anyone who watches it through has understood both the unit
 * of work and the price of finding out.
 *
 * It stops entirely under prefers-reduced-motion and when the tab is hidden.
 * Under reduced motion it shows the finished company as a still frame — the same
 * information, none of the movement.
 */

type Phase = 'planning' | 'working' | 'review' | 'closing'
type Grade = 'sourced' | 'inferred' | 'assumption'

type Beat =
  | { at: number; kind: 'shift'; number: number }
  | { at: number; kind: 'phase'; phase: Phase }
  | { at: number; kind: 'work'; who: string; text: string }
  | { at: number; kind: 'file'; who: string; title: string; grade: Grade }
  | { at: number; kind: 'build'; piece: string; who: string }
  | { at: number; kind: 'built'; piece: string; detail?: string }
  | { at: number; kind: 'said'; who: string; text: string }
  | { at: number; kind: 'flag'; text: string }
  | { at: number; kind: 'progress'; percent: number }

const DESKS = [
  { id: 'ada', job: 'chief of staff' },
  { id: 'maya', job: 'researcher' },
  { id: 'ines', job: 'strategist' },
  { id: 'otto', job: 'brand' },
  { id: 'nia', job: 'numbers' },
  { id: 'rafa', job: 'growth' },
  { id: 'kit', job: 'builder' },
  { id: 'vera', job: 'critic' },
]

const PHASES: Phase[] = ['planning', 'working', 'review', 'closing']

/** The product, in the order it comes into existence. This list is the whole
 *  argument: every row is a thing the founder can check themselves. */
const PIECES = [
  { id: 'page', label: 'A page people can visit' },
  { id: 'db', label: 'A database of their own' },
  { id: 'signups', label: 'Somewhere signups are stored' },
  { id: 'live', label: 'A real web address' },
  { id: 'email', label: 'Confirmation emails' },
  { id: 'pay', label: 'A checkout that takes cards' },
]

// Times are milliseconds from the start of the run, so the whole arc can be
// read at a glance and retimed without recomputing every gap. About 66 seconds.
const SCRIPT: Beat[] = [
  // ------------------------------------------------------------- shift one
  { at: 300, kind: 'shift', number: 1 },
  { at: 600, kind: 'phase', phase: 'planning' },
  { at: 1000, kind: 'work', who: 'ada', text: 'is deciding what to do first' },
  { at: 1900, kind: 'phase', phase: 'working' },
  { at: 2200, kind: 'work', who: 'maya', text: 'is reading rival booking apps' },
  { at: 3000, kind: 'work', who: 'ines', text: 'is working out who this is for' },
  { at: 3700, kind: 'work', who: 'maya', text: 'is comparing what nine of them charge' },
  { at: 4600, kind: 'file', who: 'maya', title: 'market-research.md', grade: 'sourced' },
  { at: 5100, kind: 'said', who: 'maya', text: 'Nine apps, £12 to £49. None of them do rounds.' },
  { at: 6000, kind: 'work', who: 'otto', text: 'is writing the words for the page' },
  { at: 6700, kind: 'work', who: 'nia', text: 'is building the money model' },
  { at: 7600, kind: 'file', who: 'ines', title: 'positioning.md', grade: 'inferred' },
  { at: 8400, kind: 'file', who: 'nia', title: 'unit-economics.md', grade: 'assumption' },
  { at: 9200, kind: 'phase', phase: 'review' },
  { at: 9600, kind: 'work', who: 'vera', text: 'is checking every claim has a source' },
  { at: 10600, kind: 'flag', text: '£29 is defended with rival pricing, never with a customer.' },
  { at: 11600, kind: 'phase', phase: 'closing' },
  { at: 12100, kind: 'progress', percent: 18 },

  // ------------------------------------------------------------- shift two
  { at: 13600, kind: 'shift', number: 2 },
  { at: 14000, kind: 'phase', phase: 'planning' },
  { at: 14400, kind: 'work', who: 'ada', text: 'is putting the build on the agenda' },
  { at: 15200, kind: 'phase', phase: 'working' },
  { at: 15600, kind: 'build', piece: 'db', who: 'kit' },
  { at: 15800, kind: 'work', who: 'kit', text: 'is creating your database' },
  { at: 17400, kind: 'built', piece: 'db', detail: 'yours, not ours' },
  { at: 17900, kind: 'build', piece: 'signups', who: 'kit' },
  { at: 18100, kind: 'work', who: 'kit', text: 'is making somewhere to keep signups' },
  { at: 19600, kind: 'built', piece: 'signups', detail: 'locked to each customer' },
  { at: 20200, kind: 'said', who: 'kit', text: 'Rows are locked down — nobody can read anyone else’s.' },
  { at: 21000, kind: 'build', piece: 'page', who: 'kit' },
  { at: 21300, kind: 'work', who: 'kit', text: 'is building the page' },
  { at: 22200, kind: 'work', who: 'otto', text: 'is cutting the headline down' },
  { at: 23200, kind: 'built', piece: 'page', detail: 'signup form wired up' },
  { at: 23900, kind: 'build', piece: 'live', who: 'kit' },
  { at: 24200, kind: 'work', who: 'kit', text: 'is putting it on the internet' },
  { at: 25800, kind: 'built', piece: 'live', detail: 'groomer-rounds.netlify.app' },
  { at: 26500, kind: 'said', who: 'kit', text: 'It’s live. Open it on your phone.' },
  { at: 27400, kind: 'phase', phase: 'review' },
  { at: 27800, kind: 'work', who: 'vera', text: 'is trying to break the signup form' },
  { at: 29000, kind: 'flag', text: 'The page promises a reminder the day before. Nothing sends one yet.' },
  { at: 30200, kind: 'phase', phase: 'closing' },
  { at: 30700, kind: 'progress', percent: 61 },

  // ----------------------------------------------------------- shift three
  { at: 32200, kind: 'shift', number: 3 },
  { at: 32600, kind: 'phase', phase: 'planning' },
  { at: 33000, kind: 'work', who: 'ada', text: 'is taking Vera’s objection first' },
  { at: 33900, kind: 'phase', phase: 'working' },
  { at: 34300, kind: 'build', piece: 'email', who: 'kit' },
  { at: 34600, kind: 'work', who: 'kit', text: 'is writing the confirmation email' },
  { at: 36000, kind: 'built', piece: 'email', detail: 'sends on every signup' },
  { at: 36700, kind: 'build', piece: 'pay', who: 'kit' },
  { at: 37000, kind: 'work', who: 'kit', text: 'is setting up the checkout' },
  { at: 37800, kind: 'work', who: 'nia', text: 'is checking £29 still covers the round' },
  { at: 38900, kind: 'built', piece: 'pay', detail: 'test cards working' },
  { at: 39600, kind: 'work', who: 'rafa', text: 'is finding where groomers already talk' },
  { at: 40600, kind: 'file', who: 'rafa', title: 'where-they-are.md', grade: 'sourced' },
  { at: 41600, kind: 'phase', phase: 'review' },
  { at: 42000, kind: 'work', who: 'vera', text: 'is paying with a test card' },
  { at: 43400, kind: 'flag', text: 'Nobody has bought this yet. Everything here is still a guess.' },
  { at: 44600, kind: 'phase', phase: 'closing' },
  { at: 45100, kind: 'progress', percent: 94 },
  { at: 45600, kind: 'said', who: 'ada', text: 'A working product, three shifts in. Now go and show someone.' },
  { at: 51000, kind: 'progress', percent: 94 },
]

interface State {
  shift: number
  now: string | null
  phase: Phase
  percent: number
  activity: Record<string, string>
  done: Set<string>
  files: { title: string; grade: Grade }[]
  built: Record<string, { state: 'building' | 'done'; detail?: string }>
  flags: string[]
  feed: { id: number; text: string }[]
}

const EMPTY: State = {
  shift: 1,
  now: null,
  phase: 'planning',
  percent: 0,
  activity: {},
  done: new Set(),
  files: [],
  built: {},
  flags: [],
  feed: [],
}

const FINISHED: State = {
  shift: 3,
  now: 'the third shift is over — everything above is saved',
  phase: 'closing',
  percent: 94,
  activity: {},
  done: new Set(DESKS.map((d) => d.id)),
  files: [
    { title: 'market-research.md', grade: 'sourced' },
    { title: 'positioning.md', grade: 'inferred' },
    { title: 'unit-economics.md', grade: 'assumption' },
    { title: 'where-they-are.md', grade: 'sourced' },
  ],
  built: {
    page: { state: 'done', detail: 'signup form wired up' },
    db: { state: 'done', detail: 'yours, not ours' },
    signups: { state: 'done', detail: 'locked to each customer' },
    live: { state: 'done', detail: 'groomer-rounds.netlify.app' },
    email: { state: 'done', detail: 'sends on every signup' },
    pay: { state: 'done', detail: 'test cards working' },
  },
  flags: ['Nobody has bought this yet. Everything here is still a guess.'],
  feed: [{ id: 1, text: 'ada: a working product, three shifts in.' }],
}

export function LiveShift() {
  const reduced = useReducedMotion()
  const [state, setState] = useState<State>(EMPTY)
  const step = useRef(0)
  const seq = useRef(0)

  useEffect(() => {
    if (reduced) {
      setState(FINISHED)
      return
    }

    let timer: ReturnType<typeof setTimeout>
    let alive = true

    const advance = () => {
      if (!alive) return
      if (step.current >= SCRIPT.length) {
        step.current = 0
        setState({ ...EMPTY, done: new Set(), built: {} })
        timer = setTimeout(advance, 900)
        return
      }
      const beat = SCRIPT[step.current++]
      setState((prev) => apply(prev, beat, ++seq.current))
      const next = SCRIPT[step.current]
      const wait = next ? next.at - beat.at : 1500
      timer = setTimeout(advance, Math.max(120, wait))
    }

    const onVisibility = () => {
      // Clear first, always. Two 'visible' events with no 'hidden' between
      // them would otherwise leave two chains running and the whole thing
      // would play at double speed.
      clearTimeout(timer)
      if (!document.hidden) {
        timer = setTimeout(advance, 500)
      }
    }

    timer = setTimeout(advance, 500)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      alive = false
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [reduced])

  const phaseIndex = PHASES.indexOf(state.phase)
  const live = state.built.live?.state === 'done' ? state.built.live.detail : null

  return (
    <div className="panel flex h-full flex-col">
      {/* ------------------------------------------------------------ header */}
      <div className="border-rule flex items-baseline gap-2 border-b px-3 py-2">
        <Mark shape="circle" tone="blue" live={!reduced} className="self-center" />
        <span className="display text-[0.9375rem]">Booking Tool</span>
        <span className="text-ink-faint truncate font-mono text-[0.625rem]">
          for mobile dog groomers
        </span>
        <span className="text-ink-faint ml-auto shrink-0 font-mono text-[0.625rem]">
          shift {state.shift} of 3
        </span>
      </div>

      {/* -------------------------------------------------------- phase rail */}
      <ol className="border-rule-soft flex items-center gap-1 border-b px-3 py-1.5">
        {PHASES.map((phase, i) => (
          <li key={phase} className="flex items-center gap-1">
            <span
              className={cn(
                'eyebrow text-[0.625rem]',
                i === phaseIndex ? 'text-ink' : 'text-ink-faint/60',
              )}
            >
              {phase}
            </span>
            {i < PHASES.length - 1 && (
              <span
                className={cn(
                  'h-px w-3',
                  i < phaseIndex ? 'bg-ink-faint' : 'bg-rule-soft',
                )}
              />
            )}
          </li>
        ))}
        <li className="numeric text-ink-faint ml-auto text-[0.625rem]">
          {state.percent}%
        </li>
      </ol>

      {/* The promise is that you watch the work happen. One sentence at a
          readable size does that better than eight truncated ones. */}
      <div className="border-rule-soft flex h-8 items-center border-b px-3">
        <p className="text-ink-soft truncate text-[0.75rem]">
          {state.now ?? 'waiting to start'}
        </p>
      </div>

      {/* ------------------------------------------------------------- desks */}
      <div className="bg-rule-soft grid grid-cols-4 gap-px">
        {DESKS.map((desk) => {
          const doing = state.activity[desk.id]
          const finished = state.done.has(desk.id)
          return (
            <div key={desk.id} className="bg-panel px-2 py-1.5">
              <div className="flex items-center justify-between gap-1">
                <span className="display text-[0.75rem]">{desk.id}</span>
                <Mark
                  shape={doing ? 'circle' : finished ? 'square' : 'ring'}
                  tone={doing ? 'blue' : finished ? 'ink' : 'faint'}
                  live={Boolean(doing) && !reduced}
                  className="size-1.5"
                />
              </div>
              <p className="text-ink-faint truncate font-mono text-[0.5rem]">
                {desk.job}
              </p>
            </div>
          )
        })}
      </div>

      {/* ------------------------------------------ what the business now has */}
      <div className="border-rule-soft border-t px-3 py-2">
        <p className="eyebrow text-ink-faint text-[0.625rem]">
          what your business has
        </p>
        <ul className="mt-1.5 space-y-1">
          {PIECES.map((piece) => {
            const at = state.built[piece.id]
            const building = at?.state === 'building'
            const done = at?.state === 'done'
            return (
              <li key={piece.id} className="flex items-baseline gap-2">
                <Mark
                  shape={done ? 'square' : building ? 'circle' : 'ring'}
                  tone={done ? 'blue' : building ? 'yellow' : 'faint'}
                  live={building && !reduced}
                  className="size-2 shrink-0 self-center"
                />
                <span
                  className={cn(
                    'text-[0.6875rem] leading-snug',
                    done ? 'text-ink' : 'text-ink-faint',
                  )}
                >
                  {piece.label}
                </span>
                {done && at.detail && (
                  <span className="text-ink-faint ml-auto shrink-0 truncate font-mono text-[0.5625rem]">
                    {at.detail}
                  </span>
                )}
              </li>
            )
          })}
        </ul>

        {state.files.length > 0 && (
          <p className="text-ink-faint mt-2 font-mono text-[0.5625rem]">
            {state.files.length} documents ·{' '}
            {state.files.filter((f) => f.grade === 'sourced').length} with sources ·{' '}
            {state.files.filter((f) => f.grade === 'assumption').length} marked as
            guesses
          </p>
        )}

        {/* The one line that proves it is a real thing and not a picture. */}
        {live && (
          <p className="border-rule-soft mt-2 flex items-baseline gap-2 border-t pt-2">
            <span className="eyebrow text-ink-faint text-[0.625rem]">live at</span>
            <span className="font-mono text-[0.6875rem] underline">{live}</span>
          </p>
        )}

        {state.flags.length > 0 && (
          <div className="border-rule-soft mt-2 border-t pt-2">
            <p className="eyebrow text-serious text-[0.625rem]">
              vera, objection {state.flags.length}
            </p>
            <p className="text-ink-soft mt-0.5 text-[0.6875rem] leading-snug">
              {state.flags[state.flags.length - 1]}
            </p>
          </div>
        )}
      </div>

      {/* --------------------------------------------------------------- log */}
      <div className="border-rule-soft flex min-h-[3.25rem] flex-1 flex-col justify-end overflow-hidden border-t px-3 py-1.5">
        <ul className="space-y-0.5">
          {state.feed.slice(-9).map((line) => (
            <li
              key={line.id}
              className="text-ink-soft truncate font-mono text-[0.625rem]"
            >
              {line.text}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function apply(prev: State, beat: Beat, id: number): State {
  switch (beat.kind) {
    case 'shift':
      // A new shift clears the desks but never the product: the whole point of
      // the abstraction is that work accumulates across shifts.
      return { ...prev, shift: beat.number, activity: {}, done: new Set() }
    case 'phase':
      return { ...prev, phase: beat.phase }
    case 'work':
      return {
        ...prev,
        now: `${beat.who} ${beat.text}`,
        activity: { ...prev.activity, [beat.who]: beat.text },
        feed: [...prev.feed, { id, text: `${beat.who} ${beat.text}` }],
      }
    case 'file': {
      const activity = { ...prev.activity }
      delete activity[beat.who]
      return {
        ...prev,
        activity,
        done: new Set(prev.done).add(beat.who),
        files: [...prev.files, { title: beat.title, grade: beat.grade }],
        feed: [...prev.feed, { id, text: `${beat.who} filed ${beat.title}` }],
      }
    }
    case 'build':
      return {
        ...prev,
        built: { ...prev.built, [beat.piece]: { state: 'building' } },
      }
    case 'built': {
      const piece = PIECES.find((p) => p.id === beat.piece)
      return {
        ...prev,
        built: {
          ...prev.built,
          [beat.piece]: { state: 'done', detail: beat.detail },
        },
        feed: [
          ...prev.feed,
          { id, text: `done: ${piece?.label.toLowerCase() ?? beat.piece}` },
        ],
      }
    }
    case 'said':
      return {
        ...prev,
        feed: [...prev.feed, { id, text: `${beat.who}: ${beat.text}` }],
      }
    case 'flag': {
      const activity = { ...prev.activity }
      delete activity.vera
      return {
        ...prev,
        activity,
        flags: [...prev.flags, beat.text],
        feed: [...prev.feed, { id, text: 'vera raised an objection' }],
      }
    }
    case 'progress':
      return {
        ...prev,
        percent: beat.percent,
        activity: {},
        done: new Set(DESKS.map((d) => d.id)),
      }
  }
}
