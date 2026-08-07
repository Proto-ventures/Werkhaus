import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  api,
  type Artifact,
  type AttentionRequest,
  type Company,
  type Decision,
  type LedgerEntry,
  type Objection,
  type Shift,
  type ShiftEvent,
  type Task,
} from '@/api/client'
import { Mark } from '@/components/bauhaus'
import {
  DecisionRow,
  DocRow,
  EmptyLine,
  HistoryRow,
  LedgerTable,
  ObjectionRow,
  Section,
  minutesText,
  useClock,
  useStored,
} from '@/components/dash'
import { Page } from '@/components/shell'
import { ArtifactReader } from '@/components/work'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useCompany } from '@/hooks/useCompany'
import { PHASES, clock, money } from '@/lib/display'
import { cn } from '@/lib/utils'

/**
 * The dashboard is one page, one column, in one fixed order:
 *
 *   1. what is happening right now, in a sentence
 *   2. anything that needs you
 *   3. who is working, live
 *   4. everything else, each behind a labelled show/hide
 *
 * Nothing reorders, nothing appears in a new place, and every state is written
 * out in words. The aim is that a glance answers "is it fine?" and a click
 * answers anything deeper.
 */
export function CompanyBoard() {
  const { cid, section } = useParams<{ cid: string; section?: string }>()
  const { company, events, activity, connected, error, refresh } = useCompany(cid)
  useClock()

  // ----------------------------------------------------------------- data
  const [tasks, setTasks] = useState<Task[]>([])
  const [attention, setAttention] = useState<AttentionRequest[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [objections, setObjections] = useState<Objection[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [ledger, setLedger] = useState<LedgerEntry[]>([])

  const loadAll = useCallback(async () => {
    if (!cid) return
    const [t, at, ar, ob, de, sh, le] = await Promise.all([
      api.listTasks(cid),
      api.listAttention(cid),
      api.listArtifacts(cid),
      api.listObjections(cid),
      api.listDecisions(cid),
      api.listShifts(cid),
      api.listLedger(cid),
    ])
    setTasks(t)
    setAttention(at)
    setArtifacts(ar)
    setObjections(ob)
    setDecisions(de)
    setShifts(sh)
    setLedger(le)
  }, [cid])

  // `company` is a fresh object whenever the socket saw something that
  // matters, so it doubles as the change signal for every list.
  useEffect(() => {
    void loadAll()
  }, [loadAll, company])

  // ------------------------------------------------------------- sections
  const [open, setOpen] = useStored<Record<string, boolean>>('wh.sections', {
    docs: true,
    vera: true,
    decisions: false,
    money: false,
    history: false,
    log: false,
  })
  const toggle = (key: string) => setOpen({ ...open, [key]: !open[key] })

  // Old bookmarked routes land on the same page with that section opened.
  const anchors = {
    docs: useRef<HTMLElement>(null),
    money: useRef<HTMLElement>(null),
    history: useRef<HTMLElement>(null),
  }
  useEffect(() => {
    const target = section === 'work' ? 'docs' : section === 'shifts' ? 'history' : section
    if (target && target in anchors) {
      setOpen({ ...open, [target]: true })
      anchors[target as keyof typeof anchors].current?.scrollIntoView()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section])

  const [reading, setReading] = useState<Artifact | null>(null)
  const [body, setBody] = useState<string | null>(null)
  useEffect(() => {
    if (!reading) return
    setBody(null)
    void api.readArtifact(reading.id).then(setBody)
  }, [reading])

  const [busy, setBusy] = useState(false)

  if (error) {
    return (
      <Page>
        <p className="text-red text-sm">{error}</p>
      </Page>
    )
  }
  if (!company || !cid) {
    return (
      <Page>
        <p className="text-ink-faint font-mono text-sm">loading...</p>
      </Page>
    )
  }

  // ------------------------------------------------------------- derived
  const working = company.status === 'working'
  const pending = attention.filter((a) => a.answered_at === null)
  const running = shifts.find((s) => s.status === 'running')
  const phase = phaseOf(events)
  const openTasks = tasks.filter((t) => t.status === 'open')
  const contested = decisions.filter((d) => d.contested_by).length
  const serious = objections.filter((o) => o.severity !== 'noted').length

  const moves = [
    ...company.progress.whats_missing.map((text) => ({ text, suggested: true })),
    ...openTasks
      .filter((t) => !company.progress.whats_missing.includes(t.title))
      .map((t) => ({ text: t.title, suggested: false })),
  ].slice(0, 3)

  async function act(fn: () => Promise<unknown>, done?: string) {
    setBusy(true)
    try {
      await fn()
      if (done) toast.success(done)
      await refresh()
      await loadAll()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Page>
      <div className="mx-auto max-w-3xl space-y-4">
        {/* 1 ---------------------------------------------------- right now */}
        <header className="panel">
          <div className="px-4 py-4">
            <div className="flex flex-wrap items-center gap-3">
              <StatusMark status={company.status} />
              <h1 className="display text-xl leading-none">{company.name}</h1>
              <span className="text-ink-faint ml-auto flex items-center gap-1.5 font-mono text-[0.6875rem]">
                <Mark shape={connected ? 'circle' : 'ring'} tone={connected ? 'blue' : 'faint'} />
                {connected ? 'live' : 'reconnecting'}
              </span>
            </div>

            <StatusSentence
              company={company}
              running={running}
              phase={phase}
              pendingName={pending[0]?.role_id ?? null}
            />

            <div className="mt-4 flex flex-wrap items-center gap-2">
              {company.status === 'halted' ? (
                <button
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() => act(() => api.resume(cid))}
                >
                  start it up again
                </button>
              ) : (
                <button
                  className="btn btn-primary"
                  disabled={busy || working || company.status === 'blocked'}
                  onClick={() => act(() => api.startShift(cid), 'Shift started.')}
                >
                  {working
                    ? 'a shift is running'
                    : company.shift_count === 0
                      ? 'start the first shift'
                      : 'start a shift'}
                </button>
              )}
              <button
                className="btn btn-danger"
                disabled={busy || company.status === 'halted'}
                onClick={() =>
                  act(() => api.halt(cid), 'Stopped. Everything done so far is saved.')
                }
              >
                stop everything
              </button>
            </div>
          </div>

          {working && <PhaseSteps phase={phase} />}

          <KeyNumbers company={company} />
        </header>

        {/* 2 ---------------------------------------------------- needs you */}
        {pending.map((request) => (
          <AttentionCard
            key={request.id}
            request={request}
            name={roleName(company, request.role_id)}
            busy={busy}
            onAnswer={(answer) =>
              act(
                () => api.answerAttention(cid, request.id, answer),
                'Answered. The team continues.',
              )
            }
          />
        ))}

        {!working && company.status !== 'blocked' && moves.length > 0 && (
          <MovesCard
            moves={moves}
            busy={busy}
            onWork={(text) =>
              act(() => api.startShift(cid, text), 'Shift started on that.')
            }
            onNote={(text) =>
              act(() => api.sendNote(cid, text), 'Noted. The team reads it next shift.')
            }
          />
        )}

        {/* 3 -------------------------------------------------- working now */}
        {(working || company.status === 'blocked') && (
          <WorkingNow company={company} activity={activity} />
        )}

        {/* 4 ------------------------------------------- everything else */}
        <Section
          title="Documents"
          meta={artifacts.length === 0 ? 'none yet' : String(artifacts.length)}
          open={open.docs}
          onToggle={() => toggle('docs')}
          anchor={anchors.docs}
        >
          {artifacts.length === 0 ? (
            <EmptyLine>Nothing yet. Documents appear here during a shift.</EmptyLine>
          ) : (
            artifacts.map((artifact) => (
              <DocRow key={artifact.id} artifact={artifact} onOpen={setReading} />
            ))
          )}
        </Section>

        <Section
          title="What Vera flagged"
          meta={
            objections.length === 0
              ? 'none yet'
              : `${objections.length}${serious ? ` · ${serious} serious` : ''}`
          }
          open={open.vera}
          onToggle={() => toggle('vera')}
        >
          {objections.length === 0 ? (
            <EmptyLine>Vera reviews at the end of every shift.</EmptyLine>
          ) : (
            objections.map((objection) => (
              <ObjectionRow key={objection.id} objection={objection} />
            ))
          )}
        </Section>

        <Section
          title="Decisions"
          meta={
            decisions.length === 0
              ? 'none yet'
              : `${decisions.length}${contested ? ` · ${contested} contested` : ''}`
          }
          open={open.decisions}
          onToggle={() => toggle('decisions')}
        >
          {decisions.length === 0 ? (
            <EmptyLine>No decisions yet. Each one is logged here with its reasons.</EmptyLine>
          ) : (
            decisions.map((decision) => (
              <DecisionRow key={decision.id} decision={decision} />
            ))
          )}
        </Section>

        <Section
          title="Money"
          meta={`${money(company.budget.spent)} of ${money(company.budget.cap)}`}
          open={open.money}
          onToggle={() => toggle('money')}
          anchor={anchors.money}
        >
          <CapEditor
            cap={Number(company.budget.cap)}
            busy={busy}
            onSave={(cap) => act(() => api.setBudget(cid, cap), 'Budget updated.')}
          />
          <LedgerTable ledger={ledger} />
        </Section>

        <Section
          title="Past shifts"
          meta={shifts.length === 0 ? 'none yet' : String(shifts.length)}
          open={open.history}
          onToggle={() => toggle('history')}
          anchor={anchors.history}
        >
          {shifts.length === 0 ? (
            <EmptyLine>No shifts yet.</EmptyLine>
          ) : (
            shifts.map((shift) => <HistoryRow key={shift.id} shift={shift} />)
          )}
        </Section>

        <Section
          title="The log"
          meta={events.length === 0 ? 'quiet' : `latest: ${latestLine(events)}`}
          open={open.log}
          onToggle={() => toggle('log')}
        >
          {events.length === 0 ? (
            <EmptyLine>Nothing has happened yet.</EmptyLine>
          ) : (
            <ol className="max-h-80 overflow-y-auto">
              {events.map((event) => (
                <li
                  key={event.id}
                  className="border-rule-soft flex gap-3 border-b px-4 py-1.5 last:border-b-0"
                >
                  <time className="numeric text-ink-faint shrink-0 pt-px text-[0.6875rem]">
                    {clock(event.at)}
                  </time>
                  <span className="min-w-0 text-[0.8125rem] leading-snug break-words">
                    {event.text}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Section>
      </div>

      <Dialog open={reading !== null} onOpenChange={(next) => !next && setReading(null)}>
        <DialogContent className="border-rule max-h-[85dvh] overflow-y-auto border sm:max-w-3xl">
          {reading && (
            <>
              <DialogHeader>
                <DialogTitle className="display text-xl">{reading.title}</DialogTitle>
                <DialogDescription>{reading.summary}</DialogDescription>
              </DialogHeader>
              <ArtifactReader artifact={reading} body={body} />
            </>
          )}
        </DialogContent>
      </Dialog>
    </Page>
  )
}

/* ---------------------------------------------------------------- pieces */

function StatusMark({ status }: { status: string }) {
  if (status === 'working') return <Mark shape="circle" tone="blue" live />
  if (status === 'blocked') return <Mark shape="triangle" tone="yellow" />
  if (status === 'halted') return <Mark shape="triangle" tone="red" />
  return <Mark shape="square" tone="faint" />
}

/**
 * The whole state of the company, written out. First line says what is true;
 * second line says what happens next, so there is never a "…and now what?".
 */
function StatusSentence({
  company,
  running,
  phase,
  pendingName,
}: {
  company: { status: string; shift_count: number }
  running: Shift | undefined
  phase: string | null
  pendingName: string | null
}) {
  let main: string
  let next: string

  if (company.status === 'working' && running) {
    const index = Math.max(0, PHASES.findIndex(([key]) => key === phase))
    main =
      `Shift ${running.number} is running. ` +
      `Step ${index + 1} of 5: ${PHASES[index][1].toLowerCase()}. ` +
      `Started ${minutesText(running.started_at)}.`
    next = 'A shift usually takes about 15 minutes. You can close this tab. The work carries on.'
  } else if (company.status === 'blocked') {
    main = `Paused. ${pendingName ?? 'The team'} asked you a question.`
    next = 'Answer it below and the team continues.'
  } else if (company.status === 'halted') {
    main = 'Stopped. Everything already done is saved.'
    next = 'Press start when you want to continue where it left off.'
  } else if (company.shift_count === 0) {
    main = 'Ready when you are.'
    next = 'Nothing happens until you press start.'
  } else {
    main = 'Between shifts. Nothing is running.'
    next = 'Start a shift, or pick one of the moves below.'
  }

  return (
    <>
      <p className="mt-3 text-[0.9375rem] leading-snug">{main}</p>
      <p className="text-ink-faint mt-1 text-[0.8125rem] leading-snug">{next}</p>
    </>
  )
}

/** Steps, numbered, so the sequence is knowable in advance. */
function PhaseSteps({ phase }: { phase: string | null }) {
  const index = PHASES.findIndex(([key]) => key === phase)
  return (
    <ol className="border-rule-soft divide-rule-soft grid grid-cols-5 divide-x border-t">
      {PHASES.map(([key, label], i) => {
        const done = index > i
        const current = index === i
        return (
          <li
            key={key}
            aria-current={current ? 'step' : undefined}
            className={cn(
              'px-2 py-2 text-center sm:px-3',
              current && 'bg-ink text-paper',
              !current && done && 'text-ink-soft',
              !current && !done && 'text-ink-faint/70',
            )}
          >
            <span className="numeric block text-[0.6875rem]">
              {done ? 'done' : `step ${i + 1}`}
            </span>
            <span className="eyebrow block truncate">{label.toLowerCase()}</span>
          </li>
        )
      })}
    </ol>
  )
}

/** The three numbers, always in the same place, always in the same order. */
function KeyNumbers({ company }: { company: Company }) {
  const spent = Number(company.budget.spent)
  const cap = Number(company.budget.cap)
  const perShift = Number(company.budget.per_shift_cap)
  const shiftsLeft = perShift > 0 ? Math.max(0, Math.floor((cap - spent) / perShift)) : 0
  return (
    <div className="border-rule-soft divide-rule-soft grid grid-cols-3 divide-x border-t">
      <div className="px-4 py-2.5">
        <span className="eyebrow text-ink-faint block">how far along</span>
        <span className="numeric text-[0.9375rem]">{company.progress.percent}%</span>
        <span className="bg-rule-soft mt-1 block h-1.5 w-full">
          <span
            className="bg-blue block h-full"
            style={{ width: `${company.progress.percent}%` }}
          />
        </span>
      </div>
      <div className="px-4 py-2.5">
        <span className="eyebrow text-ink-faint block">spent</span>
        <span className="numeric text-[0.9375rem]">
          {money(spent)} <span className="text-ink-faint">of {money(cap)}</span>
        </span>
      </div>
      <div className="px-4 py-2.5">
        <span className="eyebrow text-ink-faint block">shifts left</span>
        <span className="numeric text-[0.9375rem]">{shiftsLeft}</span>
      </div>
    </div>
  )
}

/**
 * Bounded, not full-bleed: prominent by position and border, without flooding
 * the screen yellow. One question, its options as buttons, nothing else.
 */
function AttentionCard({
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
      <div className="px-4 py-4">
        <p className="flex items-center gap-2">
          <Mark shape="triangle" tone="yellow" />
          <span className="eyebrow">{name} needs an answer</span>
        </p>
        <p className="mt-2 max-w-2xl text-[0.9375rem] leading-relaxed">{request.question}</p>
        <div className="mt-3 flex flex-col items-start gap-2">
          {request.options.map((option) => (
            <button
              key={option}
              type="button"
              className="btn text-left"
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

/**
 * At most three, the judge's pick first and marked. Each is one click. Below
 * them, a place to say something in your own words instead.
 */
function MovesCard({
  moves,
  busy,
  onWork,
  onNote,
}: {
  moves: { text: string; suggested: boolean }[]
  busy: boolean
  onWork: (text: string) => void
  onNote: (text: string) => void
}) {
  const [note, setNote] = useState('')
  return (
    <div className="panel">
      <p className="border-rule-soft border-b px-4 py-3">
        <span className="display text-base">What's next</span>
        <span className="text-ink-faint ml-3 font-mono text-[0.6875rem]">
          pick one, or just start a shift
        </span>
      </p>
      <ol>
        {moves.map((move, i) => (
          <li
            key={move.text}
            className="border-rule-soft flex items-center gap-3 border-b px-4 py-3"
          >
            <span className="numeric text-ink-faint text-[0.75rem]">{i + 1}</span>
            <span className="min-w-0 flex-1 text-[0.875rem] leading-snug">
              {move.text}
              {move.suggested && i === 0 && (
                <span className="eyebrow text-blue ml-2">suggested</span>
              )}
            </span>
            <button
              type="button"
              className="btn shrink-0 py-1 text-[0.75rem]"
              disabled={busy}
              onClick={() => onWork(move.text)}
            >
              work on this
            </button>
          </li>
        ))}
      </ol>
      <form
        className="flex gap-2 px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (!note.trim()) return
          onNote(note.trim())
          setNote('')
        }}
      >
        <input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Or tell the team something, in your words"
          className="border-rule-soft placeholder:text-ink-faint focus-visible:ring-ring min-w-0 flex-1 border px-3 py-1.5 text-[0.8125rem] focus-visible:ring-2 focus-visible:outline-none"
        />
        <button type="submit" className="btn py-1 text-[0.75rem]" disabled={busy || !note.trim()}>
          leave the note
        </button>
      </form>
    </div>
  )
}

/**
 * Only the people doing something, one per line, with what they are doing in
 * plain words. The other rows exist behind one labelled toggle, so the default
 * view is a short list, not eight competing cards.
 */
function WorkingNow({
  company,
  activity,
}: {
  company: Company
  activity: Record<string, string>
}) {
  const [everyone, setEveryone] = useStored('wh.everyone', false)
  const line = (id: string, fallback: string | null | undefined) =>
    activity[id] ?? fallback ?? null
  const active = company.roster.filter(
    (r) => line(r.id, r.current_activity) || r.status === 'working' || r.status === 'blocked' || r.status === 'failed',
  )
  const resting = company.roster.length - active.length
  const rows = everyone ? company.roster : active

  return (
    <div className="panel">
      <p className="border-rule-soft flex items-baseline gap-3 border-b px-4 py-3">
        <span className="display text-base">Working now</span>
        <button
          type="button"
          className="text-link ml-auto font-mono text-[0.6875rem] underline"
          onClick={() => setEveryone(!everyone)}
        >
          {everyone ? 'show only active' : `show all ${company.roster.length}`}
        </button>
      </p>
      {rows.length === 0 ? (
        <EmptyLine>Nobody is mid-task right now.</EmptyLine>
      ) : (
        rows.map((role) => {
          const doing = line(role.id, role.current_activity)
          return (
            <p
              key={role.id}
              className="border-rule-soft flex items-baseline gap-3 border-b px-4 py-2 last:border-b-0"
            >
              <Mark
                shape={doing ? 'circle' : role.status === 'failed' ? 'triangle' : 'square'}
                tone={doing ? 'blue' : role.status === 'failed' ? 'red' : 'faint'}
                live={Boolean(doing)}
                className="self-center"
              />
              <span className="display w-16 shrink-0 text-[0.875rem]">
                {role.display_name}
              </span>
              <span className="text-ink-soft min-w-0 flex-1 truncate text-[0.8125rem]">
                {doing ??
                  (role.status === 'failed'
                    ? 'stopped on a problem; resumes next shift'
                    : 'between tasks')}
              </span>
            </p>
          )
        })
      )}
      {!everyone && resting > 0 && (
        <p className="text-ink-faint px-4 py-2 font-mono text-[0.6875rem]">
          {resting} {resting === 1 ? 'person is' : 'people are'} between tasks
        </p>
      )}
    </div>
  )
}

function CapEditor({
  cap,
  busy,
  onSave,
}: {
  cap: number
  busy: boolean
  onSave: (cap: number) => void
}) {
  const [value, setValue] = useState(cap.toFixed(2))
  useEffect(() => setValue(cap.toFixed(2)), [cap])
  return (
    <form
      className="border-rule-soft flex flex-wrap items-end gap-3 border-b px-4 py-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSave(Number(value))
      }}
    >
      <label className="block">
        <span className="eyebrow text-ink-faint block">spending cap</span>
        <input
          value={value}
          inputMode="decimal"
          onChange={(e) => setValue(e.target.value)}
          className="numeric border-rule-soft focus-visible:ring-ring mt-1 w-28 border px-3 py-1.5 text-[0.875rem] focus-visible:ring-2 focus-visible:outline-none"
        />
      </label>
      <button type="submit" className="btn py-1.5 text-[0.8125rem]" disabled={busy}>
        save the cap
      </button>
      <span className="text-ink-faint font-mono text-[0.6875rem]">
        when it is reached, everything stops and the work is kept
      </span>
    </form>
  )
}

/* ----------------------------------------------------------------- helpers */

function phaseOf(events: ShiftEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].kind === 'shift.phase') {
      const phase = events[i].payload?.phase
      return typeof phase === 'string' ? phase : null
    }
  }
  return null
}

function latestLine(events: ShiftEvent[]): string {
  const last = events[events.length - 1]
  if (!last) return 'quiet'
  return last.text.length > 44 ? `${last.text.slice(0, 44)}...` : last.text
}

function roleName(company: Company, roleId: string | null | undefined): string {
  return company.roster.find((r) => r.id === roleId)?.display_name ?? 'The team'
}
