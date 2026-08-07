import { useEffect, useReducer, useState } from 'react'
import type {
  Artifact,
  Decision,
  LedgerEntry,
  Objection,
  Shift,
} from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { CONFIDENCE, SEVERITY, SHIFT_STATUS, clock, day, money, sourceCount } from '@/lib/display'
import { cn } from '@/lib/utils'

/**
 * Dashboard building blocks, designed around a few rules that matter for
 * neurodivergent users and cost everyone else nothing:
 *
 * - Fixed order. Sections never reorder, appear, or shuffle. A thing lives
 *   where it lived yesterday.
 * - One idea per line, in literal words. "show" and "hide", not chevrons you
 *   have to decode.
 * - Progressive disclosure. Everything beyond the current state is behind a
 *   labelled toggle, and the open/closed choice is remembered.
 * - Nothing moves unless the user moved it. Opening a section is instant, not
 *   animated. The only motion anywhere is the soft breath on a working mark.
 * - Time is visible. Started when, usually takes how long.
 */

/** Open/closed choices survive reloads, so the layout is the one you left. */
export function useStored<T>(key: string, initial: T): [T, (v: T) => void] {
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = localStorage.getItem(key)
      return raw === null ? initial : (JSON.parse(raw) as T)
    } catch {
      return initial
    }
  })
  const set = (next: T) => {
    setValue(next)
    try {
      localStorage.setItem(key, JSON.stringify(next))
    } catch {
      /* storage full or blocked; the session still works */
    }
  }
  return [value, set]
}

/** Re-renders twice a minute so "started 4 min ago" stays true. */
export function useClock(): number {
  const [tick, bump] = useReducer((n: number) => n + 1, 0)
  useEffect(() => {
    const timer = setInterval(bump, 30_000)
    return () => clearInterval(timer)
  }, [])
  return tick
}

export function minutesAgo(iso: string): number {
  return Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60_000))
}

export function minutesText(iso: string): string {
  const m = minutesAgo(iso)
  if (m === 0) return 'just now'
  if (m === 1) return '1 minute ago'
  if (m < 60) return `${m} minutes ago`
  const h = Math.round(m / 60)
  return h === 1 ? 'about an hour ago' : `about ${h} hours ago`
}

/* ------------------------------------------------------------------ section */

export function Section({
  title,
  meta,
  open,
  onToggle,
  children,
  anchor,
}: {
  title: string
  meta: string
  open: boolean
  onToggle: () => void
  children: React.ReactNode
  anchor?: React.Ref<HTMLElement>
}) {
  return (
    <section ref={anchor} className="panel">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="focus-visible:ring-ring flex w-full items-baseline gap-3 px-4 py-3 text-left focus-visible:ring-2 focus-visible:outline-none"
      >
        <span className="numeric text-ink-faint w-3 text-center text-[0.9375rem]" aria-hidden>
          {open ? '−' : '+'}
        </span>
        <span className="display text-base">{title}</span>
        <span className="text-ink-faint font-mono text-[0.75rem]">{meta}</span>
        <span className="text-ink-faint ml-auto font-mono text-[0.6875rem]">
          {open ? 'hide' : 'show'}
        </span>
      </button>
      {open && <div className="border-rule-soft border-t">{children}</div>}
    </section>
  )
}

export function EmptyLine({ children }: { children: React.ReactNode }) {
  return <p className="text-ink-faint px-4 py-4 font-mono text-[0.8125rem]">{children}</p>
}

/* -------------------------------------------------------------------- rows */

export function DocRow({
  artifact,
  onOpen,
}: {
  artifact: Artifact
  onOpen: (a: Artifact) => void
}) {
  const tone = CONFIDENCE[artifact.confidence]
  return (
    <button
      type="button"
      onClick={() => onOpen(artifact)}
      className="border-rule-soft hover:bg-secondary focus-visible:ring-ring flex w-full items-baseline gap-3 border-b px-4 py-3 text-left last:border-b-0 focus-visible:ring-2 focus-visible:outline-none"
    >
      <Mark
        shape={
          artifact.confidence === 'sourced'
            ? 'circle'
            : artifact.confidence === 'inferred'
              ? 'square'
              : 'triangle'
        }
        tone={
          artifact.confidence === 'sourced'
            ? 'blue'
            : artifact.confidence === 'inferred'
              ? 'ink'
              : 'yellow'
        }
        className="self-center"
      />
      <span className="min-w-0 flex-1">
        <span className="display block truncate text-[0.9375rem]">{artifact.title}</span>
        <span className="text-ink-soft block truncate text-[0.8125rem]">
          {artifact.summary}
        </span>
      </span>
      <span className="text-ink-faint hidden shrink-0 text-right font-mono text-[0.6875rem] sm:block">
        {tone.label} · {sourceCount(artifact.sources.length)}
        <span className="block">{artifact.produced_by}</span>
      </span>
      <span className="text-link shrink-0 font-mono text-[0.75rem] underline">read</span>
    </button>
  )
}

export function ObjectionRow({ objection }: { objection: Objection }) {
  const tone = SEVERITY[objection.severity]
  return (
    <div className="border-rule-soft border-b px-4 py-3 last:border-b-0">
      <p className="flex items-center gap-2">
        <Mark
          shape="triangle"
          tone={objection.severity === 'fatal' ? 'red' : objection.severity === 'serious' ? 'yellow' : 'faint'}
        />
        <span className={cn('eyebrow', tone.className)}>{tone.label}</span>
        {objection.about_label && (
          <span className="text-ink-faint truncate font-mono text-[0.6875rem]">
            about {objection.about_label}
          </span>
        )}
      </p>
      <p className="mt-1.5 max-w-2xl text-[0.875rem] leading-relaxed">{objection.text}</p>
      {objection.settled_by && (
        <p className="text-ink-soft mt-1.5 max-w-2xl text-[0.8125rem] leading-snug">
          <span className="eyebrow text-ink-faint mr-2">settled by</span>
          {objection.settled_by}
        </p>
      )}
    </div>
  )
}

export function DecisionRow({ decision }: { decision: Decision }) {
  return (
    <div className="border-rule-soft border-b px-4 py-3 last:border-b-0">
      <p className="display text-[0.9375rem]">{decision.title}</p>
      <p className="text-ink-soft mt-1 max-w-2xl text-[0.8125rem] leading-relaxed">
        {decision.rationale}
      </p>
      {decision.alternatives_rejected.length > 0 && (
        <p className="text-ink-faint mt-1.5 max-w-2xl text-[0.8125rem]">
          <span className="eyebrow mr-2">instead of</span>
          {decision.alternatives_rejected.join(' · ')}
        </p>
      )}
      {decision.contest_note && (
        <p className="border-l-serious mt-2 max-w-2xl border-l-4 py-0.5 pl-3 text-[0.8125rem] leading-snug">
          <span className="eyebrow text-serious mr-2">vera contested this</span>
          {decision.contest_note}
        </p>
      )}
    </div>
  )
}

export function HistoryRow({ shift }: { shift: Shift }) {
  const bad = ['failed', 'aborted', 'budget_exceeded'].includes(shift.status)
  return (
    <div className="border-rule-soft border-b px-4 py-3 last:border-b-0">
      <p className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5">
        <span className="display text-[0.9375rem]">Shift {shift.number}</span>
        <span className={cn('eyebrow', bad ? 'text-red' : 'text-ink-soft')}>
          {SHIFT_STATUS[shift.status].toLowerCase()}
        </span>
        <span className="text-ink-faint ml-auto font-mono text-[0.6875rem]">
          {money(shift.cost)} · {day(shift.started_at)}
        </span>
      </p>
      {shift.failure_reason && (
        <p className="text-red mt-1 text-[0.8125rem] leading-snug">{shift.failure_reason}</p>
      )}
      {shift.summary && (
        <p className="text-ink-soft mt-1 max-w-2xl text-[0.8125rem] leading-relaxed">
          {shift.summary}
        </p>
      )}
    </div>
  )
}

export function LedgerTable({ ledger }: { ledger: LedgerEntry[] }) {
  if (ledger.length === 0) return <EmptyLine>Nothing spent yet.</EmptyLine>
  return (
    <table className="w-full border-collapse text-[0.8125rem]">
      <thead>
        <tr className="bg-secondary">
          <th className="eyebrow border-rule-soft border-b px-4 py-2 text-left">when</th>
          <th className="eyebrow border-rule-soft border-b px-4 py-2 text-left">what for</th>
          <th className="eyebrow border-rule-soft border-b px-4 py-2 text-right">amount</th>
        </tr>
      </thead>
      <tbody>
        {ledger.map((entry) => (
          <tr key={entry.id} className="border-rule-soft border-b last:border-b-0">
            <td className="numeric text-ink-faint px-4 py-2 whitespace-nowrap">
              {day(entry.at)} {clock(entry.at)}
            </td>
            <td className="px-4 py-2">{entry.note}</td>
            <td className="numeric px-4 py-2 text-right">{money(entry.amount)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
