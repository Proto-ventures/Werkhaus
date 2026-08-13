/**
 * What the employees think with.
 *
 * A model is a real decision, not a preference: free tiers differ by an order
 * of magnitude, and a model that will not call tools cannot work a shift at all
 * — it answers in prose and files nothing. So the picker leads with what each
 * provider actually gives you, names the models known to work, and says out
 * loud which plausible-looking ones are dead ends.
 *
 * The last option is deliberately not a long tail of half-tested cards. Almost
 * every inference platform speaks the OpenAI protocol, so one honest entry — an
 * address and a key — covers all of them, including the ones that don't exist
 * yet.
 */

import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'
import { api, type BrainChoice, type BrainProvider } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

export function Brain({ cid }: { cid: string }) {
  const [providers, setProviders] = useState<BrainProvider[]>([])
  const [choice, setChoice] = useState<BrainChoice | null>(null)
  const [open, setOpen] = useState(false)
  const [picked, setPicked] = useState<string>('gemini')
  const [model, setModel] = useState('')
  const [key, setKey] = useState('')
  const [baseUrl, setBaseUrl] = useState('')
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<{ message: string; hint?: string } | null>(
    null,
  )

  useEffect(() => {
    void api.listBrains().then(setProviders)
    void api.getBrain(cid).then((c) => {
      setChoice(c)
      if (c.provider) setPicked(c.provider)
      if (c.model) setModel(c.model)
      if (c.base_url) setBaseUrl(c.base_url)
    })
  }, [cid])

  const provider = useMemo(
    () => providers.find((p) => p.id === picked),
    [providers, picked],
  )
  const avoided = provider?.avoid?.[model.trim()]

  async function save() {
    if (!provider) return
    setBusy(true)
    setFailed(null)
    try {
      const saved = await api.setBrain(cid, {
        provider: provider.id,
        model: model.trim(),
        key: key.trim(),
        base_url: provider.needs_base_url ? baseUrl.trim() : undefined,
      })
      setChoice(saved)
      setKey('')
      setOpen(false)
      toast.success(`The team thinks with ${saved.model}.`)
    } catch (e) {
      const detail = (e as { detail?: { hint?: string | null } }).detail
      setFailed({ message: (e as Error).message, hint: detail?.hint ?? undefined })
    } finally {
      setBusy(false)
    }
  }

  if (!choice) return null

  return (
    <div className="panel">
      <p className="border-rule-soft flex items-baseline gap-3 border-b px-4 py-3">
        <span className="display text-base">What the team thinks with</span>
        {choice.configured && !open && (
          <button
            type="button"
            className="text-link ml-auto font-mono text-[0.6875rem] underline"
            onClick={() => setOpen(true)}
          >
            change
          </button>
        )}
      </p>

      {!open ? (
        <div className="px-4 py-3">
          {choice.configured ? (
            <>
              <p className="flex items-baseline gap-2">
                <Mark shape="circle" tone="blue" className="self-center" />
                <span className="font-mono text-[0.875rem]">{choice.model}</span>
                <span className="text-ink-faint font-mono text-[0.6875rem]">
                  {choice.provider}
                </span>
              </p>
              {choice.base_url && (
                <p className="text-ink-faint mt-1 font-mono text-[0.6875rem]">
                  {choice.base_url}
                </p>
              )}
              {choice.key_hint && (
                <p className="text-ink-faint mt-1 font-mono text-[0.6875rem]">
                  key · {choice.key_hint}
                </p>
              )}
            </>
          ) : (
            <>
              <p className="text-[0.875rem] leading-snug">
                The team is thinking with the model this Werkhaus was started
                with. You can point it at your own instead — including anything
                that speaks the OpenAI API.
              </p>
              <button
                type="button"
                className="btn btn-primary mt-3 py-1 text-[0.8125rem]"
                disabled={!choice.editable}
                onClick={() => setOpen(true)}
              >
                choose a model
              </button>
            </>
          )}
          {choice.note && (
            <p className="text-ink-soft mt-2 text-[0.8125rem] leading-snug">
              {choice.note}
            </p>
          )}
        </div>
      ) : (
        <div className="px-4 py-3">
          <div className="border-rule-soft divide-rule-soft grid divide-y border sm:grid-cols-2 sm:divide-x sm:divide-y-0">
            <ul className="max-h-56 overflow-y-auto">
              {providers.map((entry) => (
                <li key={entry.id}>
                  <button
                    type="button"
                    aria-pressed={picked === entry.id}
                    onClick={() => {
                      setPicked(entry.id)
                      setModel(entry.models[0] ?? '')
                      setFailed(null)
                    }}
                    className={cn(
                      'block w-full px-3 py-2 text-left',
                      picked === entry.id ? 'bg-ink text-paper' : 'hover:bg-secondary',
                    )}
                  >
                    <span className="display block text-[0.8125rem]">
                      {entry.name}
                    </span>
                    <span
                      className={cn(
                        'block text-[0.75rem] leading-snug',
                        picked === entry.id ? 'text-paper/80' : 'text-ink-soft',
                      )}
                    >
                      {entry.free_note}
                    </span>
                  </button>
                </li>
              ))}
            </ul>

            <div className="space-y-3 p-3">
              {provider?.models.length ? (
                <div>
                  <span className="eyebrow text-ink-faint">
                    models that can work a shift
                  </span>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {provider.models.map((name) => (
                      <button
                        key={name}
                        type="button"
                        onClick={() => setModel(name)}
                        className={cn(
                          'border-rule-soft border px-1.5 py-0.5 font-mono text-[0.6875rem]',
                          model === name ? 'bg-ink text-paper' : 'hover:bg-secondary',
                        )}
                      >
                        {name}
                      </button>
                    ))}
                  </div>
                </div>
              ) : null}

              <label className="block">
                <span className="eyebrow text-ink-faint">model</span>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  spellCheck={false}
                  className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
                />
              </label>

              {provider?.needs_base_url && (
                <label className="block">
                  <span className="eyebrow text-ink-faint">address</span>
                  <input
                    value={baseUrl}
                    onChange={(e) => setBaseUrl(e.target.value)}
                    placeholder="https://api.swarms.world/v1"
                    spellCheck={false}
                    className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
                  />
                  <span className="text-ink-faint mt-1 block text-[0.75rem] leading-snug">
                    Usually ends in /v1 — the part where the service's API
                    begins.
                  </span>
                </label>
              )}

              <label className="block">
                <span className="eyebrow text-ink-faint">key</span>
                <input
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  autoComplete="off"
                  spellCheck={false}
                  className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
                />
                {provider?.key_hint && (
                  <span className="text-ink-faint mt-1 block text-[0.75rem]">
                    {provider.key_hint}
                  </span>
                )}
              </label>

              {provider?.console_url && (
                <a
                  href={provider.console_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-link block font-mono text-[0.6875rem] underline"
                >
                  where to get one
                </a>
              )}
            </div>
          </div>

          {avoided && (
            <p className="border-yellow bg-yellow/10 mt-3 border-l-2 px-3 py-2 text-[0.8125rem] leading-snug">
              That one {avoided}.
            </p>
          )}

          {failed && (
            <div className="border-red mt-3 border-l-2 px-3 py-2">
              <p className="text-red text-[0.875rem] leading-snug">
                {failed.message}
              </p>
              {failed.hint && (
                <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
                  {failed.hint}
                </p>
              )}
              <p className="text-ink-faint mt-1 text-[0.8125rem]">
                Nothing was saved.
              </p>
            </div>
          )}

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              className="btn btn-primary py-1 text-[0.8125rem]"
              disabled={busy || !model.trim() || !key.trim() || Boolean(avoided)}
              onClick={save}
            >
              {busy ? 'checking with them' : 'check it and save'}
            </button>
            <button
              type="button"
              className="text-link font-mono text-[0.6875rem] underline"
              onClick={() => {
                setOpen(false)
                setFailed(null)
              }}
            >
              cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
