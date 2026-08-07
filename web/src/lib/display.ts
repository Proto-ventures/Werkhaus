/**
 * Display helpers.
 *
 * The vocabulary rule: the user has employees who work shifts. They do not have
 * agents, conversations, tokens, or models. Anything that would leak the second
 * vocabulary into the first belongs here, where it can be fixed once.
 */

import type { components } from '@/api/types.gen'

type Confidence = components['schemas']['Artifact']['confidence']
type Severity = components['schemas']['Objection']['severity']
type CompanyStatus = components['schemas']['Company']['status']
type ShiftStatus = components['schemas']['Shift']['status']

export const CONFIDENCE: Record<
  Confidence,
  { label: string; blurb: string; className: string; rule: string }
> = {
  sourced: {
    label: 'sourced',
    blurb: 'Taken from pages an employee actually opened.',
    className: 'text-sourced',
    rule: 'border-l-4 border-l-sourced border-solid',
  },
  inferred: {
    label: 'inferred',
    blurb: 'Reasoned from something sourced. Nobody checked it directly.',
    className: 'text-inferred',
    rule: 'border-l-4 border-l-inferred border-solid',
  },
  assumption: {
    label: 'made up',
    blurb: 'Made up to keep going. Treat it as a guess until someone checks.',
    // Dashed, deliberately: you can squint at the artifact list and see how
    // much of this company is actually evidenced.
    className: 'text-assumption',
    rule: 'border-l-4 border-l-assumption border-dashed',
  },
}

export const SEVERITY: Record<Severity, { label: string; className: string }> = {
  fatal: { label: 'fatal', className: 'text-fatal' },
  serious: { label: 'serious', className: 'text-serious' },
  noted: { label: 'noted', className: 'text-noted' },
}

/** Company status, said the way a person would say it. */
export const COMPANY_STATUS: Record<CompanyStatus, string> = {
  draft: 'Not started',
  idle: 'Waiting for you',
  working: 'Working',
  blocked: 'Needs you',
  halted: 'Stopped',
  archived: 'Archived',
}

export const SHIFT_STATUS: Record<ShiftStatus, string> = {
  queued: 'Queued',
  running: 'Running',
  completed: 'Finished',
  failed: 'Stopped early',
  aborted: 'You stopped it',
  budget_exceeded: 'Ran out of budget',
}

export const PHASES = [
  ['planning', 'Planning'],
  ['working', 'Working'],
  ['review', 'Review'],
  ['integrating', 'Filing'],
  ['closing', 'Writing up'],
] as const

export function money(value: string | number): string {
  const amount = typeof value === 'string' ? Number(value) : value
  return `$${amount.toFixed(2)}`
}

export function clock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

export function day(iso: string): string {
  return new Date(iso).toLocaleDateString([], {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}

/** "3 sources" / "no sources" — never "sources: 3". */
export function sourceCount(n: number): string {
  if (n === 0) return 'no sources'
  return n === 1 ? '1 source' : `${n} sources`
}
