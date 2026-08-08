/**
 * The example report shown on the front page.
 *
 * Same content the stub produces, kept here so the page can play back a finished
 * shift rather than describe one. Labelled as an example on the page: we are
 * pre-launch and it is not a customer's company.
 */

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
  /** Seconds this panel holds before the replay moves on. */
  dwell: number
}

export const PANELS: Panel[] = [
  { id: 'research', file: 'market-research.md', by: 'maya', mark: 'sourced', dwell: 11 },
  { id: 'positioning', file: 'positioning.md', by: 'ines', mark: 'inferred', dwell: 9 },
  { id: 'economics', file: 'unit-economics.md', by: 'nia', mark: 'assumption', dwell: 11 },
  { id: 'site', file: 'site/', by: 'kit', mark: 'sourced', dwell: 8 },
  { id: 'vera', file: '3 objections', by: 'vera', mark: null, dwell: 14 },
]

export const RESEARCH = {
  head: ['App', 'Price / mo', 'Built for', 'Plans a route?'],
  rows: [
    ['Pawfect Books', '£12', 'salons with a front desk', 'No'],
    ['Groomly', '£29', 'salons, multi-chair', 'No'],
    ['Kennel Desk', '£39', 'kennels and daycare', 'No'],
    ['MoeGo', '£49', 'salons and mobile', 'Partly'],
    ['Time To Pet', '£45', 'dog walkers', 'Yes'],
    ['Setmore', '£0-£9', 'anyone with appointments', 'No'],
  ],
  sources: [
    'moego.pet/pricing',
    'timetopet.com/pricing',
    'groomly.app/plans',
  ],
  found:
    'Nine apps priced £12 to £49. Only two think about travel between jobs, ' +
    'and neither of those is built for grooming.',
  caveat:
    'Two more appear in search results but publish no price. Excluded rather ' +
    'than guessed at.',
}

export const POSITIONING = {
  title: 'Price at £29/mo, and sell the route',
  why:
    'Every app that plans a route sits at £45 or above and is built for ' +
    'somebody else. The gap is grooming-shaped, and £29 sits under it.',
  instead: [
    '£12/mo, which competes with diary apps a groomer already tolerates',
    '£49/mo, which MoeGo owns and defends with a decade of features',
  ],
  contested:
    'Reasoned from rival pricing, not from any willingness-to-pay evidence. ' +
    'Defensible, not validated.',
}

/** The whole point of this panel is that most of the rows are guesses. */
export const ECONOMICS = {
  head: ['Line', 'Per box', 'Where it came from'],
  rows: [
    ['Price', '£29.00', 'Decided this shift', false],
    ['Hosting and database', '£0.00', 'Inside the free tiers at this size', false],
    ['Texts for reminders', '£3.40', 'Roughly 85 jobs a month, one text each', true],
    ['Support', '£6.00', 'Fifteen minutes a customer a month', true],
    ['Payments', '£1.15', "Stripe's published pricing", false],
  ] as [string, string, string, boolean][],
  total: ['Contribution', '£18.45'],
  gap: 'Churn is not modelled at all. A groomer who leaves after two months never repays the first conversation.',
}

export const SITE = {
  url: 'groomer-rounds.netlify.app',
  headline: 'Your day, in the order the roads make sense.',
  sub: 'Bookings, routes and the evening-before reminder, without a single WhatsApp thread.',
  checks: [
    'Builds clean',
    'Renders down to 360px',
    'A signup writes a real row to your own database',
    'The confirmation email arrives',
    'A test card completes the checkout',
  ],
}

export const OBJECTIONS = [
  {
    severity: 'serious' as const,
    against: 'positioning',
    about: 'positioning.md',
    text:
      'The £29 price is defended entirely with rival pricing. Not one working ' +
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
      'Contribution of £18.45 rests on two cost lines that are guesses, and ' +
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

export const VERDICT = {
  percent: 94,
  headline:
    'It works end to end — signups land, emails send, a card goes through. ' +
    'Nobody has actually paid yet.',
  missing: [
    'No evidence any working groomer will pay £29',
    'Two cost lines are still guesses, and churn is unmodelled',
    'The checkout has only ever taken test cards',
  ],
}
