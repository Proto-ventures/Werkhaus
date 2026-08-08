/**
 * The conversation rail. Everything between you and the company happens here.
 *
 * It reads top to bottom as one thread: Ada's three questions when the company
 * is new, the written plan you approve, then the running record of each shift —
 * collapsed once it's over — with anything that needs an answer from you inline,
 * where a question belongs.
 *
 * The same rules as everywhere else: literal words, fixed order, nothing moves
 * unless you moved it or an employee actually did something.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import type {
  AttentionRequest,
  Company,
  ShiftEvent,
} from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { useStored } from '@/components/dash'
import { clock } from '@/lib/display'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------- onboarding */

interface Said {
  who: 'ada' | 'you'
  text: string
}

interface Onboarding {
  step: number
  said: Said[]
}

interface QuestionOption {
  value: string
  label: string
  blurb: string
}

interface Question {
  key: string
  ask: string
  placeholder: string
  optional: boolean
  options?: QuestionOption[]
}

/** The autonomy dial. Both extremes burn budget fast — one on unattended work,
 *  one on questions and planning. The middle is the default for a reason. */
export const AUTONOMY_OPTIONS: QuestionOption[] = [
  {
    value: 'full_auto',
    label: 'full auto',
    blurb: 'Shifts run themselves, decisions are made for you, you see results. Fastest, least yours.',
  },
  {
    value: 'semi_auto',
    label: 'semi auto',
    blurb: 'Shifts run themselves; small calls are made for you, big ones ask first.',
  },
  {
    value: 'balanced',
    label: 'balanced',
    blurb: 'You start shifts. Small calls are made for you; big ones ask. The default.',
  },
  {
    value: 'limited',
    label: 'more control',
    blurb: 'You start shifts, and the team checks in on small and big decisions.',
  },
  {
    value: 'full_control',
    label: 'full control',
    blurb: 'Nothing happens unasked. Every direction is a question first. Slowest, most yours.',
  },
]

const QUESTIONS: Question[] = [
  {
    key: 'autonomy',
    ask: 'First: how much should the team do on its own? You can change this later in settings.',
    placeholder: '',
    optional: false,
    options: AUTONOMY_OPTIONS,
  },
  {
    key: 'audience',
    ask: 'Who is this for? The more specific you are, the better the research gets.',
    placeholder: 'People in small UK flats who buy few objects but care what they are',
    optional: false,
  },
  {
    key: 'success_looks_like',
    ask: 'What would make this a success in your eyes? Pick something you could actually check.',
    placeholder: 'A live page with at least 3 real signups and a price I can defend',
    optional: false,
  },
  {
    key: 'constraints',
    ask: 'Last one — anything the team must not do? You can skip this.',
    placeholder: 'UK only for the first year. No paid advertising.',
    optional: true,
  },
]

const PLAN_ITEMS = [
  'Research the market and the competition, with sources for every claim',
  'Settle the positioning and a price, with the reasoning written down',
  'Write the brand voice and the words for the page',
  'Sketch the numbers: what it costs, what it can earn',
  'Build a landing page with a working waitlist',
  'Vera reviews all of it and flags anything weak',
]

/* -------------------------------------------------------------- the rail */

export function Rail({
  company,
  events,
  attention,
  busy,
  onAnswer,
  onNote,
  onCharter,
  onStart,
}: {
  company: Company
  events: ShiftEvent[]
  attention: AttentionRequest[]
  busy: boolean
  onAnswer: (requestId: string, answer: string) => void
  onNote: (text: string) => void
  onCharter: (patch: Record<string, unknown>) => Promise<void>
  onStart: () => void
}) {
  const [onb, setOnb] = useStored<Onboarding>(`wh.onb.${company.id}`, {
    step: 0,
    said: [],
  })

  // A company that has already worked doesn't get re-interviewed.
  const interviewing = company.shift_count === 0 && onb.step < QUESTIONS.length
  useEffect(() => {
    if (company.shift_count > 0 && onb.step < QUESTIONS.length) {
      setOnb({ ...onb, step: QUESTIONS.length })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [company.shift_count])

  const planReady =
    !interviewing &&
    company.shift_count === 0 &&
    (company.status === 'idle' || company.status === 'draft')

  const pending = attention.filter((a) => a.answered_at === null)
  const groups = useMemo(() => groupFeed(events), [events])

  // Stay pinned to the newest turn, but only if the reader was already there.
  const scroller = useRef<HTMLDivElement>(null)
  const pinned = useRef(true)
  useEffect(() => {
    const el = scroller.current
    if (el && pinned.current) el.scrollTop = el.scrollHeight
  }, [events.length, onb.said.length, pending.length, planReady])

  async function submit(text: string) {
    if (interviewing) {
      const question = QUESTIONS[onb.step]
      const patch =
        question.key === 'constraints'
          ? { constraints: text.split('\n').map((l) => l.trim()).filter(Boolean) }
          : { [question.key]: text }
      try {
        await onCharter(patch)
      } catch (e) {
        toast.error((e as Error).message)
        return
      }
      advance({ who: 'you', text })
    } else {
      onNote(text)
    }
  }

  function skip() {
    advance({ who: 'you', text: 'Skip that one.' })
  }

  async function pick(option: QuestionOption) {
    const question = QUESTIONS[onb.step]
    try {
      await onCharter({ [question.key]: option.value })
    } catch (e) {
      toast.error((e as Error).message)
      return
    }
    advance({ who: 'you', text: option.label })
  }

  function advance(answer: Said) {
    const next = onb.step + 1
    const said: Said[] = [...onb.said, answer]
    if (next >= QUESTIONS.length) {
      said.push({
        who: 'ada',
        text: 'Good. I wrote that into the plan below. Nothing starts until you approve it.',
      })
    }
    setOnb({ step: next, said })
  }

  function approve() {
    setOnb({ ...onb, said: [...onb.said, { who: 'you', text: 'Plan approved.' }] })
    onStart()
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget
          pinned.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
        }}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4"
      >
        <AdaTurn first>
          You want to build: &ldquo;{company.charter.idea}&rdquo;.
          {company.shift_count === 0
            ? ' Before the team starts, I have three questions.'
            : ''}
        </AdaTurn>

        {onb.said.map((turn, i) =>
          turn.who === 'you' ? (
            <YouTurn key={i}>{turn.text}</YouTurn>
          ) : (
            <AdaTurn key={i}>{turn.text}</AdaTurn>
          ),
        )}

        {interviewing && (
          <AdaTurn>
            {QUESTIONS[onb.step].ask}
            {QUESTIONS[onb.step].options && (
              <span className="mt-2.5 flex flex-col items-start gap-1.5">
                {QUESTIONS[onb.step].options!.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    disabled={busy}
                    onClick={() => pick(option)}
                    className="btn block py-1.5 text-left text-[0.8125rem]"
                  >
                    <span className="display block">{option.label}</span>
                    <span className="text-ink-soft block text-[0.75rem] leading-snug font-normal normal-case">
                      {option.blurb}
                    </span>
                  </button>
                ))}
              </span>
            )}
            {QUESTIONS[onb.step].optional && (
              <button
                type="button"
                onClick={skip}
                className="text-link mt-2 block font-mono text-[0.75rem] underline"
              >
                skip this
              </button>
            )}
          </AdaTurn>
        )}

        {planReady && <PlanCard company={company} busy={busy} onApprove={approve} />}

        {groups.map((group) =>
          group.t === 'you' ? (
            <YouTurn key={group.id}>{group.text}</YouTurn>
          ) : group.t === 'said' ? (
            <AdaTurn key={group.id} name={group.name}>
              {group.text}
            </AdaTurn>
          ) : (
            <ShiftGroupCard key={group.id} group={group} />
          ),
        )}

        {pending.map((request) => (
          <QuestionCard
            key={request.id}
            request={request}
            name={roleName(company, request.role_id)}
            busy={busy}
            onAnswer={(answer) => onAnswer(request.id, answer)}
          />
        ))}
      </div>

      <Composer
        busy={busy}
        disabled={interviewing && Boolean(QUESTIONS[onb.step].options)}
        placeholder={
          interviewing
            ? QUESTIONS[onb.step].options
              ? 'pick one above'
              : QUESTIONS[onb.step].placeholder
            : 'Tell the team something, in your words'
        }
        hint={
          interviewing
            ? `question ${onb.step + 1} of ${QUESTIONS.length}`
            : 'the team reads it at the start of the next shift'
        }
        onSubmit={submit}
      />
    </div>
  )
}

/* ----------------------------------------------------------------- turns */

function AdaTurn({
  children,
  name = 'ada, chief of staff',
  first = false,
}: {
  children: React.ReactNode
  name?: string
  first?: boolean
}) {
  return (
    <div className={cn(first && 'pt-1')}>
      <p className="eyebrow text-ink-faint flex items-center gap-1.5">
        <Mark shape="square" tone="faint" />
        {name}
      </p>
      <p className="mt-1 pl-4 text-[0.875rem] leading-relaxed">{children}</p>
    </div>
  )
}

function YouTurn({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      <p className="bg-secondary border-rule-soft max-w-[85%] border px-3 py-2 text-[0.875rem] leading-relaxed">
        {children}
      </p>
    </div>
  )
}

function PlanCard({
  company,
  busy,
  onApprove,
}: {
  company: Company
  busy: boolean
  onApprove: () => void
}) {
  return (
    <div className="panel">
      <p className="border-rule-soft border-b px-4 py-3">
        <span className="display text-base">The plan for shift 1</span>
      </p>
      <ol className="px-4 py-3">
        {PLAN_ITEMS.map((item, i) => (
          <li key={item} className="flex gap-3 py-1 text-[0.8125rem] leading-snug">
            <span className="numeric text-ink-faint shrink-0">{i + 1}</span>
            <span>{item}</span>
          </li>
        ))}
      </ol>
      <div className="border-rule-soft border-t px-4 py-3">
        <p className="text-ink-faint mb-2.5 font-mono text-[0.6875rem]">
          about {perShift(company)} of the budget · roughly 15 minutes · nothing
          goes public without you
        </p>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          onClick={onApprove}
        >
          approve the plan and start
        </button>
      </div>
    </div>
  )
}

function perShift(company: Company): string {
  return `$${Number(company.budget.per_shift_cap).toFixed(0)}`
}

function QuestionCard({
  request,
  name,
  busy,
  onAnswer,
}: {
  request: AttentionRequest
  name: string
  busy: boolean
  onAnswer: (answer: string) => void
}) {
  return (
    <div className="panel border-l-yellow border-l-4">
      <div className="px-4 py-3">
        <p className="flex items-center gap-2">
          <Mark shape="triangle" tone="yellow" />
          <span className="eyebrow">{name} needs an answer</span>
        </p>
        <p className="mt-2 text-[0.875rem] leading-relaxed">{request.question}</p>
        <div className="mt-3 flex flex-col items-start gap-1.5">
          {request.options.map((option) => (
            <button
              key={option}
              type="button"
              className="btn py-1 text-left text-[0.8125rem]"
              disabled={busy}
              onClick={() => onAnswer(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------- the feed */

type FeedItem =
  | { t: 'you'; id: string; text: string }
  | { t: 'said'; id: string; name: string; text: string }
  | { t: 'group'; id: string; number: number; lines: ShiftEvent[]; done: boolean; closing: string | null }

/**
 * Fold the raw feed into conversation shape: your notes and answers as your
 * turns, an employee reporting back as theirs, and the churn of a shift as one
 * collapsible block per shift instead of hundreds of loose lines.
 */
function groupFeed(events: ShiftEvent[]): FeedItem[] {
  const items: FeedItem[] = []
  let group: Extract<FeedItem, { t: 'group' }> | null = null

  for (const event of events) {
    if (event.kind === 'role.said' && event.text.startsWith('You ')) {
      // "You told the team: …" / "You answered Maya: …" — strip the preamble,
      // it's a bubble on your side, the framing is visual.
      const said = event.text.replace(/^You (told the team|answered [^:]+): /, '')
      items.push({ t: 'you', id: String(event.seq), text: said })
      continue
    }
    if (event.kind === 'role.said') {
      const [name, ...rest] = event.text.split(': ')
      items.push({
        t: 'said',
        id: String(event.seq),
        name: rest.length ? name.toLowerCase() : 'the team',
        text: rest.length ? rest.join(': ') : event.text,
      })
      continue
    }
    if (event.kind === 'shift.started') {
      group = {
        t: 'group',
        id: String(event.seq),
        number: shiftNumber(event),
        lines: [],
        done: false,
        closing: null,
      }
      items.push(group)
      continue
    }
    if (event.kind === 'shift.completed' || event.kind === 'shift.failed') {
      if (group) {
        group.done = true
        group.closing = event.text
        group = null
      } else {
        items.push({ t: 'said', id: String(event.seq), name: 'ada, chief of staff', text: event.text })
      }
      continue
    }
    if (event.kind === 'attention.needed') continue // rendered as a question card
    if (group) {
      group.lines.push(event)
    }
  }
  return items
}

function shiftNumber(event: ShiftEvent): number {
  const match = /Shift (\d+)/.exec(event.text)
  if (match) return Number(match[1])
  const tail = event.shift_id?.split('/').pop()
  return tail ? Number(tail) : 1
}

function ShiftGroupCard({ group }: { group: Extract<FeedItem, { t: 'group' }> }) {
  const [open, setOpen] = useState(false)
  const shown = open ? group.lines : group.done ? [] : group.lines.slice(-3)

  return (
    <div className="panel">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="focus-visible:ring-ring flex w-full items-baseline gap-2 px-3 py-2 text-left focus-visible:ring-2 focus-visible:outline-none"
      >
        <Mark
          shape={group.done ? 'square' : 'circle'}
          tone={group.done ? 'faint' : 'blue'}
          live={!group.done}
          className="self-center"
        />
        <span className="display text-[0.875rem]">shift {group.number}</span>
        <span className="text-ink-faint font-mono text-[0.6875rem]">
          {group.done ? 'finished' : 'running'} · {group.lines.length}{' '}
          {group.lines.length === 1 ? 'step' : 'steps'}
        </span>
        <span className="text-ink-faint ml-auto font-mono text-[0.6875rem]">
          {open ? 'hide' : 'show'}
        </span>
      </button>
      {shown.length > 0 && (
        <ol className="border-rule-soft max-h-72 overflow-y-auto border-t">
          {shown.map((event) => (
            <li
              key={event.seq}
              className="flex gap-2.5 px-3 py-1 text-[0.75rem] leading-snug"
            >
              <time className="numeric text-ink-faint shrink-0 pt-px text-[0.625rem]">
                {clock(event.at)}
              </time>
              <span className="text-ink-soft min-w-0 break-words">{event.text}</span>
            </li>
          ))}
        </ol>
      )}
      {group.closing && (
        <p className="border-rule-soft border-t px-3 py-2 text-[0.8125rem] leading-relaxed">
          {group.closing}
        </p>
      )}
    </div>
  )
}

/* -------------------------------------------------------------- composer */

function Composer({
  busy,
  disabled = false,
  placeholder,
  hint,
  onSubmit,
}: {
  busy: boolean
  disabled?: boolean
  placeholder: string
  hint: string
  onSubmit: (text: string) => void
}) {
  const [text, setText] = useState('')

  function send() {
    const trimmed = text.trim()
    if (!trimmed) return
    onSubmit(trimmed)
    setText('')
  }

  return (
    <form
      className="border-rule bg-panel border-t px-3 py-3"
      onSubmit={(e) => {
        e.preventDefault()
        send()
      }}
    >
      <div className="border-rule focus-within:ring-ring flex items-end gap-2 border bg-paper focus-within:ring-2">
        <textarea
          rows={2}
          value={text}
          disabled={disabled}
          placeholder={placeholder}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              send()
            }
          }}
          className="placeholder:text-ink-faint min-w-0 flex-1 resize-none bg-transparent px-3 py-2 text-[0.875rem] leading-snug focus:outline-none"
        />
        <button
          type="submit"
          aria-label="send"
          disabled={busy || !text.trim()}
          className="bg-ink text-paper hover:bg-blue disabled:bg-rule-soft m-1.5 flex size-8 shrink-0 items-center justify-center"
        >
          <span className="mark mark-square bg-current size-2.5" aria-hidden />
        </button>
      </div>
      <p className="text-ink-faint mt-1.5 font-mono text-[0.625rem]">{hint}</p>
    </form>
  )
}

function roleName(company: Company, roleId: string | null | undefined): string {
  return company.roster.find((r) => r.id === roleId)?.display_name ?? 'The team'
}
