/**
 * The mark vocabulary.
 *
 * Four shapes, each assigned a meaning and then applied consistently rather
 * than scattered for decoration. A shape carries the state, so the interface
 * still reads in greyscale, in print, and to someone who cannot separate the
 * blue from the amber.
 *
 *   square    a fact, at rest — filled in the evidence blue when sourced,
 *             plain ink when merely inferred
 *   ring      hollow: an assumption, something nobody has checked
 *   circle    working, live
 *   triangle  flagged — an objection, something that needs you
 *
 * The hollow/filled distinction is the load-bearing one. A number leaving this
 * app — copied into a deck, printed, screenshotted — has to carry whether it
 * was verified, and colour alone does not survive any of those journeys.
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

/**
 * The logo.
 *
 * A serial, the way the reference numbers its plates, then the name. Werkhaus
 * files things — shifts, documents, objections — and a filing number is the
 * truest possible mark for it. Set in the pixel face so it reads as a stamped
 * identifier rather than a piece of branding.
 */
export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('flex items-baseline gap-2', className)}>
      <span aria-hidden className="mark mark-square bg-blue translate-y-[-1px]" />
      <span className="font-mono text-[0.9375rem] tracking-[0.16em] uppercase">
        werkhaus
      </span>
    </span>
  )
}
