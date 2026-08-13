/**
 * Every MCP server we know of, and a way to connect any of them.
 *
 * Deliberately separated from the six verified cards next to it. Those carry
 * walkthrough prose written against the provider's real sign-up flow and a
 * probe that proves the key works. These carry what their publisher wrote.
 * Blurring the two would make the verified ones worthless, because nobody
 * could tell which was which — so this says "nobody here has tested these"
 * and means it.
 */

import { useCallback, useEffect, useState } from 'react'
import { toast } from 'sonner'
import { api, type DirectoryEntry, type McpConnection } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

export function Directory({ cid }: { cid: string }) {
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<DirectoryEntry[]>([])
  const [total, setTotal] = useState<number | null>(null)
  const [connected, setConnected] = useState<McpConnection[]>([])
  const [picked, setPicked] = useState<DirectoryEntry | null>(null)
  const [busy, setBusy] = useState(false)

  const reload = useCallback(async () => {
    setConnected(await api.listMcp(cid))
  }, [cid])

  useEffect(() => {
    void api.mcpCategories().then((c) => setTotal(c.total))
    void reload()
  }, [reload])

  useEffect(() => {
    const id = setTimeout(() => {
      void api.searchDirectory(q, 12).then(setHits)
    }, 200)
    return () => clearTimeout(id)
  }, [q])

  async function remove(name: string) {
    setBusy(true)
    try {
      await api.removeMcp(cid, name)
      await reload()
    } finally {
      setBusy(false)
    }
  }

  if (picked) {
    return (
      <ConnectServer
        cid={cid}
        entry={picked}
        onCancel={() => setPicked(null)}
        onDone={async () => {
          setPicked(null)
          await reload()
        }}
      />
    )
  }

  return (
    <div className="space-y-4">
      {connected.length > 0 && (
        <ul className="bg-rule border-rule grid gap-px border">
          {connected.map((server) => (
            <li key={server.name} className="bg-panel flex items-baseline gap-2 px-3 py-2">
              <Mark
                shape={server.verified ? 'circle' : 'square'}
                tone={server.verified ? 'blue' : 'ink'}
                className="self-center"
              />
              <span className="display text-[0.8125rem]">{server.label}</span>
              <span className="text-ink-faint font-mono text-[0.625rem]">
                {server.transport === 'stdio' ? server.command : server.url}
              </span>
              <button
                type="button"
                disabled={busy}
                onClick={() => remove(server.name)}
                className="text-link ml-auto font-mono text-[0.625rem] underline"
              >
                remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <div>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={
            total ? `Search ${total.toLocaleString()} servers…` : 'Search…'
          }
          className="border-rule-soft block w-full border px-3 py-2 text-[0.875rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
        />
        <p className="text-ink-faint mt-1 text-[0.75rem] leading-snug">
          Published by other people and untested by us. Connecting one hands it
          whatever you type in, so read what it does first.
        </p>
      </div>

      <ul className="divide-rule-soft divide-y">
        {hits.map((entry) => (
          <li key={entry.url} className="flex items-baseline gap-2 py-2">
            <div className="min-w-0">
              <p className="flex items-baseline gap-2">
                <span className="display text-[0.8125rem]">{entry.name}</span>
                {entry.official && (
                  <span className="text-ink-faint font-mono text-[0.5625rem]">
                    official
                  </span>
                )}
                {entry.remote && (
                  <span className="text-ink-faint font-mono text-[0.5625rem]">
                    remote
                  </span>
                )}
              </p>
              <p className="text-ink-soft line-clamp-2 text-[0.75rem] leading-snug">
                {entry.description}
              </p>
            </div>
            <button
              type="button"
              onClick={() => setPicked(entry)}
              className={cn(
                'btn ml-auto shrink-0 py-0.5 text-[0.75rem]',
                !entry.url_hint && !entry.cmd_hint && 'opacity-70',
              )}
            >
              connect
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

function ConnectServer({
  cid,
  entry,
  onDone,
  onCancel,
}: {
  cid: string
  entry: DirectoryEntry
  onDone: () => void
  onCancel: () => void
}) {
  const remote = Boolean(entry.url_hint)
  const [name, setName] = useState(
    entry.name.split('/').pop()!.replace(/[^a-zA-Z0-9]+/g, '_').toLowerCase().slice(0, 24),
  )
  const [url, setUrl] = useState(entry.url_hint ?? '')
  const [command, setCommand] = useState(entry.cmd_hint ?? '')
  const [env, setEnv] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)
  const [failed, setFailed] = useState<string | null>(null)

  async function save() {
    setBusy(true)
    setFailed(null)
    try {
      await api.addMcp(cid, {
        name,
        label: entry.name,
        transport: remote ? entry.transport || 'streamable-http' : 'stdio',
        url: remote ? url : undefined,
        command: remote ? undefined : command,
        env,
        directory_url: entry.url,
      })
      toast.success(`${entry.name} is connected.`)
      onDone()
    } catch (e) {
      setFailed((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel p-4">
      <p className="display text-base">{entry.name}</p>
      <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
        {entry.description}
      </p>
      <a
        href={entry.url}
        target="_blank"
        rel="noreferrer noopener"
        className="text-link mt-1 block font-mono text-[0.6875rem] underline"
      >
        read what it does
      </a>

      <div className="mt-4 space-y-3">
        <label className="block">
          <span className="eyebrow text-ink-faint">short name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
          />
        </label>

        {remote ? (
          <label className="block">
            <span className="eyebrow text-ink-faint">address</span>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
            />
          </label>
        ) : (
          <label className="block">
            <span className="eyebrow text-ink-faint">command</span>
            <input
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              placeholder="npx -y some-mcp-server"
              className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
            />
            <span className="text-ink-faint mt-1 block text-[0.75rem] leading-snug">
              Runs on the machine your shifts run on. The repository's readme
              says what it should be.
            </span>
          </label>
        )}

        {/* Generated from what the server itself declared it needs. */}
        {entry.env.map((field) => (
          <label key={field.name} className="block">
            <span className="eyebrow text-ink-faint">{field.name}</span>
            <input
              type={field.secret ? 'password' : 'text'}
              autoComplete="off"
              value={env[field.name] ?? ''}
              onChange={(e) => setEnv({ ...env, [field.name]: e.target.value })}
              className="border-rule-soft mt-1 block w-full border px-2 py-1.5 font-mono text-[0.8125rem] outline-none focus-visible:ring-ring focus-visible:ring-2"
            />
            {field.description && (
              <span className="text-ink-faint mt-1 block text-[0.75rem] leading-snug">
                {field.description}
              </span>
            )}
          </label>
        ))}
      </div>

      {failed && (
        <p className="text-red mt-3 text-[0.8125rem] leading-snug">{failed}</p>
      )}

      <div className="mt-4 flex items-center gap-3">
        <button
          type="button"
          className="btn btn-primary py-1 text-[0.8125rem]"
          disabled={busy || !name.trim() || (remote ? !url.trim() : !command.trim())}
          onClick={save}
        >
          {busy ? 'saving' : 'connect it'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="text-link font-mono text-[0.6875rem] underline"
        >
          cancel
        </button>
      </div>
    </div>
  )
}
