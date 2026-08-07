import { useEffect, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'motion/react'
import { Mark } from '@/components/bauhaus'
import { CountUp } from '@/components/motion'
import {
  ECONOMICS,
  HEADER,
  OBJECTIONS,
  PANELS,
  POSITIONING,
  RESEARCH,
  SITE,
  VERDICT,
} from '@/routes/specimen'
import { cn } from '@/lib/utils'

/**
 * The report, played back.
 *
 * A finished shift is five documents and a critic's verdict on them, which as a
 * static page is a wall of text nobody reads. So it plays: one document at a
 * time, its contents assembling, and when Vera's turn comes the files she is
 * attacking light up in the rail beside her objections.
 *
 * Clicking any file takes control and stops the replay. That matters more than
 * it looks: a thing you can steer is obviously a real interface, and a thing
 * that only loops is a video of one.
 */
export function ReportReplay() {
  const reduced = useReducedMotion()
  const [active, setActive] = useState(0)
  const [auto, setAuto] = useState(true)

  useEffect(() => {
    if (!auto || reduced) return
    const timer = setTimeout(
      () => setActive((i) => (i + 1) % PANELS.length),
      PANELS[active].dwell * 1000,
    )
    return () => clearTimeout(timer)
  }, [active, auto, reduced])

  const panel = PANELS[active]
  const onVera = panel.id === 'vera'
  const attacked = new Set(OBJECTIONS.map((o) => o.against))

  return (
    <div className="panel">
      <header className="border-rule flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b px-4 py-3">
        <span className="eyebrow">example report</span>
        <span className="display text-base">{HEADER.company}</span>
        <span className="text-ink-faint ml-auto font-mono text-[0.75rem]">
          shift {HEADER.shift} / {HEADER.minutes} min / ${HEADER.cost}
        </span>
      </header>

      <div className="border-rule-soft border-b px-4 py-3">
        <p className="text-ink-faint font-mono text-[0.6875rem]">typed into the box</p>
        <p className="mt-1 max-w-3xl text-[0.9375rem] leading-relaxed">{HEADER.idea}</p>
      </div>

      <div className="grid lg:grid-cols-[15rem_1fr]">
        {/* ------------------------------------------------------- the rail */}
        <nav className="border-rule-soft border-b lg:border-r lg:border-b-0">
          {PANELS.map((item, i) => {
            const current = i === active
            const flagged = onVera && attacked.has(item.id)
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => {
                  setActive(i)
                  setAuto(false)
                }}
                aria-current={current ? 'true' : undefined}
                className={cn(
                  'border-rule-soft relative block w-full border-b px-3 py-2.5 text-left last:border-b-0',
                  current ? 'bg-ink text-paper' : 'hover:bg-secondary',
                )}
              >
                <span className="flex items-center gap-2">
                  {item.mark ? (
                    <Mark
                      shape={
                        item.mark === 'sourced'
                          ? 'circle'
                          : item.mark === 'inferred'
                            ? 'square'
                            : 'triangle'
                      }
                      tone={
                        current
                          ? 'faint'
                          : item.mark === 'sourced'
                            ? 'blue'
                            : item.mark === 'inferred'
                              ? 'ink'
                              : 'yellow'
                      }
                    />
                  ) : (
                    <Mark shape="triangle" tone={current ? 'faint' : 'red'} />
                  )}
                  <span className="truncate font-mono text-[0.75rem]">{item.file}</span>
                </span>
                <span
                  className={cn(
                    'mt-0.5 block font-mono text-[0.625rem]',
                    current ? 'text-paper/60' : 'text-ink-faint',
                  )}
                >
                  {item.by}
                </span>

                {/* Vera names which file each objection is against, so the rail
                    shows you what she is attacking while you read it. */}
                <AnimatePresence>
                  {flagged && (
                    <motion.span
                      initial={{ opacity: 0, x: -4 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0 }}
                      className="bg-yellow text-ink absolute top-2.5 right-2 px-1 font-mono text-[0.5625rem]"
                    >
                      contested
                    </motion.span>
                  )}
                </AnimatePresence>

                {current && auto && !reduced && (
                  <motion.span
                    key={`bar-${active}`}
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: item.dwell, ease: 'linear' }}
                    className="bg-paper/50 absolute bottom-0 left-0 h-0.5 w-full origin-left"
                  />
                )}
              </button>
            )
          })}

          <p className="text-ink-faint px-3 py-2.5 font-mono text-[0.625rem]">
            {auto && !reduced ? 'playing, click any file' : 'click a file'}
          </p>
        </nav>

        {/* ---------------------------------------------------- the document */}
        <div className="min-h-[26rem] p-4 sm:p-6">
          <AnimatePresence mode="wait">
            <motion.div
              key={panel.id}
              initial={reduced ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={reduced ? undefined : { opacity: 0, y: -6 }}
              transition={{ duration: 0.28, ease: 'easeOut' }}
            >
              {panel.id === 'research' && <Research />}
              {panel.id === 'positioning' && <Positioning />}
              {panel.id === 'economics' && <Economics />}
              {panel.id === 'site' && <Site />}
              {panel.id === 'vera' && <Vera />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      <Verdict />
    </div>
  )
}

/* -------------------------------------------------------------- primitives */

const list = { hidden: {}, show: { transition: { staggerChildren: 0.05 } } }
const row = {
  hidden: { opacity: 0, y: 5 },
  show: { opacity: 1, y: 0, transition: { duration: 0.25 } },
}

function Stagger({ children }: { children: React.ReactNode }) {
  const reduced = useReducedMotion()
  if (reduced) return <>{children}</>
  return (
    <motion.div variants={list} initial="hidden" animate="show">
      {children}
    </motion.div>
  )
}

function Line({ children, className }: { children: React.ReactNode; className?: string }) {
  const reduced = useReducedMotion()
  if (reduced) return <div className={className}>{children}</div>
  return (
    <motion.div variants={row} className={className}>
      {children}
    </motion.div>
  )
}

function Title({ file, note }: { file: string; note: string }) {
  return (
    <div className="border-rule-soft mb-4 border-b pb-3">
      <p className="display text-lg">{file}</p>
      <p className="text-ink-soft mt-0.5 text-[0.8125rem]">{note}</p>
    </div>
  )
}

/* ------------------------------------------------------------------ panels */

function Research() {
  return (
    <>
      <Title
        file="market-research.md"
        note="Marked sourced. A document cannot carry that mark without the pages it came from."
      />
      <div className="border-rule overflow-x-auto border">
        <table className="w-full border-collapse text-[0.8125rem]">
          <thead>
            <tr className="bg-secondary">
              {RESEARCH.head.map((h) => (
                <th
                  key={h}
                  className="eyebrow border-rule border-b px-3 py-2 text-left whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <motion.tbody variants={list} initial="hidden" animate="show">
            {RESEARCH.rows.map((r) => (
              <motion.tr
                key={r[0]}
                variants={row}
                className="border-rule-soft border-b last:border-b-0"
              >
                {r.map((cell, i) => (
                  <td key={i} className={cn('px-3 py-1.5', i === 1 && 'numeric')}>
                    {cell}
                  </td>
                ))}
              </motion.tr>
            ))}
          </motion.tbody>
        </table>
      </div>

      <Stagger>
        <Line className="mt-4 flex items-start gap-2">
          <Mark shape="circle" tone="blue" className="mt-1.5" />
          <p className="text-[0.9375rem] leading-relaxed">{RESEARCH.found}</p>
        </Line>
        <Line className="mt-3">
          <p className="eyebrow text-ink-faint">the three pages this came from</p>
          <ul className="mt-1 space-y-0.5">
            {RESEARCH.sources.map((s) => (
              <li key={s} className="text-link font-mono text-[0.75rem] underline">
                {s}
              </li>
            ))}
          </ul>
        </Line>
        <Line className="text-ink-faint mt-3 font-mono text-[0.75rem]">
          {RESEARCH.caveat}
        </Line>
      </Stagger>
    </>
  )
}

function Positioning() {
  return (
    <>
      <Title
        file="positioning.md"
        note="Marked inferred. Reasoned from the table, not tested on a customer."
      />
      <Stagger>
        <Line>
          <h3 className="display text-xl">{POSITIONING.title}</h3>
          <p className="text-ink-soft mt-1.5 max-w-2xl text-[0.9375rem] leading-relaxed">
            {POSITIONING.why}
          </p>
        </Line>
        <Line className="mt-4">
          <p className="eyebrow text-ink-faint">instead of</p>
          <ul className="mt-1 space-y-1">
            {POSITIONING.instead.map((alt) => (
              <li key={alt} className="text-ink-soft flex gap-2 text-[0.875rem] leading-snug">
                <span aria-hidden className="bg-ink-faint mt-2 size-1 shrink-0" />
                {alt}
              </li>
            ))}
          </ul>
        </Line>
        <Line className="border-l-serious mt-5 max-w-2xl border-l-4 py-1 pl-3">
          <span className="eyebrow text-serious mr-2">vera contested this</span>
          <span className="text-[0.875rem] leading-snug">{POSITIONING.contested}</span>
        </Line>
      </Stagger>
    </>
  )
}

function Economics() {
  return (
    <>
      <Title
        file="unit-economics.md"
        note="Marked made up. Four of the six lines are guesses and each one says so."
      />
      <div className="border-rule overflow-x-auto border">
        <table className="w-full border-collapse text-[0.8125rem]">
          <thead>
            <tr className="bg-secondary">
              {ECONOMICS.head.map((h) => (
                <th
                  key={h}
                  className="eyebrow border-rule border-b px-3 py-2 text-left whitespace-nowrap"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <motion.tbody variants={list} initial="hidden" animate="show">
            {ECONOMICS.rows.map(([line, amount, from, guess]) => (
              <motion.tr
                key={line}
                variants={row}
                className={cn('border-rule-soft border-b', guess && 'bg-yellow/10')}
              >
                <td className="px-3 py-1.5">{line}</td>
                <td className="numeric px-3 py-1.5">{amount}</td>
                <td className="px-3 py-1.5">
                  <span className="flex items-center gap-2">
                    {guess && <Mark shape="triangle" tone="yellow" />}
                    <span className={guess ? 'text-assumption' : 'text-ink-soft'}>
                      {from}
                    </span>
                  </span>
                </td>
              </motion.tr>
            ))}
            <motion.tr variants={row} className="bg-secondary">
              <td className="display px-3 py-2">{ECONOMICS.total[0]}</td>
              <td className="numeric display px-3 py-2">{ECONOMICS.total[1]}</td>
              <td />
            </motion.tr>
          </motion.tbody>
        </table>
      </div>
      <Stagger>
        <Line className="border-l-serious mt-4 max-w-2xl border-l-4 py-1 pl-3">
          <span className="eyebrow text-serious mr-2">not modelled</span>
          <span className="text-[0.875rem] leading-snug">{ECONOMICS.gap}</span>
        </Line>
      </Stagger>
    </>
  )
}

function Site() {
  const reduced = useReducedMotion()
  return (
    <>
      <Title file="site/" note="The one output that either works or does not." />
      <div className="border-rule border">
        <div className="border-rule-soft bg-secondary flex items-center gap-2 border-b px-3 py-1.5">
          <span className="flex gap-1" aria-hidden>
            <span className="bg-ink-faint/40 size-2 rounded-full" />
            <span className="bg-ink-faint/40 size-2 rounded-full" />
            <span className="bg-ink-faint/40 size-2 rounded-full" />
          </span>
          <span className="text-ink-faint font-mono text-[0.6875rem]">{SITE.url}</span>
        </div>
        <motion.div
          initial={reduced ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.15, duration: 0.4 }}
          className="bg-panel px-6 py-10"
        >
          <p className="display max-w-md text-2xl leading-tight">{SITE.headline}</p>
          <p className="text-ink-soft mt-3 max-w-md text-[0.875rem] leading-relaxed">
            {SITE.sub}
          </p>
          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="border-rule-soft text-ink-faint border px-3 py-1.5 font-mono text-[0.75rem]">
              you@example.com
            </span>
            <span className="bg-ink text-paper px-3 py-1.5 font-mono text-[0.75rem]">
              join the waitlist
            </span>
          </div>
        </motion.div>
      </div>
      <Stagger>
        {SITE.checks.map((check) => (
          <Line key={check} className="mt-2 flex items-center gap-2">
            <Mark shape="circle" tone="blue" />
            <span className="text-[0.875rem]">{check}</span>
          </Line>
        ))}
      </Stagger>
    </>
  )
}

function Vera() {
  return (
    <>
      <Title
        file="vera, end of shift"
        note="She cannot edit anything. Three minimum, each naming a claim and what would settle it."
      />
      <Stagger>
        {OBJECTIONS.map((o) => (
          <Line key={o.about} className="border-rule mb-3 border p-4">
            <div className="flex items-center gap-2">
              <Mark shape="triangle" tone={o.severity === 'serious' ? 'yellow' : 'faint'} />
              <span
                className={cn(
                  'eyebrow',
                  o.severity === 'serious' ? 'text-serious' : 'text-noted',
                )}
              >
                {o.severity}
              </span>
              <span className="text-ink-faint ml-auto font-mono text-[0.6875rem]">
                against {o.about}
              </span>
            </div>
            <p className="mt-2 text-[0.9375rem] leading-relaxed">{o.text}</p>
            <p className="border-rule-soft text-ink-soft mt-3 border-t pt-2.5 text-[0.8125rem] leading-snug">
              <span className="eyebrow text-ink-faint mr-2">settled by</span>
              {o.settled}
            </p>
          </Line>
        ))}
      </Stagger>
    </>
  )
}

function Verdict() {
  const reduced = useReducedMotion()
  return (
    <div className="border-rule grid border-t lg:grid-cols-[15rem_1fr]">
      <div className="text-ink-faint border-rule-soft px-3 py-4 font-mono text-[0.6875rem] lg:border-r">
        where it left the company
      </div>
      <div className="px-4 py-4 sm:px-6">
        <div className="flex items-baseline gap-4">
          <CountUp to={VERDICT.percent} className="numeric display text-4xl" />
          <p className="max-w-xl text-[0.9375rem] leading-snug">{VERDICT.headline}</p>
        </div>
        <div className="bg-rule-soft mt-3 h-2 max-w-xl">
          <motion.div
            className="bg-blue h-full origin-left"
            initial={reduced ? false : { scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true, margin: '-10%' }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
            style={{ width: `${VERDICT.percent}%` }}
          />
        </div>
        <p className="eyebrow text-ink-faint mt-4">still missing</p>
        <ul className="mt-1 space-y-1">
          {VERDICT.missing.map((m) => (
            <li key={m} className="text-ink-soft flex gap-2 text-[0.875rem] leading-snug">
              <span aria-hidden className="bg-yellow mt-2 size-1 shrink-0" />
              {m}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
