import { useMemo, useState } from 'react'
import {
  KEYS,
  LABELS,
  amount,
  project,
  type Assumption,
  type Key,
} from '@/lib/finance'
import { cn } from '@/lib/utils'

/**
 * The money model, drawn — and pushable.
 *
 * One component for both surfaces, so the front page cannot show a nicer
 * version of this than the studio does. The studio passes what an employee
 * filed; the front page passes the worked example.
 *
 * Two decisions carry the whole thing:
 *
 * The curve is drawn **hollow**, in the same register as an assumption mark
 * everywhere else in the product, because that is what it is. A projection
 * drawn as a solid confident bar chart is the exact artifact that gets pasted
 * into a deck and read as a fact six weeks later.
 *
 * And every input is a control. A number you can move is a number you can
 * argue with, and watching the curve fall when you put churn into a model that
 * did not have any is worth more than a paragraph explaining that it should.
 * Moving them changes nothing on disk — this is you testing their homework,
 * not you doing it.
 */

export function MoneyPlate({
  assumptions,
  currency = 'EUR',
  horizonMonths = 12,
  className,
}: {
  assumptions: Assumption[]
  currency?: string
  horizonMonths?: number
  className?: string
}) {
  // What-if overrides, by key. Empty until the reader moves something.
  const [what, setWhat] = useState<Partial<Record<Key, number>>>({})
  const touched = Object.keys(what).length > 0

  const live: Assumption[] = useMemo(() => {
    const byKey = new Map(assumptions.map((a) => [a.key, a]))
    const out = assumptions.map((a) =>
      what[a.key as Key] === undefined
        ? a
        : { ...a, value: what[a.key as Key] as number },
    )
    // A key nobody modelled becomes a real assumption the moment the reader
    // supplies one — and it is marked as theirs, not as the team's.
    for (const key of KEYS) {
      if (byKey.has(key) || what[key] === undefined) continue
      out.push({
        key,
        label: LABELS[key],
        value: what[key] as number,
        unit: key === 'churn' ? 'rate' : key.includes('cost') || key === 'price' ? 'money' : 'count',
        confidence: 'assumption',
        note: 'you added this',
      })
    }
    return out
  }, [assumptions, what])

  const shown = project(live, horizonMonths)
  const filed = project(assumptions, horizonMonths)
  const last = shown.months[shown.months.length - 1]

  if (shown.months.length === 0) {
    return (
      <div className={cn('panel p-6', className)}>
        <p className="display text-[1.125rem] leading-snug">
          Not enough of a model to project.
        </p>
        <p className="text-ink-soft mt-2 max-w-[46ch] text-[0.875rem] leading-relaxed">
          A projection needs at least a price and a number of customers. Missing:{' '}
          {shown.missing.join(', ')}.
        </p>
      </div>
    )
  }

  return (
    <div className={cn('panel', className)}>
      <div className="border-rule-soft flex flex-wrap items-end justify-between gap-x-8 gap-y-4 border-b px-5 py-4 sm:px-6">
        <div>
          <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
            month {horizonMonths}, if every assumption holds
          </p>
          <p className="numeric mt-1 text-[2.25rem] leading-none">
            {amount(last.revenue, currency)}
            <span className="text-ink-faint ml-2 font-mono text-[0.75rem]">a month</span>
          </p>
        </div>
        <dl className="flex gap-8">
          <div>
            <dt className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
              pays for itself
            </dt>
            <dd className="numeric mt-1 text-[1.125rem] leading-none">
              {shown.breakEven ? `month ${shown.breakEven}` : 'not yet'}
            </dd>
          </div>
          <div>
            <dt className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
              customers by then
            </dt>
            <dd className="numeric mt-1 text-[1.125rem] leading-none">
              {Math.round(last.customers)}
            </dd>
          </div>
        </dl>
      </div>

      <Chart projection={shown} currency={currency} filedPeak={filed.peak} />

      <div className="border-rule-soft grid border-t lg:grid-cols-2">
        <div className="border-rule-soft border-b p-5 lg:border-r lg:border-b-0 sm:p-6">
          <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
            what it rests on · move one
          </p>
          <ul className="mt-4 space-y-4">
            {assumptions.map((a) => (
              <Dial
                key={a.key}
                assumption={a}
                currency={currency}
                value={what[a.key as Key] ?? a.value}
                onChange={(v) => setWhat((w) => ({ ...w, [a.key]: v }))}
              />
            ))}
          </ul>
        </div>

        <div className="p-5 sm:p-6">
          <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
            holes in it
          </p>
          {filed.missing.length === 0 ? (
            <p className="text-ink-soft mt-3 text-[0.875rem]">
              Every number the projection needs is in the model.
            </p>
          ) : (
            <ul className="mt-4 space-y-4">
              {filed.missing.map((key) => (
                <Hole
                  key={key}
                  hole={key}
                  currency={currency}
                  value={what[key]}
                  onChange={(v) => setWhat((w) => ({ ...w, [key]: v }))}
                />
              ))}
            </ul>
          )}

          {touched && (
            <button
              type="button"
              onClick={() => setWhat({})}
              className="text-link mt-6 font-mono text-[0.6875rem] underline"
            >
              put it back the way they filed it
            </button>
          )}
        </div>
      </div>

      <p className="border-rule-soft text-ink-faint border-t px-5 py-3 font-mono text-[0.625rem] leading-relaxed sm:px-6">
        drawn hollow because none of it has happened · nothing you move here is
        saved
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------- chart */

const W = 720
const H = 210
const PAD = 14

/**
 * Revenue as hollow bars, what it costs as a solid line over them.
 *
 * The scale is held to the *filed* model's peak while the reader pushes the
 * dials, so the curve visibly rises and falls instead of the axis silently
 * rescaling under it — a chart that always fills its box shows no change at
 * all, which is the most common way a slider lies.
 */
function Chart({
  projection,
  currency,
  filedPeak,
}: {
  projection: ReturnType<typeof project>
  currency: string
  filedPeak: number
}) {
  const top = Math.max(projection.peak, filedPeak) * 1.08 || 1
  const n = projection.months.length
  const step = (W - PAD * 2) / n
  const barW = step * 0.56
  const y = (v: number) => H - PAD - (Math.max(0, v) / top) * (H - PAD * 2)

  const costLine = projection.months
    .map((m, i) => `${PAD + step * i + step / 2},${y(m.costs)}`)
    .join(' ')

  return (
    <div className="px-5 pt-5 sm:px-6">
      <div className="flex items-baseline justify-between">
        <span className="text-ink-faint font-mono text-[0.625rem]">
          {amount(top, currency)}
        </span>
        <span className="text-ink-faint font-mono text-[0.625rem] tracking-[0.08em] uppercase">
          revenue, hollow · what it costs, solid
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} className="mt-1 w-full" role="img"
        aria-label={`Projected revenue over ${n} months, reaching ${amount(
          projection.months[n - 1].revenue, currency,
        )} a month.`}>
        {projection.breakEven && (
          <g>
            <line
              x1={PAD + step * (projection.breakEven - 1) + step / 2}
              x2={PAD + step * (projection.breakEven - 1) + step / 2}
              y1={PAD - 6}
              y2={H - PAD}
              stroke="var(--rule-soft)"
              strokeWidth={1}
            />
            <text
              x={PAD + step * (projection.breakEven - 1) + step / 2 + 5}
              y={PAD}
              className="fill-ink-faint font-mono"
              fontSize={10}
            >
              pays for itself
            </text>
          </g>
        )}

        {projection.months.map((m, i) => (
          <rect
            key={m.month}
            x={PAD + step * i + (step - barW) / 2}
            y={y(m.revenue)}
            width={barW}
            height={Math.max(1, H - PAD - y(m.revenue))}
            fill="none"
            stroke="var(--ink)"
            strokeWidth={1}
          />
        ))}

        <polyline
          points={costLine}
          fill="none"
          stroke="var(--ink-soft)"
          strokeWidth={1.75}
        />

        <line
          x1={PAD}
          x2={W - PAD}
          y1={H - PAD}
          y2={H - PAD}
          stroke="var(--rule)"
          strokeWidth={1}
        />
      </svg>

      <div className="text-ink-faint mt-1 flex justify-between font-mono text-[0.625rem]">
        <span>month 1</span>
        <span>month {n}</span>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------- dials */

function markClass(mark: string) {
  if (mark === 'assumption') return 'mark mark-ring border-assumption !size-2'
  if (mark === 'sourced') return 'mark mark-square bg-sourced !size-2'
  return 'mark mark-square bg-inferred !size-2'
}

/** The span a number is allowed to move over, from the number itself. */
function span(a: { unit: string; value: number }): [number, number, number] {
  if (a.unit === 'rate') return [0, 0.3, 0.005]
  if (a.unit === 'count') return [0, Math.max(10, Math.ceil(a.value * 4)), 1]
  return [0, Math.max(10, Math.ceil(a.value * 3)), a.value < 10 ? 0.05 : 1]
}

function show(value: number, unit: string, currency: string) {
  if (unit === 'rate') return `${(value * 100).toFixed(1)}%`
  if (unit === 'count') return String(Math.round(value))
  // Cents matter on a dial in a way they do not in a headline: €10.55 is the
  // number somebody wrote down, and rounding it to €11 here would quietly
  // disagree with the €18.45 contribution the documents quote.
  return amount(value, currency, value % 1 !== 0)
}

function Dial({
  assumption,
  value,
  currency,
  onChange,
}: {
  assumption: Assumption
  value: number
  currency: string
  onChange: (v: number) => void
}) {
  const [min, max, stepSize] = span({ unit: assumption.unit, value: assumption.value })
  const moved = value !== assumption.value
  return (
    <li>
      <label className="flex items-baseline gap-2">
        <span aria-hidden className={cn(markClass(assumption.confidence), 'translate-y-[1px]')} />
        <span className="text-ink-soft min-w-0 flex-1 text-[0.8125rem] leading-snug">
          {assumption.label}
        </span>
        <span
          className={cn(
            'numeric shrink-0 text-[0.875rem]',
            moved && 'text-link',
          )}
        >
          {show(value, assumption.unit, currency)}
        </span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={stepSize}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={assumption.label}
        className="accent-ink focus-visible:ring-ring mt-1.5 w-full focus-visible:ring-2 focus-visible:outline-none"
      />
      {assumption.note && (
        <p className="text-ink-faint mt-0.5 font-mono text-[0.625rem] leading-relaxed">
          {assumption.note}
        </p>
      )}
    </li>
  )
}

/**
 * A number nobody modelled.
 *
 * It sits at zero and says so, rather than being folded into the curve as if
 * somebody had decided it was zero. Supplying one is the reader's own
 * assumption and is marked as theirs.
 */
function Hole({
  hole,
  value,
  currency,
  onChange,
}: {
  hole: Key
  value: number | undefined
  currency: string
  onChange: (v: number) => void
}) {
  const unit: string = hole === 'churn' ? 'rate' : hole.includes('cost') || hole === 'price' ? 'money' : 'count'
  const [min, max, stepSize] = span({ unit, value: value ?? (unit === 'rate' ? 0.06 : 100) })
  return (
    <li>
      <label className="flex items-baseline gap-2">
        <span aria-hidden className="mark mark-ring border-ink-faint !size-2 translate-y-[1px]" />
        <span className="text-ink-soft min-w-0 flex-1 text-[0.8125rem] leading-snug">
          {LABELS[hole]}
        </span>
        <span className={cn('numeric shrink-0 text-[0.875rem]', value !== undefined && 'text-link')}>
          {value === undefined ? 'not modelled' : show(value, unit, currency)}
        </span>
      </label>
      <input
        type="range"
        min={min}
        max={max}
        step={stepSize}
        value={value ?? 0}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={`${LABELS[hole]} — not modelled`}
        className="accent-ink focus-visible:ring-ring mt-1.5 w-full focus-visible:ring-2 focus-visible:outline-none"
      />
      <p className="text-ink-faint mt-0.5 font-mono text-[0.625rem] leading-relaxed">
        {value === undefined
          ? 'nobody put a number here. the curve above assumes none of it happens.'
          : 'your number, not theirs'}
      </p>
    </li>
  )
}
