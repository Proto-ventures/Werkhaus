/**
 * What the company is connected to.
 *
 * Its own tab rather than a settings sub-page, because this is where a
 * document-writing toy becomes a business that can take an order. A card never
 * shows a bare service name: it says what the service does for *this* company,
 * what it costs, how long connecting takes, and — the part that makes it an
 * argument rather than a chore — which piece of work it is currently holding up.
 */

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api, type IntegrationState } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { ConnectWalkthrough } from '@/components/studio/connect'
import { Directory } from '@/components/studio/directory'
import { Vault } from '@/components/studio/planwork'
import { cn } from '@/lib/utils'

const GROUPS: { label: string; of: string[] }[] = [
  { label: 'what it runs on', of: ['database', 'hosting', 'email'] },
  { label: 'getting paid', of: ['payments'] },
]

export function Services({ cid }: { cid: string }) {
  const [items, setItems] = useState<IntegrationState[] | null>(null)
  const [connecting, setConnecting] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setItems(await api.listIntegrations(cid))
  }, [cid])

  useEffect(() => {
    void load()
  }, [load])

  if (items === null) {
    return <p className="text-ink-faint font-mono text-sm">loading...</p>
  }

  const open = connecting
    ? items.find((i) => i.spec.id === connecting)
    : undefined

  if (open) {
    return (
      <div className="mx-auto max-w-2xl">
        <ConnectWalkthrough
          cid={cid}
          spec={open.spec}
          onCancel={() => setConnecting(null)}
          onDone={() => {
            setConnecting(null)
            void load()
          }}
        />
      </div>
    )
  }

  async function act(fn: () => Promise<unknown>, said?: string) {
    setBusy(true)
    try {
      await fn()
      if (said) toast.success(said)
      await load()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const connected = items.filter(
    (i) => i.connection.status === 'connected',
  ).length

  return (
    <div className="space-y-8">
      <div>
        <h2 className="display text-xl">What it's connected to</h2>
        <p className="text-ink-soft mt-1 max-w-xl text-[0.9375rem] leading-snug">
          Your business needs accounts of its own — somewhere to keep customers,
          somewhere to live on the internet, a way to take money. You make each
          account; the team does the rest. {connected} of {items.length} connected.
        </p>
      </div>

      {GROUPS.map((group) => {
        const cards = items.filter((i) => group.of.includes(i.spec.category))
        if (cards.length === 0) return null
        return (
          <section key={group.label}>
            <p className="eyebrow text-ink-faint mb-2">{group.label}</p>
            <div className="grid gap-px bg-rule border-rule border sm:grid-cols-2">
              {cards.map((item) => (
                <Card
                  key={item.spec.id}
                  item={item}
                  busy={busy}
                  onConnect={() => setConnecting(item.spec.id)}
                  onRecheck={() =>
                    act(
                      () => api.verifyIntegration(cid, item.spec.id),
                      'Checked.',
                    )
                  }
                  onDisconnect={() =>
                    act(
                      () => api.disconnectIntegration(cid, item.spec.id),
                      `${item.spec.display_name} is disconnected.`,
                    )
                  }
                />
              ))}
            </div>
          </section>
        )
      })}

      <section>
        <p className="eyebrow text-ink-faint mb-2">anything else</p>
        <p className="text-ink-soft mb-3 max-w-xl text-[0.8125rem] leading-snug">
          The six above are set up by us and checked before they're saved.
          Below is every other service anyone has published an MCP server for —
          thousands of them, none tested by us.
        </p>
        <Directory cid={cid} />
      </section>

      <div>
        <p className="eyebrow text-ink-faint mb-2">other keys</p>
        <Vault cid={cid} allowance={null} />
      </div>
    </div>
  )
}

function Card({
  item,
  busy,
  onConnect,
  onRecheck,
  onDisconnect,
}: {
  item: IntegrationState
  busy: boolean
  onConnect: () => void
  onRecheck: () => void
  onDisconnect: () => void
}) {
  const { spec, connection } = item
  const state = connection.status
  const mark =
    state === 'connected'
      ? { shape: 'circle' as const, tone: 'blue' as const }
      : state === 'needs_attention'
        ? { shape: 'triangle' as const, tone: 'red' as const }
        : { shape: 'ring' as const, tone: 'faint' as const }

  return (
    <div className="bg-panel flex flex-col p-4">
      <div className="flex items-baseline gap-2">
        <Mark {...mark} className="self-center" />
        <span className="display text-[0.9375rem]">{spec.display_name}</span>
        {spec.availability === 'beta' && (
          <span className="text-ink-faint font-mono text-[0.625rem]">in testing</span>
        )}
        <span className="text-ink-faint ml-auto font-mono text-[0.625rem]">
          {state === 'connected'
            ? 'connected'
            : state === 'needs_attention'
              ? 'needs a look'
              : `about ${spec.minutes} min`}
        </span>
      </div>

      <p className="text-ink-soft mt-2 text-[0.875rem] leading-snug">
        {spec.what_it_does}
      </p>

      {state === 'connected' ? (
        <>
          {connection.scope_note && (
            <p className="mt-2 text-[0.8125rem] leading-snug">
              {connection.scope_note}
            </p>
          )}
          <ul className="mt-2">
            {connection.fields_present.map((name) => (
              <li
                key={name}
                className="text-ink-faint font-mono text-[0.6875rem] leading-relaxed"
              >
                {name} · {connection.hints[name] ?? 'saved'}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <ul className="mt-2 space-y-1">
          {spec.unlocks.map((line) => (
            <li
              key={line}
              className="text-ink-soft flex gap-2 text-[0.8125rem] leading-snug"
            >
              <Mark shape="square" tone="faint" className="mt-1.5 shrink-0" />
              <span>{line}</span>
            </li>
          ))}
        </ul>
      )}

      {connection.blocks.length > 0 && state !== 'connected' && (
        <p className="text-ink-soft mt-2 text-[0.8125rem] leading-snug">
          Holding up: {connection.blocks.join(', ').toLowerCase()}.
        </p>
      )}

      {connection.message && state === 'needs_attention' && (
        <p className="text-red mt-2 text-[0.8125rem] leading-snug">
          {connection.message}
        </p>
      )}

      {connection.unavailable_reason && (
        <p className="text-ink-soft mt-2 text-[0.8125rem] leading-snug">
          {connection.unavailable_reason}
        </p>
      )}

      {spec.cost_note && state !== 'connected' && (
        <p className="text-ink-faint mt-2 text-[0.75rem] leading-snug">
          {spec.cost_note}
        </p>
      )}

      <div className="mt-auto flex items-center gap-3 pt-3">
        {state === 'connected' ? (
          <>
            <button
              type="button"
              className="btn py-1 text-[0.8125rem]"
              disabled={busy}
              onClick={onRecheck}
            >
              check it still works
            </button>
            <button
              type="button"
              className="text-link font-mono text-[0.6875rem] underline"
              onClick={onDisconnect}
            >
              disconnect
            </button>
          </>
        ) : state === 'unavailable' ? (
          spec.docs_url && (
            <a
              href={spec.docs_url}
              target="_blank"
              rel="noreferrer noopener"
              className={cn('text-link font-mono text-[0.6875rem] underline')}
            >
              read about it
            </a>
          )
        ) : (
          <button
            type="button"
            className="btn btn-primary py-1 text-[0.8125rem]"
            disabled={busy}
            onClick={onConnect}
          >
            {state === 'needs_attention' ? 'fix it' : 'connect'}
          </button>
        )}
      </div>
    </div>
  )
}
