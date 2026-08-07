/**
 * The Bauhaus vocabulary.
 *
 * Circle, square, triangle — used the way the school used them: assigned to
 * meanings and then applied consistently, not scattered for decoration. Here a
 * shape carries state, so the interface still reads in greyscale, in print, and
 * to someone who can't separate the red from the yellow.
 *
 *   circle    working, live, evidenced
 *   square    idle, neutral, at rest
 *   triangle  flagged — a warning, an objection, something that needs you
 */

import { cn } from '@/lib/utils'

export type Shape = 'circle' | 'square' | 'triangle' | 'ring'
export type Tone = 'blue' | 'yellow' | 'red' | 'ink' | 'faint'

const TONE: Record<Tone, string> = {
  blue: 'text-blue',
  yellow: 'text-yellow',
  red: 'text-red',
  ink: 'text-ink',
  faint: 'text-ink-faint',
}

export function Mark({
  shape,
  tone = 'ink',
  live = false,
  className,
  style,
}: {
  shape: Shape
  tone?: Tone
  live?: boolean
  className?: string
  style?: React.CSSProperties
}) {
  const isTriangle = shape === 'triangle'
  return (
    <span
      aria-hidden
      className={cn(
        'mark',
        `mark-${shape}`,
        TONE[tone],
        live && 'pulse',
        // A triangle is drawn with borders, so it colours itself; the solid
        // shapes need the fill.
        !isTriangle && shape !== 'ring' && 'bg-current',
        shape === 'ring' && 'border-current',
        className,
      )}
      style={style}
    />
  )
}

/** The logo is the three marks in their fixed order, then the name. */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-center gap-2', className)}>
      <span className="flex items-center gap-[3px]" aria-hidden>
        <span className="mark mark-circle bg-blue size-2.5" />
        <span className="mark mark-square bg-yellow size-2.5" />
        <span className="mark mark-triangle text-red" />
      </span>
      <span className="font-display text-[1.0625rem] font-semibold lowercase tracking-[0.02em]">
        werkhaus
      </span>
    </span>
  )
}
