/**
 * The "plan & files" tab: everything the company knows and owns, behind one
 * fixed vertical list. The plan first, because "what are we doing" is the
 * question a founder brings; keys and switches last, because settings are where
 * you go on purpose, not where you live.
 */

import { useEffect, useState } from 'react'
import type {
  Artifact,
  Company,
  Decision,
  LedgerEntry,
  Objection,
  Shift,
  VaultItem,
} from '@/api/client'
import { api } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import {
  DecisionRow,
  DocRow,
  EmptyLine,
  HistoryRow,
  LedgerTable,
  ObjectionRow,
} from '@/components/dash'
import { AUTONOMY_OPTIONS } from '@/components/studio/rail'
import { ArtifactReader } from '@/components/work'
import { money } from '@/lib/display'
import { cn } from '@/lib/utils'

export type PlanSection =
  | 'plan'
  | 'documents'
  | 'vera'
  | 'decisions'
  | 'money'
  | 'history'
  | 'settings'

const SECTIONS: { key: PlanSection; label: string }[] = [
  { key: 'plan', label: 'the plan' },
  { key: 'documents', label: 'documents' },
  { key: 'vera', label: 'what vera flagged' },
  { key: 'decisions', label: 'decisions' },
  { key: 'money', label: 'money' },
  { key: 'history', label: 'past shifts' },
  { key: 'settings', label: 'settings & keys' },
]

export function PlanWork({
  company,
  artifacts,
  objections,
  decisions,
  shifts,
  ledger,
  busy,
  section,
  onSection,
  onSetBudget,
  onHalt,
  onShare,
  onUnshare,
  onAutonomy,
}: {
  company: Company
  artifacts: Artifact[]
  objections: Objection[]
  decisions: Decision[]
  shifts: Shift[]
  ledger: LedgerEntry[]
  busy: boolean
  section: PlanSection
  onSection: (s: PlanSection) => void
  onSetBudget: (cap: number) => void
  onHalt: () => void
  onShare: () => void
  onUnshare: () => void
  onAutonomy: (value: string) => void
}) {
  const [reading, setReading] = useState<Artifact | null>(null)
  const [body, setBody] = useState<string | null>(null)
  useEffect(() => {
    if (!reading) return
    setBody(null)
    void api.readArtifact(reading.id).then(setBody)
  }, [reading])

  const serious = objections.filter((o) => o.severity !== 'noted').length
  const counts: Record<PlanSection, string> = {
    plan: `${company.progress.percent}%`,
    documents: String(artifacts.length),
    vera: serious ? `${objections.length} · ${serious} serious` : String(objections.length),
    decisions: String(decisions.length),
    money: money(company.budget.spent),
    history: String(shifts.length),
    settings: '',
  }

  return (
    <div className="flex min-h-0 flex-1">
      <nav className="border-rule-soft w-44 shrink-0 overflow-y-auto border-r py-2">
        {SECTIONS.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            aria-current={section === key ? 'page' : undefined}
            onClick={() => {
              onSection(key)
              setReading(null)
            }}
            className={cn(
              'focus-visible:ring-ring flex w-full items-baseline gap-2 px-4 py-2 text-left focus-visible:ring-2 focus-visible:outline-none',
              section === key ? 'bg-ink text-paper' : 'hover:bg-secondary',
            )}
          >
            <span className="display min-w-0 flex-1 truncate text-[0.8125rem]">
              {label}
            </span>
            <span
              className={cn(
                'font-mono text-[0.625rem]',
                section === key ? 'text-paper/70' : 'text-ink-faint',
              )}
            >
              {counts[key]}
            </span>
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-3xl px-6 py-6">
          {section === 'plan' && <PlanPane company={company} />}

          {section === 'documents' &&
            (reading ? (
              <div>
                <button
                  type="button"
                  className="text-link mb-4 font-mono text-[0.75rem] underline"
                  onClick={() => setReading(null)}
                >
                  back to all documents
                </button>
                <h2 className="display mb-1 text-xl">{reading.title}</h2>
                <p className="text-ink-soft mb-4 text-[0.875rem]">{reading.summary}</p>
                <ArtifactReader artifact={reading} body={body} />
              </div>
            ) : (
              <Pane
                title="Documents"
                blurb="Everything the team has produced, each labelled with how much of it is actually evidenced."
              >
                {artifacts.length === 0 ? (
                  <EmptyLine>Nothing yet. Documents appear here during a shift.</EmptyLine>
                ) : (
                  artifacts.map((artifact) => (
                    <DocRow key={artifact.id} artifact={artifact} onOpen={setReading} />
                  ))
                )}
              </Pane>
            ))}

          {section === 'vera' && (
            <Pane
              title="What Vera flagged"
              blurb="Vera is paid to find what's wrong, not to agree. Each flag names the claim and what would settle it."
            >
              {objections.length === 0 ? (
                <EmptyLine>Vera reviews at the end of every shift.</EmptyLine>
              ) : (
                objections.map((objection) => (
                  <ObjectionRow key={objection.id} objection={objection} />
                ))
              )}
            </Pane>
          )}

          {section === 'decisions' && (
            <Pane
              title="Decisions"
              blurb="Every call the team made, with its reasons and what was rejected."
            >
              {decisions.length === 0 ? (
                <EmptyLine>No decisions yet. Each one is logged here with its reasons.</EmptyLine>
              ) : (
                decisions.map((decision) => (
                  <DecisionRow key={decision.id} decision={decision} />
                ))
              )}
            </Pane>
          )}

          {section === 'money' && (
            <Pane
              title="Money"
              blurb="What's been spent, on what. When the cap is reached, everything stops and the work is kept."
            >
              <CapEditor
                cap={Number(company.budget.cap)}
                busy={busy}
                onSave={onSetBudget}
              />
              <LedgerTable ledger={ledger} />
            </Pane>
          )}

          {section === 'history' && (
            <Pane title="Past shifts" blurb="One entry per shift, oldest last.">
              {shifts.length === 0 ? (
                <EmptyLine>No shifts yet.</EmptyLine>
              ) : (
                shifts.map((shift) => <HistoryRow key={shift.id} shift={shift} />)
              )}
            </Pane>
          )}

          {section === 'settings' && (
            <SettingsPane
              company={company}
              busy={busy}
              onHalt={onHalt}
              onShare={onShare}
              onUnshare={onUnshare}
              onAutonomy={onAutonomy}
            />
          )}
        </div>
      </div>
    </div>
  )
}

function Pane({
  title,
  blurb,
  children,
}: {
  title: string
  blurb: string
  children: React.ReactNode
}) {
  return (
    <div>
      <h2 className="display text-xl">{title}</h2>
      <p className="text-ink-soft mt-1 mb-4 max-w-xl text-[0.8125rem] leading-snug">
        {blurb}
      </p>
      <div className="panel">{children}</div>
    </div>
  )
}

/* ------------------------------------------------------------------ plan */

function PlanPane({ company }: { company: Company }) {
  const { charter, progress } = company
  return (
    <div className="space-y-4">
      <div>
        <h2 className="display text-xl">The plan</h2>
        <p className="text-ink-soft mt-1 max-w-xl text-[0.8125rem] leading-snug">
          What the company is for, and how far along it is. The team is judged
          against this every shift.
        </p>
      </div>

      <div className="panel">
        <dl className="divide-rule-soft divide-y">
          <PlanRow label="building">{charter.one_liner || charter.idea}</PlanRow>
          <PlanRow label="for">{charter.audience || 'Not set yet — answer Ada in the chat.'}</PlanRow>
          <PlanRow label="done means">
            {charter.success_looks_like || 'Not set yet — answer Ada in the chat.'}
          </PlanRow>
          {charter.constraints.length > 0 && (
            <PlanRow label="never">{charter.constraints.join(' · ')}</PlanRow>
          )}
        </dl>
      </div>

      <div className="panel">
        <div className="px-4 py-3.5">
          <div className="flex items-baseline gap-3">
            <span className="numeric text-2xl leading-none">{progress.percent}%</span>
            <span className="text-ink-soft text-[0.875rem]">{progress.headline}</span>
          </div>
          <span className="bg-rule-soft mt-3 block h-2 w-full">
            <span
              className="bg-blue block h-full"
              style={{ width: `${progress.percent}%` }}
            />
          </span>
        </div>
        {progress.whats_missing.length > 0 && (
          <ol className="border-rule-soft border-t px-4 py-3">
            <li className="eyebrow text-ink-faint pb-1.5">still missing</li>
            {progress.whats_missing.map((item, i) => (
              <li key={item} className="flex gap-3 py-1 text-[0.8125rem] leading-snug">
                <span className="numeric text-ink-faint shrink-0">{i + 1}</span>
                <span>{item}</span>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  )
}

function PlanRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 px-4 py-3">
      <dt className="eyebrow text-ink-faint w-24 shrink-0 pt-0.5">{label}</dt>
      <dd className="min-w-0 text-[0.875rem] leading-relaxed">{children}</dd>
    </div>
  )
}

/* -------------------------------------------------------------- settings */

function SettingsPane({
  company,
  busy,
  onHalt,
  onShare,
  onUnshare,
  onAutonomy,
}: {
  company: Company
  busy: boolean
  onHalt: () => void
  onShare: () => void
  onUnshare: () => void
  onAutonomy: (value: string) => void
}) {
  const autonomy = (company.charter as { autonomy?: string }).autonomy ?? 'balanced'
  return (
    <div className="space-y-6">
      <div>
        <h2 className="display text-xl">Settings &amp; keys</h2>
        <p className="text-ink-soft mt-1 max-w-xl text-[0.8125rem] leading-snug">
          How much the team does on its own, keys it can use, the public link,
          and the stop button.
        </p>
      </div>

      <div className="panel">
        <p className="border-rule-soft border-b px-4 py-3">
          <span className="display text-base">On its own</span>
          <span className="text-ink-faint ml-3 font-mono text-[0.6875rem]">
            both ends spend faster — one on work, one on questions
          </span>
        </p>
        <div className="divide-rule-soft divide-y">
          {AUTONOMY_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              disabled={busy}
              aria-pressed={autonomy === option.value}
              onClick={() => onAutonomy(option.value)}
              className={cn(
                'focus-visible:ring-ring flex w-full items-baseline gap-3 px-4 py-2.5 text-left focus-visible:ring-2 focus-visible:outline-none',
                autonomy === option.value ? 'bg-ink text-paper' : 'hover:bg-secondary',
              )}
            >
              <span className="display w-28 shrink-0 text-[0.8125rem]">
                {option.label}
              </span>
              <span
                className={cn(
                  'min-w-0 text-[0.75rem] leading-snug',
                  autonomy === option.value ? 'text-paper/80' : 'text-ink-soft',
                )}
              >
                {option.blurb}
              </span>
            </button>
          ))}
        </div>
      </div>

      <Vault cid={company.id} />

      <div className="panel">
        <p className="border-rule-soft border-b px-4 py-3">
          <span className="display text-base">Public page</span>
        </p>
        <div className="px-4 py-3">
          {company.share ? (
            <>
              <p className="text-[0.875rem] leading-relaxed">
                A read-only page of this company is live. Documents marked public
                and every shift report are on it; notes and keys never are.
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <code className="bg-secondary px-2 py-1 font-mono text-[0.75rem]">
                  {window.location.origin}
                  {company.share.url}
                </code>
                <button className="btn py-1 text-[0.75rem]" onClick={onShare}>
                  copy the link
                </button>
                <button
                  className="btn py-1 text-[0.75rem]"
                  disabled={busy}
                  onClick={onUnshare}
                >
                  take it down
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-[0.875rem] leading-relaxed">
                Publish a read-only page anyone can open. Every file is scanned
                for anything private first; if the scan finds something, nothing
                is published.
              </p>
              <button
                className="btn mt-3 py-1.5 text-[0.8125rem]"
                disabled={busy}
                onClick={onShare}
              >
                publish the page
              </button>
            </>
          )}
        </div>
      </div>

      <div className="panel border-l-red border-l-4">
        <div className="px-4 py-3">
          <p className="display text-base">Stop everything</p>
          <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
            Stops all work immediately. Everything already done is saved, and you
            can start again whenever you like.
          </p>
          <button
            className="btn btn-danger mt-3 py-1.5 text-[0.8125rem]"
            disabled={busy || company.status === 'halted'}
            onClick={onHalt}
          >
            stop everything
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * The vault. A value goes in once and is never shown again — not to you, not on
 * the public page, not in the activity feed. The team can use it; nobody can
 * read it back out.
 */
function Vault({ cid }: { cid: string }) {
  const [items, setItems] = useState<VaultItem[]>([])
  const [name, setName] = useState('')
  const [value, setValue] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    void api.listVault(cid).then(setItems)
  }, [cid])

  async function add() {
    setSaving(true)
    setError(null)
    try {
      await api.setVault(cid, name.trim(), value)
      setItems(await api.listVault(cid))
      setName('')
      setValue('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  async function remove(itemName: string) {
    await api.deleteVault(cid, itemName)
    setItems(await api.listVault(cid))
  }

  return (
    <div className="panel">
      <p className="border-rule-soft border-b px-4 py-3">
        <span className="display text-base">Keys the team can use</span>
      </p>
      <p className="text-ink-soft px-4 pt-3 text-[0.8125rem] leading-snug">
        API keys, passwords, anything the team needs for its work. A value is
        shown exactly once — right now, while you type it. After that not even
        you can read it back, and it can never appear on the public page.
      </p>

      {items.length > 0 && (
        <ul className="border-rule-soft mx-4 mt-3 border">
          {items.map((item) => (
            <li
              key={item.name}
              className="border-rule-soft flex items-baseline gap-3 border-b px-3 py-2 last:border-b-0"
            >
              <Mark shape="square" tone="ink" className="self-center" />
              <code className="font-mono text-[0.8125rem]">{item.name}</code>
              <span className="text-ink-faint font-mono text-[0.6875rem]">
                {item.hint}
              </span>
              <button
                type="button"
                className="text-link ml-auto font-mono text-[0.6875rem] underline"
                onClick={() => remove(item.name)}
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <form
        className="flex flex-wrap items-end gap-2 px-4 py-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (name.trim() && value) void add()
        }}
      >
        <label className="block">
          <span className="eyebrow text-ink-faint block">name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="STRIPE_KEY"
            className="border-rule-soft placeholder:text-ink-faint focus-visible:ring-ring mt-1 w-40 border px-3 py-1.5 font-mono text-[0.8125rem] focus-visible:ring-2 focus-visible:outline-none"
          />
        </label>
        <label className="block min-w-0 flex-1">
          <span className="eyebrow text-ink-faint block">value</span>
          <input
            value={value}
            type="password"
            autoComplete="off"
            onChange={(e) => setValue(e.target.value)}
            placeholder="shown only while you type it"
            className="border-rule-soft placeholder:text-ink-faint focus-visible:ring-ring mt-1 w-full border px-3 py-1.5 font-mono text-[0.8125rem] focus-visible:ring-2 focus-visible:outline-none"
          />
        </label>
        <button
          type="submit"
          className="btn py-1.5 text-[0.8125rem]"
          disabled={saving || !name.trim() || !value}
        >
          keep it
        </button>
      </form>
      {error && <p className="text-red px-4 pb-3 text-[0.8125rem]">{error}</p>}
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
    </form>
  )
}
