/**
 * What a business would earn, worked out from what it rests on.
 *
 * There is no revenue anywhere in the stored model — see ``MoneyModel`` in the
 * contract. Revenue is arithmetic over assumptions, done here, every time it is
 * shown. That is the whole safety property: a number nobody earned cannot be
 * saved as if somebody had, and every figure on screen can be traced back to a
 * marked assumption you can argue with.
 *
 * The model is deliberately the smallest one that can be wrong in a useful way:
 * a price, customers, how many arrive, how many leave, what serving one costs,
 * and what the month costs before anyone shows up. No cohorts, no funnel, no
 * blended CAC. A bigger model is not a better one when every input is a guess.
 */

export type Mark = 'sourced' | 'inferred' | 'assumption'
export type Unit = 'money' | 'count' | 'rate'

export interface Assumption {
  key: string
  label: string
  value: number
  unit: Unit
  confidence: Mark
  note?: string
}

/** The keys the projection multiplies, and what each one has to mean. */
export const KEYS = [
  'price',
  'customers',
  'new_customers',
  'churn',
  'variable_cost',
  'fixed_cost',
] as const

export type Key = (typeof KEYS)[number]

/** What a key is called when the model does not carry a label of its own. */
export const LABELS: Record<Key, string> = {
  price: 'what one customer pays a month',
  customers: 'customers at the end of month one',
  new_customers: 'customers arriving each month after',
  churn: 'the share of them who leave each month',
  variable_cost: 'what serving one customer costs a month',
  fixed_cost: 'what the month costs before any customers',
}

/** Without these two there is nothing to project at all. */
const REQUIRED: Key[] = ['price', 'customers']

export interface Month {
  month: number
  customers: number
  revenue: number
  costs: number
  /** Revenue less what it cost to serve it, before the fixed costs. */
  contribution: number
  profit: number
  cumulative: number
}

export interface Projection {
  months: Month[]
  /**
   * Keys nobody modelled. A missing key is *not* a zero: `churn` absent means
   * nobody worked out how many customers leave, and a curve drawn as though
   * none of them ever do should say so rather than look like an answer.
   */
  missing: Key[]
  /** The first month that pays for itself, if one does inside the horizon. */
  breakEven: number | null
  peak: number
}

function get(assumptions: Assumption[], key: Key): number | null {
  const found = assumptions.find((a) => a.key === key)
  return found ? Number(found.value) : null
}

export function project(
  assumptions: Assumption[],
  horizonMonths = 12,
): Projection {
  const missing = KEYS.filter((k) => get(assumptions, k) === null)
  const price = get(assumptions, 'price')
  const start = get(assumptions, 'customers')

  if (REQUIRED.some((k) => get(assumptions, k) === null) || price === null || start === null) {
    return { months: [], missing, breakEven: null, peak: 0 }
  }

  const arriving = get(assumptions, 'new_customers') ?? 0
  const churn = get(assumptions, 'churn') ?? 0
  const variable = get(assumptions, 'variable_cost') ?? 0
  const fixed = get(assumptions, 'fixed_cost') ?? 0

  const months: Month[] = []
  let customers = start
  let cumulative = 0
  let breakEven: number | null = null

  for (let m = 1; m <= horizonMonths; m++) {
    if (m > 1) customers = customers * (1 - churn) + arriving
    const revenue = customers * price
    const costs = customers * variable + fixed
    const profit = revenue - costs
    cumulative += profit
    if (breakEven === null && profit >= 0) breakEven = m
    months.push({
      month: m,
      customers,
      revenue,
      costs,
      contribution: customers * (price - variable),
      profit,
      cumulative,
    })
  }

  const peak = Math.max(...months.map((m) => Math.max(m.revenue, m.costs)))
  return { months, missing, breakEven, peak }
}

/**
 * Money, at the size a plate shows it: no decimals above ten unless the exact
 * figure is the point, which it is on a dial showing what somebody wrote down.
 */
export function amount(value: number, currency = 'EUR', cents = false) {
  const symbol = currency === 'EUR' ? '€' : currency === 'USD' ? '$' : `${currency} `
  const rounded =
    cents || Math.abs(value) < 10
      ? Math.round(value * 100) / 100
      : Math.round(value)
  const sign = rounded < 0 ? '−' : ''
  return `${sign}${symbol}${Math.abs(rounded).toLocaleString('en-IE', {
    minimumFractionDigits: cents && rounded % 1 !== 0 ? 2 : 0,
    maximumFractionDigits: 2,
  })}`
}
