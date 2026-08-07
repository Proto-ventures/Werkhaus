import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, devInfo, type Company, type DevInfo } from '@/api/client'
import { Mark } from '@/components/bauhaus'
import { Page } from '@/components/shell'
import { COMPANY_STATUS, money } from '@/lib/display'

const STATE = {
  working: { shape: 'circle', tone: 'blue' },
  blocked: { shape: 'triangle', tone: 'yellow' },
  halted: { shape: 'triangle', tone: 'red' },
  idle: { shape: 'square', tone: 'ink' },
  draft: { shape: 'square', tone: 'faint' },
  archived: { shape: 'square', tone: 'faint' },
} as const

export function CompanyList() {
  const [companies, setCompanies] = useState<Company[] | null>(null)
  const [dev, setDev] = useState<DevInfo | null>(null)

  useEffect(() => {
    void api.listCompanies().then(setCompanies)
    void devInfo().then(setDev)
  }, [])

  return (
    <Page>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="display text-2xl sm:text-3xl">Your companies</h1>
          <p className="text-ink-soft mt-1.5 text-[0.9375rem]">
            Each one is a team of eight, working shifts on a business you described.
          </p>
        </div>
        <Link to="/" className="btn btn-primary">
          start a company
        </Link>
      </div>

      {companies === null ? (
        <p className="text-ink-faint mt-8 font-mono text-sm">loading...</p>
      ) : companies.length === 0 ? (
        <div className="panel mt-8 p-10">
          <p className="display text-lg">No companies yet</p>
          <p className="text-ink-soft mt-1.5 max-w-md text-[0.875rem] leading-snug">
            Describe a business in a couple of sentences. Werkhaus turns it into a
            charter, hires the team, and they start work on your say-so.
          </p>
          <Link to="/" className="btn btn-primary mt-6">
            describe your business
          </Link>
        </div>
      ) : (
        <ul className="bg-rule border-rule mt-6 grid gap-px border sm:grid-cols-2">
          {companies.map((company) => {
            const state = STATE[company.status]
            return (
              <li key={company.id}>
                <Link
                  to={`/c/${company.id}`}
                  className="bg-panel hover:bg-secondary focus-visible:ring-ring flex h-full flex-col p-5 focus-visible:ring-2 focus-visible:outline-none"
                >
                  <div className="flex items-center gap-2">
                    <Mark
                      shape={state.shape}
                      tone={state.tone}
                      live={company.status === 'working'}
                    />
                    <span className="eyebrow text-ink-soft">
                      {COMPANY_STATUS[company.status]}
                    </span>
                  </div>

                  <h2 className="display mt-2 text-xl leading-tight">
                    {company.name}
                  </h2>
                  <p className="text-ink-soft mt-1 text-[0.8125rem] leading-snug">
                    {company.charter.one_liner}
                  </p>

                  <div className="mt-auto pt-5">
                    <div className="bg-rule-soft h-2 w-full">
                      <div
                        className="bg-blue h-full"
                        style={{ width: `${company.progress.percent}%` }}
                      />
                    </div>
                    <p className="text-ink-faint mt-2 flex justify-between font-mono text-[0.6875rem]">
                      <span>{company.progress.percent}% there</span>
                      <span>
                        {company.shift_count} shifts · {money(company.budget.spent)}
                      </span>
                    </p>
                  </div>
                </Link>
              </li>
            )
          })}
        </ul>
      )}

      {dev && <DevBar dev={dev} />}
    </Page>
  )
}

/**
 * Stub-only. Present so the whole failure matrix is one click away — if the team
 * only ever demos the happy path, the UI only learns to render success.
 */
function DevBar({ dev }: { dev: DevInfo }) {
  return (
    <aside className="border-rule-soft text-ink-soft mt-10 border border-dashed p-4 font-mono text-[0.75rem]">
      <p className="eyebrow">stub engine</p>
      <p className="mt-1.5 leading-snug">
        No language model has been called. Add{' '}
        <code className="bg-secondary px-1">[scenario:name]</code> to a description
        to pick how the shift goes:
      </p>
      <ul className="mt-2 grid gap-x-6 gap-y-0.5 sm:grid-cols-2">
        {dev.scenarios.map((scenario) => (
          <li key={scenario.name}>
            <code className="bg-secondary px-1">{scenario.name}</code>{' '}
            {scenario.title}
          </li>
        ))}
      </ul>
      <p className="mt-2 leading-snug">
        Shifts run at real speed on purpose (about fifteen minutes). Current
        multiplier: {dev.speed ?? 1}x.
      </p>
    </aside>
  )
}
