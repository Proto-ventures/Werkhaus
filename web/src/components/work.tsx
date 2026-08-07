/**
 * What the company produced, and what's wrong with it.
 *
 * The critic's objections sit at the same visual weight as the artifacts, not in
 * a tab behind them. A non-technical founder can't evaluate whether a market
 * analysis is any good — but they can absolutely evaluate "this price is
 * defended against competitors and never against a customer."
 */

import { ExternalLink } from 'lucide-react'
import type { Artifact } from '@/api/client'
import { CONFIDENCE } from '@/lib/display'
import { cn } from '@/lib/utils'


/** Reader for a single artifact. Markdown, rendered plainly and legibly. */
export function ArtifactReader({
  artifact,
  body,
}: {
  artifact: Artifact
  body: string | null
}) {
  const tone = CONFIDENCE[artifact.confidence]
  return (
    <div>
      <div className={cn('bg-secondary py-3 pl-4', tone.rule)}>
        <span className={cn('eyebrow', tone.className)}>{tone.label}</span>
        <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
          {tone.blurb}
        </p>
        {artifact.sources.length > 0 && (
          <ul className="mt-2 space-y-1">
            {artifact.sources.map((source) => (
              <li key={source}>
                <a
                  href={source}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="text-ink-soft inline-flex items-center gap-1 text-[0.75rem] underline underline-offset-2 hover:text-ink"
                >
                  {source}
                  <ExternalLink className="size-3" aria-hidden />
                </a>
              </li>
            ))}
          </ul>
        )}
      </div>

      {artifact.preview_url && (
        <a
          href={artifact.preview_url}
          target="_blank"
          rel="noreferrer noopener"
          className="border-rule-soft hover:bg-secondary/50 mt-4 flex items-center gap-2 border p-3 text-[0.875rem]"
        >
          Open the live page
          <ExternalLink className="text-ink-soft ml-auto size-3.5" aria-hidden />
        </a>
      )}

      <Markdown source={body} />
    </div>
  )
}

/**
 * A deliberately small Markdown renderer.
 *
 * Real artifacts are long, contain tables, and occasionally contradict
 * themselves. This handles headings, tables, lists, emphasis and rules, and
 * shows anything else as plain text rather than pretending.
 */
function Markdown({ source }: { source: string | null }) {
  if (source === null) {
    return <p className="text-ink-soft mt-6 text-sm">Loading…</p>
  }
  const blocks = source.split('\n\n')
  return (
    <div className="mt-6 space-y-4">
      {blocks.map((block, i) => {
        const trimmed = block.trim()
        if (!trimmed) return null

        if (trimmed.startsWith('|')) {
          return <Table key={i} block={trimmed} />
        }
        if (trimmed.startsWith('### ')) {
          return (
            <h4 key={i} className="display pt-2 text-base">
              {inline(trimmed.slice(4))}
            </h4>
          )
        }
        if (trimmed.startsWith('## ')) {
          return (
            <h3 key={i} className="display pt-3 text-lg">
              {inline(trimmed.slice(3))}
            </h3>
          )
        }
        if (trimmed.startsWith('# ')) {
          return (
            <h2 key={i} className="display text-xl">
              {inline(trimmed.slice(2))}
            </h2>
          )
        }
        if (trimmed === '---') {
          return <hr key={i} className="border-rule-soft" />
        }
        if (/^[-*] /m.test(trimmed)) {
          return (
            <ul key={i} className="space-y-1">
              {trimmed.split('\n').map((line, j) => (
                <li key={j} className="flex gap-2 text-[0.875rem] leading-relaxed">
                  <span
                    aria-hidden
                    className="bg-ink-faint mt-2 size-1 shrink-0 select-none"
                  />
                  <span>{inline(line.replace(/^[-*] /, ''))}</span>
                </li>
              ))}
            </ul>
          )
        }
        return (
          <p key={i} className="text-[0.875rem] leading-relaxed">
            {inline(trimmed)}
          </p>
        )
      })}
    </div>
  )
}

function Table({ block }: { block: string }) {
  const rows = block
    .split('\n')
    .filter((line) => line.trim().startsWith('|'))
    .filter((line) => !/^\|[\s:|-]+\|$/.test(line.trim()))
    .map((line) =>
      line
        .trim()
        .replace(/^\||\|$/g, '')
        .split('|')
        .map((cell) => cell.trim()),
    )
  if (rows.length === 0) return null
  const [head, ...body] = rows
  return (
    <div className="border-rule-soft overflow-x-auto border">
      <table className="w-full border-collapse text-[0.8125rem]">
        <thead>
          <tr className="bg-secondary">
            {head.map((cell, i) => (
              <th
                key={i}
                className="eyebrow border-rule-soft border-b px-3 py-2 text-left"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, i) => (
            <tr key={i} className="border-rule-soft border-b last:border-b-0">
              {row.map((cell, j) => (
                <td
                  key={j}
                  className={cn('px-3 py-2 align-top', j > 0 && 'numeric')}
                >
                  {inline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Bold and code only. Anything fancier is a distraction in a business doc. */
function inline(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold">
          {part.slice(2, -2)}
        </strong>
      )
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={i} className="bg-secondary px-1 py-0.5 font-mono text-[0.8em]">
          {part.slice(1, -1)}
        </code>
      )
    }
    return part
  })
}
