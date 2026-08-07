import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from 'motion/react'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

/**
 * A shift, running, on the front page.
 *
 * The product's promise is that you watch the work happen, so the page shows
 * that instead of describing it. This is the real dashboard's layout driven by a
 * fixed script rather than a socket: same eight desks, same activity lines, same
 * marks on the documents as they land.
 *
 * It loops. It stops entirely under prefers-reduced-motion and when the tab is
 * hidden, because an animation nobody is looking at is just a battery drain.
 */

type Beat =
  | { after: number; kind: 'phase'; phase: Phase }
  | { after: number; kind: 'work'; who: string; text: string }
  | { after: number; kind: 'file'; who: string; title: string; mark: Mark_ }
  | { after: number; kind: 'said'; who: string; text: string }
  | { after: number; kind: 'flag'; text: string }
  | { after: number; kind: 'progress'; percent: number }

type Phase = 'planning' | 'working' | 'review' | 'closing'
type Mark_ = 'sourced' | 'inferred' | 'assumption'

const DESKS = [
  { id: 'maya', job: 'researcher' },
  { id: 'ines', job: 'strategist' },
  { id: 'otto', job: 'brand' },
  { id: 'rafa', job: 'growth' },
  { id: 'nia', job: 'numbers' },
  { id: 'kit', job: 'builder' },
  { id: 'ada', job: 'chief of staff' },
  { id: 'vera', job: 'critic' },
]

const PHASES: Phase[] = ['planning', 'working', 'review', 'closing']

// Timings are in milliseconds after the previous beat. A full pass is about
// fifty seconds, which is slow enough to read and short enough to loop.
const SCRIPT: Beat[] = [
  { after: 400, kind: 'phase', phase: 'planning' },
  { after: 900, kind: 'work', who: 'ada', text: 'is picking what the team works on' },
  { after: 1400, kind: 'phase', phase: 'working' },
  { after: 500, kind: 'work', who: 'maya', text: 'is searching for UK ceramics boxes' },
  { after: 700, kind: 'work', who: 'ines', text: 'is reading the competitor table' },
  { after: 900, kind: 'work', who: 'kit', text: 'is setting up the site' },
  { after: 1200, kind: 'work', who: 'maya', text: 'is reading claycollective.uk' },
  { after: 1100, kind: 'work', who: 'kit', text: 'is building the hero section' },
  { after: 1300, kind: 'work', who: 'maya', text: 'is comparing what six boxes charge' },
  { after: 1000, kind: 'work', who: 'ines', text: 'is working out what the wedge is' },
  { after: 1400, kind: 'file', who: 'maya', title: 'market-research.md', mark: 'sourced' },
  { after: 700, kind: 'said', who: 'maya', text: 'Six boxes, £18 to £45. The ones above £30 all name the maker.' },
  { after: 1200, kind: 'work', who: 'otto', text: 'is drafting the headline' },
  { after: 900, kind: 'work', who: 'nia', text: 'is building the money model' },
  { after: 1100, kind: 'work', who: 'kit', text: 'is wiring up the waitlist form' },
  { after: 1300, kind: 'file', who: 'ines', title: 'positioning.md', mark: 'inferred' },
  { after: 900, kind: 'work', who: 'rafa', text: 'is checking where the audience actually is' },
  { after: 1100, kind: 'work', who: 'nia', text: 'is labelling which numbers are guesses' },
  { after: 1200, kind: 'file', who: 'otto', title: 'landing-copy.md', mark: 'inferred' },
  { after: 1000, kind: 'file', who: 'nia', title: 'unit-economics.md', mark: 'assumption' },
  { after: 900, kind: 'work', who: 'kit', text: 'is checking the preview loads' },
  { after: 1200, kind: 'file', who: 'kit', title: 'site/', mark: 'sourced' },
  { after: 800, kind: 'said', who: 'kit', text: "Site's live. The waitlist stores a real address." },
  { after: 1400, kind: 'phase', phase: 'review' },
  { after: 700, kind: 'work', who: 'vera', text: 'is checking which claims have a source' },
  { after: 1600, kind: 'flag', text: 'The £29 price is defended with competitor pricing, never with a customer.' },
  { after: 1500, kind: 'flag', text: 'Breakage is missing from a model for a business that mails ceramics.' },
  { after: 1400, kind: 'phase', phase: 'closing' },
  { after: 800, kind: 'progress', percent: 64 },
  { after: 4200, kind: 'progress', percent: 64 },
]

interface State {
  phase: Phase
  activity: Record<string, string>
  done: Set<string>
  files: { title: string; mark: Mark_ }[]
  feed: { id: number; text: string; kind: string }[]
  flags: string[]
  percent: number
}

const EMPTY: State = {
  phase: 'planning',
  activity: {},
  done: new Set(),
  files: [],
  feed: [],
  flags: [],
  percent: 0,
}

export function LiveShift() {
  const reduced = useReducedMotion()
  const [state, setState] = useState<State>(EMPTY)
  const step = useRef(0)
  const seq = useRef(0)

  useEffect(() => {
    // Reduced motion gets the finished shift as a still frame: same
    // information, no movement.
    if (reduced) {
      setState({
        phase: 'closing',
        activity: {},
        done: new Set(DESKS.map((d) => d.id)),
        files: [
          { title: 'market-research.md', mark: 'sourced' },
          { title: 'positioning.md', mark: 'inferred' },
          { title: 'landing-copy.md', mark: 'inferred' },
          { title: 'unit-economics.md', mark: 'assumption' },
          { title: 'site/', mark: 'sourced' },
        ],
        feed: [{ id: 1, text: 'Vera raised 3 objections.', kind: 'flag' }],
        flags: ['The £29 price is defended with competitor pricing, never with a customer.'],
        percent: 64,
      })
      return
    }

    let timer: ReturnType<typeof setTimeout>
    let alive = true

    const advance = () => {
      if (!alive) return
      if (step.current >= SCRIPT.length) {
        step.current = 0
        setState({ ...EMPTY, done: new Set(), files: [], feed: [], flags: [] })
        timer = setTimeout(advance, 1200)
        return
      }
      const beat = SCRIPT[step.current++]
      setState((prev) => apply(prev, beat, ++seq.current))
      timer = setTimeout(advance, SCRIPT[step.current]?.after ?? 1500)
    }

    const onVisibility = () => {
      // Always clear first. Two 'visible' events without a 'hidden' between
      // them would otherwise leave two chains running and the shift would play
      // at double speed.
      clearTimeout(timer)
      if (!document.hidden) timer = setTimeout(advance, 600)
    }

    timer = setTimeout(advance, 600)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      alive = false
      clearTimeout(timer)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [reduced])

  const phaseIndex = PHASES.indexOf(state.phase)

  return (
    <div className="panel flex h-full flex-col">
      <div className="border-rule flex items-center gap-2 border-b px-3 py-2">
        <Mark shape="circle" tone="blue" live={!reduced} />
        <span className="display text-[0.9375rem]">Northwind Ceramics</span>
        <span className="text-ink-faint ml-auto font-mono text-[0.625rem]">
          shift 1
        </span>
      </div>

      {/* phase rail */}
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
                className={cn('h-px w-3', i < phaseIndex ? 'bg-ink-faint' : 'bg-rule-soft')}
              />
            )}
          </li>
        ))}
        <li className="numeric text-ink-faint ml-auto text-[0.625rem]">
          {state.percent}%
        </li>
      </ol>

      {/* the desks */}
      <div className="bg-rule-soft grid grid-cols-2 gap-px sm:grid-cols-4">
        {DESKS.map((desk) => {
          const doing = state.activity[desk.id]
          const finished = state.done.has(desk.id)
          return (
            <div key={desk.id} className="bg-panel px-2.5 py-2">
              <div className="flex items-center justify-between gap-1">
                <span className="display text-[0.8125rem]">{desk.id}</span>
                <Mark
                  shape={doing ? 'circle' : finished ? 'square' : 'ring'}
                  tone={doing ? 'blue' : finished ? 'ink' : 'faint'}
                  live={Boolean(doing) && !reduced}
                  className="size-2"
                />
              </div>
              <p className="text-ink-faint mt-0.5 truncate font-mono text-[0.5625rem]">
                {desk.job}
              </p>
              <p className="text-ink-soft mt-1 line-clamp-2 min-h-[1.75rem] text-[0.6875rem] leading-tight">
                {doing ?? ''}
              </p>
            </div>
          )
        })}
      </div>

      {/* what landed */}
      <div className="border-rule-soft flex-1 border-t px-3 py-2">
        <p className="eyebrow text-ink-faint text-[0.625rem]">documents so far</p>
        <ul className="mt-1.5 space-y-1">
          {state.files.length === 0 && (
            <li className="text-ink-faint font-mono text-[0.6875rem]">none yet</li>
          )}
          {state.files.map((file) => (
            <li key={file.title} className="flex items-center gap-2">
              <Mark
                shape={
                  file.mark === 'sourced'
                    ? 'circle'
                    : file.mark === 'inferred'
                      ? 'square'
                      : 'triangle'
                }
                tone={
                  file.mark === 'sourced'
                    ? 'blue'
                    : file.mark === 'inferred'
                      ? 'ink'
                      : 'yellow'
                }
                className="size-2"
              />
              <span className="font-mono text-[0.6875rem]">{file.title}</span>
              <span className="text-ink-faint ml-auto font-mono text-[0.625rem]">
                {file.mark === 'assumption' ? 'made up' : file.mark}
              </span>
            </li>
          ))}
        </ul>

        {state.flags.length > 0 && (
          <div className="border-rule-soft mt-2.5 border-t pt-2">
            <p className="eyebrow text-serious text-[0.625rem]">
              vera, {state.flags.length} of 3
            </p>
            <p className="text-ink-soft mt-1 text-[0.6875rem] leading-snug">
              {state.flags[state.flags.length - 1]}
            </p>
          </div>
        )}
      </div>

      {/* the log */}
      <div className="border-rule-soft h-[4.5rem] overflow-hidden border-t px-3 py-1.5">
        <ul className="space-y-0.5">
          {state.feed.slice(-3).map((line) => (
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
    case 'phase':
      return { ...prev, phase: beat.phase }
    case 'work': {
      const activity = { ...prev.activity, [beat.who]: beat.text }
      return {
        ...prev,
        activity,
        feed: [...prev.feed, { id, text: `${beat.who} ${beat.text}`, kind: 'work' }],
      }
    }
    case 'file': {
      const activity = { ...prev.activity }
      delete activity[beat.who]
      const done = new Set(prev.done)
      done.add(beat.who)
      return {
        ...prev,
        activity,
        done,
        files: [...prev.files, { title: beat.title, mark: beat.mark }],
        feed: [...prev.feed, { id, text: `${beat.who} finished ${beat.title}`, kind: 'file' }],
      }
    }
    case 'said':
      return {
        ...prev,
        feed: [...prev.feed, { id, text: `${beat.who}: ${beat.text}`, kind: 'said' }],
      }
    case 'flag': {
      const activity = { ...prev.activity }
      delete activity.vera
      return {
        ...prev,
        activity,
        flags: [...prev.flags, beat.text],
        feed: [...prev.feed, { id, text: 'vera raised an objection', kind: 'flag' }],
      }
    }
    case 'progress': {
      const done = new Set(DESKS.map((d) => d.id))
      return { ...prev, percent: beat.percent, activity: {}, done }
    }
  }
}
