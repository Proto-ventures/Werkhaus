/**
 * The guided walkthrough for one service.
 *
 * A full pane rather than a modal: this asks for a password-shaped value, often
 * on a phone, while the person is switching between two browser tabs. A modal
 * makes that miserable.
 *
 * The words carry the whole thing. Every step must be followable without its
 * picture, because the pictures are a slot we fill later — and a walkthrough
 * that can't ship until someone records six screencasts is a walkthrough that
 * doesn't ship.
 */

import { useMemo, useState } from 'react'
import { api, type CredentialField, type IntegrationSpec } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

export function ConnectWalkthrough({
  cid,
  spec,
  onDone,
  onCancel,
}: {
  cid: string
  spec: IntegrationSpec
  onDone: () => void
  onCancel: () => void
}) {
  const steps = spec.steps
  const [at, setAt] = useState(0)
  const [values, setValues] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<{ message: string; hint?: string } | null>(
    null,
  )
  const [done, setDone] = useState<string | null>(null)

  const byName = useMemo(() => {
    const map: Record<string, CredentialField> = {}
    for (const field of spec.fields) map[field.name] = field
    return map
  }, [spec.fields])

  const step = steps[at]
  const field = step?.field ? byName[step.field] : undefined
  const last = at === steps.length - 1
  const value = field ? (values[field.name] ?? '') : ''
  const badShape = Boolean(
    field?.pattern && value && !new RegExp(field.pattern).test(value.trim()),
  )

  async function submit() {
    setBusy(true)
    setFailed(null)
    try {
      const state = await api.connectIntegration(cid, spec.id, values)
      setDone(state.connection.scope_note ?? 'Connected.')
    } catch (e) {
      const detail = (e as { detail?: { hint?: string | null } }).detail
      setFailed({
        message: (e as Error).message,
        hint: detail?.hint ?? undefined,
      })
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="panel p-6">
        <p className="flex items-baseline gap-2">
          <Mark shape="circle" tone="blue" />
          <span className="display text-lg">{spec.display_name} is connected</span>
        </p>
        <p className="mt-3 text-[0.9375rem] leading-relaxed">{done}</p>
        {spec.unlocks.length > 0 && (
          <ul className="mt-4 space-y-1">
            {spec.unlocks.map((line) => (
              <li key={line} className="flex gap-2.5 text-[0.875rem] leading-snug">
                <Mark shape="square" tone="ink" className="mt-1.5 shrink-0" />
                <span>{line}</span>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="btn btn-primary mt-5" onClick={onDone}>
          done
        </button>
      </div>
    )
  }

  return (
    <div className="panel">
      <div className="border-rule-soft flex items-baseline justify-between gap-3 border-b px-4 py-3">
        <span className="display text-base">Connect {spec.display_name}</span>
        <span className="text-ink-faint font-mono text-[0.6875rem]">
          step {at + 1} of {steps.length} · about {spec.minutes} minutes
        </span>
      </div>

      <div className="px-4 py-4">
        <p className="display text-[0.9375rem]">{step.title}</p>
        <p className="mt-1.5 max-w-prose text-[0.9375rem] leading-relaxed">
          {step.body}
        </p>

        {step.warning && (
          <p className="border-yellow bg-yellow/10 mt-3 border-l-2 px-3 py-2 text-[0.875rem] leading-snug">
            {step.warning}
          </p>
        )}

        {step.link && (
          <a
            href={step.link}
            target="_blank"
            rel="noreferrer noopener"
            className="btn mt-3 inline-block"
          >
            {step.link_label ?? 'Open it'}
          </a>
        )}

        {/* A slot. If nobody has recorded this step yet, the page simply
            doesn't show a broken image. */}
        {step.media && (
          <img
            src={`/walkthroughs/${step.media}`}
            alt={step.media_alt ?? ''}
            loading="lazy"
            onError={(e) => {
              e.currentTarget.style.display = 'none'
            }}
            className="border-rule-soft mt-3 w-full border"
          />
        )}

        {field && (
          <label className="mt-4 block">
            <span className="eyebrow text-ink-faint">{field.label}</span>
            <input
              type={field.secret_input ? 'password' : 'text'}
              value={value}
              autoComplete="off"
              spellCheck={false}
              onChange={(e) =>
                setValues({ ...values, [field.name]: e.target.value })
              }
              className={cn(
                'border-rule-soft mt-1 block w-full border px-3 py-2 font-mono text-[0.875rem] outline-none focus-visible:ring-ring focus-visible:ring-2',
                badShape && 'border-red',
              )}
            />
            {badShape && field.help && (
              <span className="text-red mt-1 block text-[0.8125rem] leading-snug">
                {field.help}
              </span>
            )}
          </label>
        )}

        {failed && (
          <div className="border-red mt-4 border-l-2 px-3 py-2">
            <p className="text-red text-[0.875rem] leading-snug">{failed.message}</p>
            {failed.hint && (
              <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
                {failed.hint}
              </p>
            )}
            <p className="text-ink-faint mt-1 text-[0.8125rem] leading-snug">
              Nothing was saved.
            </p>
          </div>
        )}
      </div>

      <div className="border-rule-soft flex items-center justify-between gap-3 border-t px-4 py-2.5">
        <button
          type="button"
          className="text-link font-mono text-[0.75rem] underline"
          onClick={() => (at === 0 ? onCancel() : setAt(at - 1))}
        >
          {at === 0 ? 'not now' : 'back'}
        </button>
        {last ? (
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy || badShape || (Boolean(field) && !value.trim())}
            onClick={submit}
          >
            {busy ? 'checking with them' : spec.verify_label}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={badShape}
            onClick={() => setAt(at + 1)}
          >
            next
          </button>
        )}
      </div>
    </div>
  )
}
