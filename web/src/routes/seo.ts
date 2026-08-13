/**
 * The pages that answer one question each: is *this* worth building?
 *
 * Programmatic, in the sense that the routes, the head tags, the sitemap and
 * the prerendered HTML are all generated from this one list. Not programmatic
 * in the sense the phrase usually means — there is no template being spun over
 * a keyword dump. Every entry carries specifics somebody had to know: who the
 * buyer actually is, the three things a shift would go and check first, and the
 * one number that decides it. A page that could be produced by swapping a noun
 * is a doorway page, it reads as one, and it is the same fiction problem this
 * product exists to refuse — the engine that replayed scripted shifts was
 * deleted for it.
 *
 * So the list stays short enough to be written rather than generated, and long
 * enough to be worth generating from. Adding one means writing four sentences
 * that are true about that trade, not adding a row.
 *
 * `tests/contract/test_seo.py` fails on a duplicate slug, a duplicate or
 * over-long title, a missing description, or a page whose checks are shared
 * with another page — which is what a spun template looks like from the outside.
 */

export interface Guide {
  /** The URL: /for/<slug>. Stable — changing one drops its ranking. */
  slug: string
  /** <title>. Under 60 characters or it is truncated in the result. */
  title: string
  /** <meta name="description">. 110-160 characters. */
  description: string
  /** The heading on the page itself, which need not be the title tag. */
  h1: string
  /** Who is actually being sold to. Not "small businesses". */
  audience: string
  /**
   * The three things a shift opens first for this trade. Specific to it —
   * the rivals a dog groomer has are not the rivals a physio has, and a page
   * that pretends otherwise is the doorway page this list refuses to be.
   */
  checks: [string, string, string]
  /** The number the whole thing turns on, phrased as the question it answers. */
  money: string
  /** What the box is prefilled with when they arrive from here. */
  idea: string
}

export const GUIDES: Guide[] = [
  {
    slug: 'mobile-dog-grooming-booking',
    title: 'Is a dog grooming booking app worth building?',
    description:
      'What mobile groomers already pay for, what those apps charge, and the number that decides whether a booking tool is worth building. One shift, four documents.',
    h1: 'A booking tool for mobile dog groomers.',
    audience: 'the one-van groomer running the day out of WhatsApp',
    checks: [
      'What the incumbent grooming apps charge, and which of them plan a route rather than list appointments',
      'Whether groomers pay per van or per appointment, because the two price the same product very differently',
      'How many of them are already in the two big grooming forums, and what they complain about there',
    ],
    money: 'What is left after card fees on a €29 subscription, once support is honest about how long it takes?',
    idea: 'A booking tool for mobile dog groomers who run everything through WhatsApp. It plans the day as a route, not a list.',
  },
  {
    slug: 'subscription-box',
    title: 'Is a subscription box worth building?',
    description:
      'Boxes die on shipping and churn, not on taste. What the shelf already costs, what the incumbents charge, and whether the second month pays for the first.',
    h1: 'A subscription box, and whether the second month pays for the first.',
    audience: 'a maker with one product and a mailing list',
    checks: [
      'What comparable boxes charge and, more usefully, what they charge for shipping separately',
      'Whether the category is already served by a marketplace that would take the discovery half of the business',
      'What the published churn looks like in the categories that talk about it publicly',
    ],
    money: 'Does the contribution on month two cover the acquisition cost of month one, or does the box need a third?',
    idea: 'A monthly subscription box for hand-thrown ceramics, one object a month from a named potter.',
  },
  {
    slug: 'zero-waste-refill-delivery',
    title: 'Is a refill delivery service worth building?',
    description:
      'Refill businesses live or die on the drop density of one postcode. What the route costs, who is already delivering there, and the number that decides it.',
    h1: 'Refills, delivered — and whether one postcode carries it.',
    audience: 'someone with a cargo bike and one neighbourhood in mind',
    checks: [
      'Who already delivers groceries in that postcode and whether refills are a line on their van already',
      'What the wholesale price of the three highest-volume products is, since the margin is set upstream',
      'Whether the council or the landlord has anything to say about a collection point',
    ],
    money: 'How many drops per hour does the round need before the bike pays for the hour?',
    idea: 'A refill service for cleaning products, delivered by cargo bike within one postcode.',
  },
  {
    slug: 'personal-trainer-scheduling',
    title: 'Is a personal trainer booking app worth building?',
    description:
      'Trainers already pay for two apps and use neither fully. What those cost, where the switching pain actually is, and whether a third is worth building.',
    h1: 'Scheduling and payments for personal trainers.',
    audience: 'the self-employed trainer with forty regulars and no front desk',
    checks: [
      'What the incumbent trainer apps charge, and which of them take a cut of the session as well as a subscription',
      'Whether the gyms they rent from already impose a booking system, which decides whether this is even installable',
      'How they take money today — because a tool that does not replace the payment step replaces nothing',
    ],
    money: 'Does the fee survive being compared to a percentage cut the trainer already resents paying?',
    idea: 'A scheduling and payments app for self-employed personal trainers who rent space in other gyms.',
  },
  {
    slug: 'independent-cafe-loyalty',
    title: 'Is a café loyalty app worth building?',
    description:
      'A paper card costs nothing and never fails. What loyalty apps charge cafés, what the tills already do, and whether an app clears that bar.',
    h1: 'Loyalty for independent cafés, against a paper card that works.',
    audience: 'one or two sites, an owner who is also on the machine',
    checks: [
      'What the till they already own does for loyalty, because that is the real incumbent rather than another app',
      'What the loyalty platforms charge per site per month, and whether they lock the customer list',
      'Whether the card schemes in this market allow the identification step the scheme depends on',
    ],
    money: 'What does one extra visit a month per customer have to be worth before the subscription is cheaper than the coffee it gives away?',
    idea: 'A loyalty app for independent cafés that works from the card the customer already taps.',
  },
  {
    slug: 'private-tutor-booking',
    title: 'Is a tutoring booking platform worth building?',
    description:
      'Tutoring marketplaces take a fifth of every lesson. What they charge, what tutors do to avoid it, and whether a tool that does not take a cut can be sold.',
    h1: 'Booking and payment for private tutors.',
    audience: 'the tutor with a full book who resents the marketplace commission',
    checks: [
      'What the marketplaces take per lesson, which is the price this is really being compared against',
      'Whether parents or students book, because they are two different buyers and only one of them pays',
      'What the safeguarding requirements are in this market for anyone handling lessons with minors',
    ],
    money: 'At what number of lessons a month does a flat fee beat the commission the tutor pays today?',
    idea: 'A booking and payments tool for private tutors who want to leave the marketplace and keep their students.',
  },
  {
    slug: 'tradesperson-quoting',
    title: 'Is a quoting app for tradespeople worth building?',
    description:
      'Electricians quote from a van at eight in the evening. What the existing job software costs, what they actually use, and whether quoting alone is a business.',
    h1: 'Quotes, for people who write them in a van.',
    audience: 'the sole-trader electrician or plumber with no office',
    checks: [
      'What the established job-management suites charge, and how much of that is for the accounting half nobody asked for',
      'Whether the merchants they buy from publish prices a quote could be built against',
      'What proportion of jobs come through a directory that already sends a quote form',
    ],
    money: 'Does winning one extra job a month cover a year of the subscription? For most trades that is the whole sale.',
    idea: 'A quoting app for sole-trader electricians who write quotes from the van, priced against merchant catalogues.',
  },
  {
    slug: 'physiotherapy-clinic-intake',
    title: 'Is a physio clinic intake tool worth building?',
    description:
      'Clinic software is bought once a decade and hated throughout. What it costs, what the record-keeping rules demand, and whether intake alone can be sold separately.',
    h1: 'Patient intake for a small physiotherapy clinic.',
    audience: 'a two- or three-room clinic with a part-time receptionist',
    checks: [
      'What the incumbent practice-management systems charge, and whether they sell per practitioner or per site',
      'What the record-retention and data rules require in this market, because they decide where this can be hosted at all',
      'Whether the insurers they bill impose a form that has to be produced anyway',
    ],
    money: 'How many receptionist hours a week does it have to save before the clinic notices?',
    idea: 'A patient intake and consent tool for small physiotherapy clinics, built around the forms the insurers already demand.',
  },
  {
    slug: 'photographer-gallery-delivery',
    title: 'Is a photo delivery tool worth building?',
    description:
      'Photographers already pay for a gallery host and a studio manager. What both cost, where they overlap, and whether the seam between them is a business.',
    h1: 'Delivering galleries, and getting paid on delivery.',
    audience: 'the wedding or portrait photographer working alone',
    checks: [
      'What the gallery hosts charge, including the storage tier nobody notices until year two',
      'Whether the studio-management tools already deliver galleries, which would make this a feature rather than a product',
      'What print labs pay in referral commission, since that is a revenue line the incumbent already books',
    ],
    money: 'Does print commission cover the storage bill, or does the subscription have to carry both?',
    idea: 'A gallery delivery tool for wedding photographers that takes payment before the download.',
  },
  {
    slug: 'bakery-preorder',
    title: 'Is a bakery pre-order system worth building?',
    description:
      'Bakeries sell out by ten and waste by four. What pre-order platforms charge, what the tills do already, and the number that decides whether it is worth it.',
    h1: 'Pre-orders for a bakery that sells out by ten.',
    audience: 'a single-site bakery baking to a guess every morning',
    checks: [
      'What the pre-order platforms charge per order rather than per month, because a bakery basket is small',
      'What the till already does, since a second system at the counter is the thing that kills adoption',
      'Whether the delivery apps they are already on forbid taking the same order directly',
    ],
    money: 'What is a day of waste worth, and how much of it does a pre-order actually remove?',
    idea: 'A pre-order and collection system for a single-site bakery that bakes to a guess every morning.',
  },
  {
    slug: 'recurring-cleaning-bookings',
    title: 'Is a cleaning business booking tool worth building?',
    description:
      'Domestic cleaning is a rota problem, not a booking problem. What the agencies pay for software, what the marketplaces take, and what a tool has to beat.',
    h1: 'Recurring bookings for a domestic cleaning round.',
    audience: 'someone running four or five cleaners and a paper rota',
    checks: [
      'What the marketplaces take per clean, which is what the owner is really comparing against',
      'Whether the cleaners are employed or self-employed here, because it changes what the software must record',
      'What the incumbent field-service tools charge per cleaner per month',
    ],
    money: 'What does one cancelled clean a week cost, and does the tool stop enough of them to pay for itself?',
    idea: 'A recurring booking and rota tool for a domestic cleaning round with five cleaners.',
  },
  {
    slug: 'yoga-studio-class-packs',
    title: 'Is a yoga studio booking app worth building?',
    description:
      'Studio software charges per member and takes the class pack with it. What that costs, what the aggregators take, and whether a smaller studio is served.',
    h1: 'Class packs and bookings for one studio.',
    audience: 'an owner-teacher with one room and a waiting list',
    checks: [
      'What the studio platforms charge, and at which member count the price steps up',
      'What the class aggregators take per booking, and whether they forbid a direct price that undercuts them',
      'Whether the expiry rules on prepaid class packs are regulated in this market',
    ],
    money: 'How much of the revenue is unredeemed class packs, and is a business built on that one you want?',
    idea: 'A booking and class-pack tool for a single-room yoga studio that wants to leave the aggregators.',
  },
  {
    slug: 'freelance-designer-proposals',
    title: 'Is a proposal tool for freelancers worth building?',
    description:
      'Proposal software is a crowded shelf. What the incumbents charge, what freelancers actually send, and whether the retainer half is the real product.',
    h1: 'Proposals and retainers for a freelance designer.',
    audience: 'the solo designer sending three proposals a month',
    checks: [
      'What the proposal tools charge, and how many of them bundle e-signature rather than reselling it',
      'Whether the invoicing tool the freelancer already pays for sends proposals too',
      'What a signature has to satisfy to be binding in this market, which decides whether this can be built alone',
    ],
    money: 'Does a higher win rate on three proposals a month beat a subscription, or does it need six?',
    idea: 'A proposal and retainer tool for freelance designers, with the signature and the first invoice in the same flow.',
  },
  {
    slug: 'mobile-bike-repair',
    title: 'Is a mobile bike repair business worth building?',
    description:
      'A mobile mechanic is a routing problem with a parts bill. What the shops charge, what the van costs an hour, and the density the round needs.',
    h1: 'Mobile bike repair, and the density the round needs.',
    audience: 'a mechanic who would rather not pay for a shopfront',
    checks: [
      'What the fixed-premises shops charge for the four most common jobs, since that is the ceiling',
      'What the parts distributors require before they will open a trade account',
      'Whether the employers and estates in the area already buy cycle-to-work servicing as a benefit',
    ],
    money: 'How many jobs a day does the round need before the van beats the rent on a shop?',
    idea: 'A mobile bike repair round serving one city, booked online and priced by job rather than by hour.',
  },
]

/** The site's own address. Canonicals and the sitemap are absolute. */
export const SITE = 'https://werkha.us'

export const GUIDE_INDEX = {
  slug: 'for',
  title: 'What is worth building — one page per business',
  description:
    'Pick the business closest to yours and see what a shift would check first: the rivals, the price to beat, and the one number that decides it.',
  // No count in the copy: it is one edit away from being wrong, and the
  // component knows how many there are.
  h1: 'Pick the one closest to yours.',
}
