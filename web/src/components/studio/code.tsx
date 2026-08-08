/**
 * The "code" tab: the files behind the website, readable, yours.
 *
 * Most people who use Werkhaus will never open this tab, and that is fine —
 * the point of it is ownership. Your company's work is ordinary files you can
 * take anywhere, not something locked inside us. The tab exists so that claim
 * is checkable.
 */

import { useEffect, useState } from 'react'
import type { WorkspaceFile } from '@/api/client'
import { api } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { cn } from '@/lib/utils'

export function Code({ cid, refreshKey }: { cid: string; refreshKey: number }) {
  const [files, setFiles] = useState<WorkspaceFile[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [body, setBody] = useState<string | null>(null)

  useEffect(() => {
    void api.listFiles(cid).then((list) => {
      setFiles(list)
      setSelected((current) => current ?? list.find((f) => f.kind === 'text')?.path ?? null)
    })
  }, [cid, refreshKey])

  useEffect(() => {
    if (!selected) return
    setBody(null)
    void api.readFile(cid, selected).then(setBody)
  }, [cid, selected])

  if (files.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6">
        <div className="max-w-sm text-center">
          <Mark shape="square" tone="faint" className="mx-auto !size-3" />
          <p className="display mt-5 text-lg">No files yet</p>
          <p className="text-ink-soft mt-2 text-[0.8125rem] leading-relaxed">
            When the team builds something, the actual files land here. They are
            ordinary code you own and can take anywhere — you never need to read
            them, but you always can.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1">
      <nav className="border-rule-soft w-56 shrink-0 overflow-y-auto border-r py-2">
        <p className="text-ink-faint px-4 pb-2 font-mono text-[0.625rem]">
          {files.length} {files.length === 1 ? 'file' : 'files'} · all yours
        </p>
        {files.map((file) => (
          <button
            key={file.path}
            type="button"
            disabled={file.kind === 'binary'}
            aria-current={selected === file.path ? 'true' : undefined}
            onClick={() => setSelected(file.path)}
            className={cn(
              'focus-visible:ring-ring flex w-full items-baseline gap-2 px-4 py-1.5 text-left focus-visible:ring-2 focus-visible:outline-none',
              selected === file.path ? 'bg-ink text-paper' : 'hover:bg-secondary',
              file.kind === 'binary' && 'opacity-50',
            )}
          >
            <span className="min-w-0 flex-1 truncate font-mono text-[0.75rem]">
              {file.path}
            </span>
            <span
              className={cn(
                'shrink-0 font-mono text-[0.625rem]',
                selected === file.path ? 'text-paper/70' : 'text-ink-faint',
              )}
            >
              {size(file.size)}
            </span>
          </button>
        ))}
      </nav>

      <div className="min-h-0 flex-1 overflow-auto">
        {selected === null ? (
          <p className="text-ink-faint px-6 py-6 font-mono text-[0.8125rem]">
            pick a file on the left
          </p>
        ) : body === null ? (
          <p className="text-ink-faint px-6 py-6 font-mono text-[0.8125rem]">loading…</p>
        ) : (
          <div>
            <p className="border-rule-soft bg-panel sticky top-0 border-b px-4 py-2 font-mono text-[0.6875rem]">
              workspace/{selected}
            </p>
            <ol className="py-3">
              {body.split('\n').map((line, i) => (
                <li key={i} className="flex px-2 leading-[1.45]">
                  <span
                    className="text-ink-faint w-10 shrink-0 pr-3 text-right font-mono text-[0.6875rem] select-none"
                    aria-hidden
                  >
                    {i + 1}
                  </span>
                  <code className="font-mono text-[0.75rem] whitespace-pre-wrap">
                    {line || ' '}
                  </code>
                </li>
              ))}
            </ol>
          </div>
        )}
      </div>
    </div>
  )
}

function size(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  return `${(bytes / 1024).toFixed(1)} kB`
}
