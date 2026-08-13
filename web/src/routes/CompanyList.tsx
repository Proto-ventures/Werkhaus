import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, type Company } from '@/api/client'
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

  useEffect(() => {
    // Served statically there is no API, and an uncaught rejection leaves a
    // stranger on "loading..." forever — reached from a link on the front page
    // that promises a finished company.
    void api
      .listCompanies()
      .then(setCompanies)
      .catch(() => setCompanies([]))
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
    </Page>
  )
}

