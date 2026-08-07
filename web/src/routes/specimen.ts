/**
 * The example report shown on the front page.
 *
 * Same content the stub produces, kept here so the page can play back a finished
 * shift rather than describe one. Labelled as an example on the page: we are
 * pre-launch and it is not a customer's company.
 */

export type Mark = 'sourced' | 'inferred' | 'assumption'

export const HEADER = {
  company: 'Northwind Ceramics',
  shift: 1,
  minutes: 12,
  cost: '6.84',
  idea:
    'A monthly subscription box for hand-thrown ceramics. One nice object a ' +
    'month, made by a real potter, sent to people who live in small flats and ' +
    "don't want more clutter.",
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
  head: ['Box', 'Price / mo', 'What arrives', 'Names the maker?'],
  rows: [
    ['Pottery Box', '£18', '2-3 small pieces', 'No'],
    ['Clay Collective', '£29', '1 piece + a zine', 'Yes'],
    ['The Pottery Box', '£32', '1-2 pieces, seasonal', 'Yes'],
    ['Handmade Home', '£24', 'mixed homeware', 'No'],
    ['Northern Clay', '£45', '1 large piece, quarterly', 'Yes'],
    ['Muddy Hands', '£22', "beginner's kit", 'n/a'],
  ],
  sources: [
    'pottery-box.co.uk/pricing',
    'claycollective.uk/subscribe',
    'thepotterybox.com/plans',
  ],
  found:
    'Every box at £29 or above names the potter. None below £25 does. Nobody ' +
    'sends exactly one object.',
  caveat:
    'Two more appear in search results but their sites are dead. Excluded ' +
    'rather than guessed at.',
}

export const POSITIONING = {
  title: 'Price at £29/mo, not £9',
  why:
    'Every box in the table that names its maker sits at £29 or above, and ' +
    'naming the maker is the whole pitch.',
  instead: [
    '£9/mo, which sits below the boxes that send unbranded seconds',
    '£45/mo quarterly, which Northern Clay already owns and which kills the habit',
  ],
  contested:
    'Reasoned from competitor pricing, not from any willingness-to-pay ' +
    'evidence. Defensible, not validated.',
}

/** The whole point of this panel is that most of the rows are guesses. */
export const ECONOMICS = {
  head: ['Line', 'Per box', 'Where it came from'],
  rows: [
    ['Price', '£29.00', 'Decided this shift', false],
    ['Potter cost', '£11.00', 'Typical wholesale, roughly 40% of retail', true],
    ['Packaging', '£2.20', 'Protective packing for one piece', true],
    ['UK shipping', '£4.80', 'Tracked, ceramics-safe, no quote yet', true],
    ['Payments', '£1.15', "Stripe's published pricing", false],
  ] as [string, string, string, boolean][],
  total: ['Contribution', '£9.85'],
  gap: 'Breakage is not modelled at all. One replacement in twenty removes about £1.45 a box.',
}

export const SITE = {
  url: 'northwind-ceramics.werkhaus.site',
  headline: "One pot a month. You'll know who made it.",
  sub: 'Every month we send a single hand-thrown piece from one potter, with their name on it.',
  checks: [
    'Builds clean',
    'Renders down to 360px',
    'Waitlist round-trips a real email address',
  ],
}

export const OBJECTIONS = [
  {
    severity: 'serious' as const,
    against: 'positioning',
    about: 'positioning.md',
    text:
      'The £29 price is defended entirely with competitor pricing. Not one ' +
      'person in the target audience has been asked what they would pay.',
    settled:
      'Five conversations with people who match the audience, asking what they ' +
      'currently spend on objects like this.',
  },
  {
    severity: 'serious' as const,
    against: 'economics',
    about: 'unit-economics.md',
    text:
      'Contribution of £9.85 rests on three cost lines that are guesses, and ' +
      'breakage is missing from the model entirely.',
    settled: 'One quote from a potter and one from a courier.',
  },
  {
    severity: 'noted' as const,
    against: 'research',
    about: 'channels.md',
    text:
      'The speciality-coffee overlap is labelled a hunch, which is honest, but ' +
      'it is also the cheapest thing on the list to check and nobody was asked ' +
      'to check it.',
    settled: 'An afternoon in one coffee forum.',
  },
]

export const VERDICT = {
  percent: 64,
  headline:
    'Positioning and price are settled and the page is live. Nobody has said ' +
    'they would buy it.',
  missing: [
    'No evidence any real person will pay £29',
    'The cost model has no supplier quotes behind it',
    'Zero waitlist signups so far',
  ],
}
