/**
 * The worked example the front page is built on.
 *
 * One fictional company, in one file, so the landing and the diagram cannot
 * drift apart. Labelled as an example wherever it appears: we are pre-launch
 * and it is nobody's real company.
 *
 * It stops at the documents on purpose. A shift does not leave a working site
 * yet — Kit is not built — and a landing page that shows one is the exact way
 * a product earns a reader who feels lied to.
 */

import type { Assumption } from '@/lib/finance'

export type Mark = 'sourced' | 'inferred' | 'assumption'

export const HEADER = {
  company: 'Booking Tool',
  shift: 3,
  minutes: 14,
  cost: '9.20',
  idea:
    'A booking tool for mobile dog groomers who run everything through ' +
    'WhatsApp. It plans the day as a route, not a list, and reminds the ' +
    'customer the evening before.',
}

export interface Panel {
  id: string
  file: string
  by: string
  mark: Mark | null
  /** One line on what is in it, as the page lists it. */
  what: string
}

export const PANELS: Panel[] = [
  {
    id: 'research',
    file: 'market-research.md',
    by: 'maya',
    mark: 'sourced',
    what: 'nine rival apps, €12 to €49, with the pages they came from',
  },
  {
    id: 'positioning',
    file: 'positioning.md',
    by: 'ines',
    mark: 'inferred',
    what: 'one price, one audience, and why not the other two',
  },
  {
    id: 'economics',
    file: 'unit-economics.md',
    by: 'nia',
    mark: 'assumption',
    what: 'contribution of €18.45, and which lines are guesses',
  },
  {
    id: 'channels',
    file: 'channels.md',
    by: 'rafa',
    mark: 'sourced',
    what: 'where mobile groomers already are',
  },
]

/**
 * The price list.
 *
 * Mirrors ``werkhaus/contract/plan.py``, which is where the engine reads it
 * from — the page is served as static files and has to be able to quote a price
 * with no API behind it. ``tests/contract/test_pricing.py`` reads this file and
 * fails if the two ever disagree, so "the site says one thing and the bill says
 * another" cannot happen quietly.
 */
export interface Tier {
  plan: string
  label: string
  /** Euros a month, billed monthly. Null is free, not "ask us". */
  price: number | null
  /** Euros for a year, paid once. Cheaper per month, and it is cash now. */
  year: number | null
  pitch: string
  /** What you get, in the order it is wanted. */
  gets: string[]
  /** The one that carries the offer. */
  featured?: boolean
}

export const PRICING: Tier[] = [
  {
    plan: 'free',
    label: 'Free',
    price: null,
    year: null,
    pitch: 'Enough to leave with a folder you can show someone.',
    gets: [
      '3 shifts to start, then one a week',
      'All four documents, every claim marked',
      "Vera's objections, same as everyone",
      'No card, ever, on this tier',
    ],
  },
  {
    plan: 'studio',
    label: 'Studio',
    price: 12,
    year: 96,
    pitch: 'A company you run every week, not a thing you tried once.',
    featured: true,
    gets: [
      '12 shifts a month — three a week',
      'Connect Stripe, and take an order',
      'Every autonomy setting, including unattended',
      'This price for as long as you stay',
    ],
  },
  {
    plan: 'pro',
    label: 'Pro',
    price: 29,
    year: 240,
    pitch: 'Your own key, your own model, no ceiling on shifts.',
    gets: [
      'Shifts are not counted',
      'Bring your own key — the model bill is yours, at cost',
      'Choose the model each employee thinks with',
      'Everything in Studio',
    ],
  },
]

/**
 * What the people we get compared to charge.
 *
 * Read off their own pages and docs rather than off the round-up articles,
 * which disagree with both vendors — the first draft of this table said Base44
 * cost $25 a month on the strength of one, and it does not.
 *
 * Lovable publishes both rates: Pro is $25 a month, $21 if paid yearly
 * (docs.lovable.dev/introduction/subscription-plans). Base44 prints only the
 * yearly rate, $16 a month for Starter, beside a stated 20% yearly discount
 * (base44.com/pricing); their month-to-month figure is that discount reversed,
 * which is arithmetic and is labelled as such on the page rather than quoted as
 * though we had read it.
 *
 * The table is not here to say we are cheaper. It is here to say we are cheaper
 * *and doing the other half of the job*, which is the only line that survives a
 * reader who already pays for one of them.
 */
export const RIVALS: {
  name: string
  /** Per month, billed monthly. */
  monthly: string
  /** Per month, billed yearly. */
  yearly: string
  does: string
  /** True where the monthly figure is derived from a published discount. */
  derived?: boolean
  ours?: boolean
}[] = [
  {
    name: 'Lovable',
    monthly: '$25',
    yearly: '$21',
    does: 'Builds the app. Their Pro plan.',
  },
  {
    name: 'Base44',
    monthly: '$20',
    yearly: '$16',
    does: 'Builds the app. Their Starter plan.',
    derived: true,
  },
  {
    name: 'Werkhaus',
    monthly: '\u20ac12',
    yearly: '\u20ac8',
    does: 'Works out whether to build it, and hands you the brief.',
    ours: true,
  },
]

export const RIVALS_CHECKED =
  'their own pricing pages, 13 august 2026 · base44 publishes a yearly rate and ' +
  'a 20% yearly discount, so their monthly figure is that discount reversed'

/**
 * Why the price is what it is, and what happens to it.
 *
 * Said out loud because the reader can see the product is not finished. The
 * offer only works if the reason it is cheap is the same reason to take it now.
 */
export const FOUNDING = {
  until: 'a shift ends with a live page',
  then: 29,
  /** Where a founding customer goes. Swap for a checkout when there is one. */
  contact: 'research@euroswarms.eu',
}

/** A line as it appears inside a document, carrying the mark it earned. */
export interface Line {
  mark: Mark | null
  text: string
}

/**
 * A page out of each document, for the miniatures on the front page.
 *
 * Short enough to set at eight point and still be read, and chosen so each
 * document shows the mark it is known for: research is nearly all sourced,
 * the money model is nearly all assumption, and you can see that from across
 * a room without reading a word.
 */
export const EXCERPTS: Record<string, Line[]> = {
  research: [
    { mark: null, text: 'Nine rivals, read this shift.' },
    { mark: 'sourced', text: 'Groomly charges €29 a month.' },
    { mark: 'sourced', text: 'Pawmap charges €39 and plans a route.' },
    { mark: 'sourced', text: 'Seven of the nine plan nothing.' },
    { mark: 'inferred', text: 'Route planning is the paid tier everywhere.' },
    { mark: 'sourced', text: 'None of them price under €12.' },
  ],
  positioning: [
    { mark: null, text: 'One audience, one price.' },
    { mark: 'inferred', text: '€29 is the price to beat.' },
    { mark: 'inferred', text: 'Sell to the one-van groomer, not the salon.' },
    { mark: 'assumption', text: 'They will switch for the route alone.' },
    { mark: 'inferred', text: 'Not the salons: they already have software.' },
  ],
  economics: [
    { mark: null, text: 'One page. Every guess labelled.' },
    { mark: 'assumption', text: 'Contribution of €18.45 a month.' },
    { mark: 'assumption', text: 'Support runs under fifteen minutes.' },
    { mark: 'sourced', text: 'Stripe takes 1.5% + €0.25.' },
    { mark: 'assumption', text: 'Churn is not in the model at all.' },
  ],
  channels: [
    { mark: null, text: 'Where they already are.' },
    { mark: 'sourced', text: 'Two forums, 40k posts between them.' },
    { mark: 'sourced', text: 'Four grooming trade shows a year in the EU.' },
    { mark: 'assumption', text: 'The forum overlap is a hunch.' },
    { mark: 'inferred', text: 'Facebook groups beat cold email here.' },
  ],
}

/**
 * The money model Nia filed in that shift.
 *
 * Same numbers as `unit-economics.md` above, in the structured form the studio
 * stores them in: €29 less €10.55 to serve is the €18.45 contribution the
 * documents quote, so the plate and the page cannot drift.
 *
 * Churn is deliberately absent. It is the hole Vera files a serious objection
 * about, and a projection drawn as though nobody ever leaves is exactly the
 * kind of quietly optimistic chart this product exists to catch — so the page
 * shows it as a hole and lets the reader put a number in it.
 */
export const MONEY: { currency: string; assumptions: Assumption[] } = {
  currency: 'EUR',
  assumptions: [
    {
      key: 'price',
      label: 'what one customer pays a month',
      value: 29,
      unit: 'money',
      confidence: 'inferred',
      note: 'reasoned from the four rivals in the table',
    },
    {
      key: 'customers',
      label: 'customers at the end of month one',
      value: 12,
      unit: 'count',
      confidence: 'assumption',
      note: 'nobody has been asked. this is a guess and it says so',
    },
    {
      key: 'new_customers',
      label: 'customers arriving each month after',
      value: 9,
      unit: 'count',
      confidence: 'assumption',
      note: 'from the two forums, at a rate nobody has tested',
    },
    {
      key: 'variable_cost',
      label: 'what serving one customer costs a month',
      value: 10.55,
      unit: 'money',
      confidence: 'assumption',
      note: 'support at under fifteen minutes, which is a guess',
    },
    {
      key: 'fixed_cost',
      label: 'what the month costs before any customers',
      value: 450,
      unit: 'money',
      confidence: 'assumption',
      note: 'hosting, the maps bill, and a phone number',
    },
  ],
}

/**
 * When each number went in, in minutes into the shift.
 *
 * A money model is not filed in one keystroke — it is assembled, one defensible
 * number at a time, and the projection is worth nothing until the first two are
 * in. The replay shows that assembly, so the figure that ends up on screen has
 * been watched being built rather than announced.
 */
export const MONEY_AT: Record<string, number> = {
  price: 8.6,
  customers: 9.1,
  new_customers: 9.6,
  variable_cost: 10.2,
  fixed_cost: 10.8,
}

/**
 * The same shift, as it happened, minute by minute.
 *
 * The front page plays this back once. It exists so a reader can watch what a
 * shift *is* — pages opened, documents landing, money going up — instead of
 * being told. Times are minutes into the shift and the spend column ends on
 * ``HEADER.cost``, so the replay and the numbers beside it cannot disagree.
 */
export interface Beat {
  at: number
  phase: 'planning' | 'working' | 'closing'
  /** What the studio said at that moment. */
  said: string
  /** The page that was opened, if one was. */
  read?: string
  /** The document that landed, if one did. */
  filed?: string
  /** Spent by this point, in dollars. */
  spent: number
}

export const REEL: Beat[] = [
  { at: 0, phase: 'planning', said: 'Ada put two things on the agenda.', spent: 0 },
  {
    at: 1.3,
    phase: 'working',
    said: 'Maya opened a rival pricing page.',
    read: 'groomly.app/plans',
    spent: 0.9,
  },
  {
    at: 2.6,
    phase: 'working',
    said: 'And another one.',
    read: 'pawmap.io/pricing',
    spent: 1.8,
  },
  {
    at: 4.2,
    phase: 'working',
    said: 'Maya filed the market overview.',
    filed: 'research',
    spent: 3.1,
  },
  {
    at: 6.4,
    phase: 'working',
    said: 'Ines committed to one price, not a menu.',
    spent: 4.2,
  },
  { at: 7.9, phase: 'working', said: 'Positioning filed.', filed: 'positioning', spent: 5.1 },
  { at: 9.6, phase: 'working', said: 'Nia built the money model.', spent: 6.3 },
  {
    at: 10.8,
    phase: 'working',
    said: 'Every guess in it is labelled.',
    filed: 'economics',
    spent: 7.1,
  },
  { at: 12.2, phase: 'working', said: 'Rafa filed where they already are.', filed: 'channels', spent: 8.1 },
  { at: 13.2, phase: 'closing', said: 'Vera started pulling it apart.', spent: 8.8 },
  { at: 14, phase: 'closing', said: 'Three objections filed. Shift closed.', spent: 9.2 },
]

export const OBJECTIONS = [
  {
    severity: 'serious' as const,
    against: 'positioning',
    about: 'positioning.md',
    text:
      'The €29 price is defended entirely with rival pricing. Not one working ' +
      'groomer has been asked what they would pay.',
    settled:
      'Five conversations with mobile groomers, asking what they pay today and ' +
      'what they would drop for this.',
  },
  {
    severity: 'serious' as const,
    against: 'economics',
    about: 'unit-economics.md',
    text:
      'Contribution of €18.45 rests on two cost lines that are guesses, and ' +
      'churn is missing from the model entirely.',
    settled: 'One month of real usage from three groomers.',
  },
  {
    severity: 'noted' as const,
    against: 'research',
    about: 'channels.md',
    text:
      'The grooming-forum overlap is labelled a hunch, which is honest, but it ' +
      'is also the cheapest thing on the list to check and nobody was asked to ' +
      'check it.',
    settled: 'An afternoon in one grooming forum.',
  },
]

/**
 * The same claim under each mark, for the page that explains them.
 *
 * Here rather than in the component because it is the same fictional company
 * as everything else in this file, down to Groomly's €29 — and two copies of
 * one example is how they drift apart.
 */
export const MARK_EXAMPLES: { mark: Mark; claim: string; behind: string }[] = [
  {
    mark: 'sourced',
    claim: 'Groomly charges €29 a month.',
    behind: 'from groomly.app/plans, opened during the shift',
  },
  {
    mark: 'inferred',
    claim: '€29 is the price to beat.',
    behind: 'reasoned from the four rivals in the table',
  },
  {
    mark: 'assumption',
    claim: 'Groomers will pay for route planning.',
    behind: 'nobody has been asked. this is a guess and it says so',
  },
]
