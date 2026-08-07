import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { api } from '@/api/client'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Page } from '@/components/shell'

/**
 * Charter capture.
 *
 * This is the real UX problem, not the dashboard. A founder types two sentences;
 * the team needs an audience, constraints and a definition of done. No amount of
 * polish downstream fixes a vague charter, so we ask the three questions here —
 * one at a time, in the founder's language, with an example under each.
 *
 * "What would make this a success?" becomes the objective the company is judged
 * against for its whole life, so it is the one field worth pushing on.
 */
const STEPS = [
  {
    key: 'idea',
    label: 'What are you building?',
    help: 'A couple of sentences is plenty. Write it how you would say it out loud.',
    placeholder:
      'A monthly subscription box for hand-thrown ceramics. One object a month, made by a real potter.',
    rows: 4,
  },
  {
    key: 'audience',
    label: 'Who is it for?',
    help: 'Be specific. "Everyone" gives the team nothing to work with.',
    placeholder:
      'People in small UK flats, late twenties to mid forties, who buy few objects but care what they are.',
    rows: 3,
  },
  {
    key: 'success_looks_like',
    label: 'What would make this a success?',
    help: 'Something you could check. The team is measured against this every shift.',
    placeholder:
      'A live waitlist page with at least 3 real signups and a price I can defend.',
    rows: 3,
  },
] as const

export function NewCompany() {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [values, setValues] = useState<Record<string, string>>({})
  const [constraints, setConstraints] = useState('')
  const [busy, setBusy] = useState(false)

  const current = STEPS[step]
  const value = values[current.key] ?? ''
  const last = step === STEPS.length - 1

  async function create() {
    setBusy(true)
    try {
      const company = await api.createCompany(values.idea)
      await api.updateCharter(company.id, {
        audience: values.audience,
        success_looks_like: values.success_looks_like,
        constraints: constraints
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
      })
      toast.success('Company created. Start the first shift when you are ready.')
      navigate(`/c/${company.id}`)
    } catch (e) {
      toast.error((e as Error).message)
      setBusy(false)
    }
  }

  return (
    <Page>
      <div className="mx-auto max-w-xl">
        <p className="eyebrow text-ink-faint">
          Step {step + 1} of {STEPS.length}
        </p>
        <div className="bg-rule-soft mt-2 flex h-1 gap-px" aria-hidden>
          {STEPS.map((s, i) => (
            <div
              key={s.key}
              className={i <= step ? 'bg-blue flex-1' : 'bg-rule-soft flex-1'}
            />
          ))}
        </div>

        <h1 className="display mt-6 text-2xl leading-tight sm:text-3xl">
          {current.label}
        </h1>
        <p className="text-ink-soft mt-1.5 text-[0.9375rem] leading-snug">
          {current.help}
        </p>

        <Textarea
          key={current.key}
          autoFocus
          rows={current.rows}
          value={value}
          placeholder={current.placeholder}
          onChange={(e) =>
            setValues((prev) => ({ ...prev, [current.key]: e.target.value }))
          }
          className="mt-4 text-[0.9375rem]"
        />

        {last && (
          <div className="mt-6">
            <Label htmlFor="constraints" className="display text-base">
              Anything the team must not do?
            </Label>
            <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
              Optional, one per line. The team stops and asks before breaking
              one of these.
            </p>
            <Textarea
              id="constraints"
              rows={3}
              value={constraints}
              placeholder={'UK only for the first year\nNo paid advertising'}
              onChange={(e) => setConstraints(e.target.value)}
              className="mt-2 text-[0.9375rem]"
            />
          </div>
        )}

        <div className="mt-6 flex items-center gap-2">
          {step > 0 && (
            <button className="btn" onClick={() => setStep(step - 1)}>
              back
            </button>
          )}
          {last ? (
            <button className="btn btn-primary" onClick={create} disabled={busy || !value.trim()}>
              {busy ? 'setting up...' : 'create the company'}
            </button>
          ) : (
            <button
              className="btn btn-primary"
              onClick={() => setStep(step + 1)}
              disabled={!value.trim()}
            >
              next
            </button>
          )}
        </div>
      </div>
    </Page>
  )
}
