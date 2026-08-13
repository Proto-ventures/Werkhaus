import { EXCERPTS, PANELS } from '@/routes/specimen'
import { cn } from '@/lib/utils'

/**
 * The four documents, as objects rather than as a list of filenames.
 *
 * A filename in a row of text is a promise; a page you can see the inside of is
 * evidence. Each one shows the marks it actually carries, so the difference
 * between the research and the money model is visible from across a room —
 * research is nearly all filled squares, the money model is nearly all hollow
 * rings, and that is the honest shape of a shift rather than a claim about it.
 *
 * They sit at slightly different angles because four identical rectangles read
 * as a chart. Hovering straightens and lifts one, which is the only motion
 * here and is started by the reader.
 */

/** A degree or two each, alternating. Enough to read as paper, not as a fan. */
const TILT = [-1.6, 1.1, -0.9, 1.8]

function markClass(mark: string | null) {
  if (mark === 'assumption') return 'mark mark-ring border-assumption'
  if (mark === 'sourced') return 'mark mark-square bg-sourced'
  return 'mark mark-square bg-inferred'
}

export function Papers({ className }: { className?: string }) {
  return (
    <ul className={cn('grid grid-cols-2 gap-4 sm:gap-5 lg:grid-cols-4', className)}>
      {PANELS.map((panel, i) => {
        const lines = EXCERPTS[panel.id] ?? []
        const [title, ...rest] = lines
        return (
          <li
            key={panel.id}
            className="bg-panel border-rule flex flex-col border p-3 transition-transform duration-500 ease-[cubic-bezier(0.22,1,0.36,1)] hover:-translate-y-2 hover:rotate-0 sm:p-4"
            style={{
              transform: `rotate(${TILT[i % TILT.length]}deg)`,
              boxShadow: '0 14px 30px -22px rgb(0 0 0 / 0.45)',
            }}
          >
            {/* The filename is the claim being made — that this is an ordinary
                file in a folder you own — so it wraps rather than truncates.
                A cut-off `market-researc…` proves nothing. */}
            <div className="border-rule-soft flex flex-wrap items-baseline gap-x-2 border-b pb-2">
              <span className="font-mono text-[0.625rem] sm:text-[0.6875rem]">
                {panel.file}
              </span>
              <span className="text-ink-faint ml-auto font-mono text-[0.625rem] tracking-[0.08em] uppercase">
                {panel.by}
              </span>
            </div>

            <p className="display mt-3 text-[0.9375rem] leading-tight">{title?.text}</p>

            <ul className="mt-3 space-y-[7px]">
              {rest.map((line) => (
                <li key={line.text} className="flex items-baseline gap-2">
                  <span
                    aria-hidden
                    className={cn(markClass(line.mark), '!size-2 translate-y-[1px]')}
                  />
                  <span className="text-ink-soft text-[0.75rem] leading-[1.45]">
                    {line.text}
                  </span>
                </li>
              ))}
            </ul>

            <p className="text-ink-faint mt-auto pt-4 font-mono text-[0.625rem]">
              {panel.what}
            </p>
          </li>
        )
      })}
    </ul>
  )
}
