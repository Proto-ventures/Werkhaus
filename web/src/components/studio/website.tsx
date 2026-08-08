/**
 * The "website" tab: the thing the company's customers will actually see,
 * shown in a browser frame, live from the files Kit wrote. This is the one
 * artifact that either works or doesn't — no confidence label needed.
 */

import { ExternalLink } from 'lucide-react'
import type { Artifact, Company } from '@/api/client'
import { siteUrl } from '@/api/client'
import { Mark } from '@/components/bauhaus'

export function Website({
  company,
  artifacts,
}: {
  company: Company
  artifacts: Artifact[]
}) {
  const site = artifacts.find((a) => a.kind === 'site')
  const url = site ? siteUrl(company.id) : null
  const kit = company.roster.find((r) => r.id === 'engineer')
  const building = company.status === 'working' && !site

  if (!url) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center px-6">
        <div className="max-w-sm text-center">
          <span className="mx-auto flex w-fit items-center gap-[5px]" aria-hidden>
            <Mark shape="circle" tone={building ? 'blue' : 'faint'} live={building} className="!size-3" />
            <Mark shape="square" tone={building ? 'yellow' : 'faint'} className="!size-3" />
            <Mark shape="triangle" tone={building ? 'red' : 'faint'} />
          </span>
          <p className="display mt-5 text-lg leading-snug">
            {building
              ? kit?.current_activity ?? 'Kit is building your website'
              : 'No website yet'}
          </p>
          <p className="text-ink-soft mt-2 text-[0.8125rem] leading-relaxed">
            {building
              ? 'It appears here the moment it builds. You can watch the steps in the chat.'
              : 'Kit builds it during the first shift. When it exists, this tab shows the real page, live.'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col p-4 sm:p-6">
      <div className="panel flex min-h-0 flex-1 flex-col">
        {/* Browser chrome, honest about what it is: a preview of real files. */}
        <div className="border-rule-soft flex items-center gap-3 border-b px-3 py-2">
          <span className="flex gap-1.5" aria-hidden>
            <span className="bg-rule-soft size-2.5 rounded-full" />
            <span className="bg-rule-soft size-2.5 rounded-full" />
            <span className="bg-rule-soft size-2.5 rounded-full" />
          </span>
          <span className="bg-secondary text-ink-soft min-w-0 flex-1 truncate px-3 py-1 text-center font-mono text-[0.6875rem]">
            {company.name.toLowerCase().replace(/[^a-z0-9]+/g, '')}.example — preview
          </span>
          <a
            href={url}
            target="_blank"
            rel="noreferrer noopener"
            className="text-link flex shrink-0 items-center gap-1 font-mono text-[0.6875rem] underline"
          >
            open full size
            <ExternalLink className="size-3" aria-hidden />
          </a>
        </div>
        <iframe
          title="Your website"
          src={url}
          sandbox="allow-scripts allow-forms"
          className="min-h-0 w-full flex-1 bg-white"
        />
      </div>
      <p className="text-ink-faint mt-2 font-mono text-[0.6875rem]">
        this is the real page, served from the files under the code tab — not a
        mock-up
      </p>
    </div>
  )
}
