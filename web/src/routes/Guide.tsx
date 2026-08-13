import { Link, Navigate, useParams } from 'react-router-dom'
import { GUIDES, GUIDE_INDEX, type Guide } from '@/routes/seo'
import { PRICING } from '@/routes/specimen'

/**
 * One page per business worth asking about, and the page that lists them.
 *
 * These exist to be found by somebody typing the question into a search engine
 * rather than typing an idea into our box, and the whole point is that they
 * arrive on a page about *their* trade. So the page says what a shift would
 * open first for that trade, names the number it turns on, and then hands them
 * the box with their own idea already in it.
 *
 * What it deliberately does not do is show them a finished report. We have not
 * run a shift for their business, and drawing one would be the same fiction as
 * a stub engine — these pages promise the questions, not the answers.
 */

function useGuide(): Guide | null {
  const { slug } = useParams<{ slug: string }>()
  return GUIDES.find((g) => g.slug === slug) ?? null
}

export function GuidePage() {
  const guide = useGuide()
  if (!guide) return <Navigate to="/for" replace />

  const studio = PRICING.find((t) => t.featured)

  return (
    <article className="mx-auto max-w-3xl px-5 py-14 sm:px-8 lg:py-20">
      <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
        <Link to="/for" className="link">
          what is worth building
        </Link>
      </p>

      <h1 className="display mt-4 text-[1.85rem] leading-[1.1] sm:text-[2.4rem]">
        {guide.h1}
      </h1>
      <p className="text-ink-soft mt-5 max-w-[54ch] text-[1.0625rem] leading-[1.65]">
        Before you build it, four documents about it: who else is already
        selling to {guide.audience}, one price you can defend, a money model
        with every guess labelled, and where the first customers are. Fourteen
        minutes, and every claim says where it came from.
      </p>

      {/* The three things a shift opens first. Written for this trade, which
          is the difference between a page and a doorway. */}
      <h2 className="display mt-12 text-xl leading-tight sm:text-2xl">
        What it checks first, for this one.
      </h2>
      <ol className="mt-6">
        {guide.checks.map((check, i) => (
          <li
            key={check}
            className="border-rule-soft grid grid-cols-[auto_1fr] gap-x-4 border-t py-4"
          >
            <span className="numeric text-ink-faint pt-[2px] text-[0.75rem]">
              {String(i + 1).padStart(2, '0')}
            </span>
            <span className="text-[1rem] leading-relaxed">{check}</span>
          </li>
        ))}
      </ol>

      <div className="panel mt-10 p-6 sm:p-7">
        <p className="text-ink-faint font-mono text-[0.625rem] tracking-[0.1em] uppercase">
          and the number it turns on
        </p>
        <p className="display mt-2 text-[1.25rem] leading-snug">{guide.money}</p>
        <p className="text-ink-soft mt-3 text-[0.875rem] leading-relaxed">
          Nia builds that as a model you can push on — every input marked
          sourced, inferred or assumption, and the gaps shown as gaps rather
          than quietly filled with zero.
        </p>
      </div>

      {/* The box is on the front page. Sending the idea with them means they
          arrive with it typed rather than facing an empty field. */}
      <div className="border-rule mt-12 border p-6 sm:p-7">
        <h2 className="display text-xl leading-tight sm:text-2xl">
          Start with this one.
        </h2>
        <p className="text-ink-soft mt-3 text-[0.9375rem] leading-relaxed">
          &ldquo;{guide.idea}&rdquo;
        </p>
        <div className="mt-6 flex flex-wrap items-center gap-5">
          <Link
            to={`/?idea=${encodeURIComponent(guide.idea)}`}
            className="btn btn-primary"
          >
            run this one, free
          </Link>
          <span className="text-ink-faint font-mono text-[0.6875rem]">
            3 shifts free, no card · then €{studio?.price} a month
          </span>
        </div>
      </div>

      <p className="text-ink-faint mt-10 font-mono text-[0.6875rem] leading-relaxed">
        this page is the questions, not the answers · the answers come from a
        shift run on your idea, not from a page written before you arrived
      </p>
    </article>
  )
}

export function GuideIndex() {
  return (
    <div className="mx-auto max-w-5xl px-5 py-14 sm:px-8 lg:py-20">
      <h1 className="display text-[1.85rem] leading-[1.1] sm:text-[2.4rem]">
        {GUIDE_INDEX.h1}
      </h1>
      <p className="text-ink-soft mt-5 max-w-[56ch] text-[1.0625rem] leading-[1.65]">
        {GUIDES.length} businesses somebody asks about often enough to write
        down. Each one says what a shift would open first and the number it
        turns on. If yours is not here, the box on the front page takes any
        sentence.
      </p>

      <ul className="bg-rule-soft border-rule-soft mt-10 grid gap-px border sm:grid-cols-2">
        {GUIDES.map((guide) => (
          <li key={guide.slug} className="bg-panel">
            <Link
              to={`/for/${guide.slug}`}
              className="focus-visible:ring-ring hover:bg-secondary block h-full p-5 focus-visible:ring-2 focus-visible:outline-none"
            >
              <p className="display text-[1.0625rem] leading-snug">{guide.h1}</p>
              <p className="text-ink-soft mt-2 text-[0.875rem] leading-snug">
                for {guide.audience}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
