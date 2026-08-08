/**
 * The studio: one screen where a company is run.
 *
 * Left, the conversation — Ada's questions, the plan, the running record, and
 * one box to type in. Centre, the work itself behind three tabs: what the
 * company knows (plan & files), what its customers will see (website), and the
 * files behind it (code). The split matches how a founder actually thinks:
 * "talk to the team" on one side, "show me the thing" on the other.
 */

import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  api,
  type Artifact,
  type AttentionRequest,
  type Decision,
  type Allowance,
  type LedgerEntry,
  type Objection,
  type Shift,
} from '@/api/client'
import { Mark, Wordmark } from '@/components/bauhaus'
import { useClock, useStored } from '@/components/dash'
import { Code } from '@/components/studio/code'
import { PlanWork, type PlanSection } from '@/components/studio/planwork'
import { Rail } from '@/components/studio/rail'
import { Website } from '@/components/studio/website'
import { useCompany } from '@/hooks/useCompany'
import { COMPANY_STATUS } from '@/lib/display'
import { cn } from '@/lib/utils'

type Tab = 'plan' | 'website' | 'code'

const TABS: { key: Tab; label: string }[] = [
  { key: 'plan', label: 'plan & files' },
  { key: 'website', label: 'website' },
  { key: 'code', label: 'code' },
]

/** Old bookmarked sub-routes land in the right place in the new layout. */
const SECTION_MAP: Record<string, { tab: Tab; section?: PlanSection }> = {
  work: { tab: 'plan', section: 'documents' },
  docs: { tab: 'plan', section: 'documents' },
  shifts: { tab: 'plan', section: 'history' },
  history: { tab: 'plan', section: 'history' },
  money: { tab: 'plan', section: 'money' },
  settings: { tab: 'plan', section: 'settings' },
  website: { tab: 'website' },
  code: { tab: 'code' },
}

export function Studio() {
  const { cid, section } = useParams<{ cid: string; section?: string }>()
  const navigate = useNavigate()
  const { company, events, connected, error, refresh } = useCompany(cid)
  useClock()

  const [tab, setTab] = useStored<Tab>(`wh.tab.${cid}`, 'plan')
  const [planSection, setPlanSection] = useStored<PlanSection>(
    `wh.plansec.${cid}`,
    'plan',
  )
  // Below lg the two panes share the screen one at a time.
  const [pane, setPane] = useState<'chat' | 'work'>('chat')

  useEffect(() => {
    const mapped = section ? SECTION_MAP[section] : undefined
    if (mapped) {
      setTab(mapped.tab)
      if (mapped.section) setPlanSection(mapped.section)
      setPane('work')
      navigate(`/c/${cid}`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [section])

  // ------------------------------------------------------------------- data
  const [attention, setAttention] = useState<AttentionRequest[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [objections, setObjections] = useState<Objection[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [shifts, setShifts] = useState<Shift[]>([])
  const [ledger, setLedger] = useState<LedgerEntry[]>([])
  const [allowance, setAllowance] = useState<Allowance | null>(null)
  const [busy, setBusy] = useState(false)

  const loadAll = useCallback(async () => {
    if (!cid) return
    const [at, ar, ob, de, sh, le, al] = await Promise.all([
      api.listAttention(cid),
      api.listArtifacts(cid),
      api.listObjections(cid),
      api.listDecisions(cid),
      api.listShifts(cid),
      api.listLedger(cid),
      api.getAllowance(),
    ])
    setAttention(at)
    setArtifacts(ar)
    setObjections(ob)
    setDecisions(de)
    setShifts(sh)
    setLedger(le)
    setAllowance(al)
  }, [cid])

  useEffect(() => {
    void loadAll()
  }, [loadAll, company])

  async function act(fn: () => Promise<unknown>, done?: string) {
    setBusy(true)
    try {
      await fn()
      if (done) toast.success(done)
      await refresh()
      await loadAll()
    } catch (e) {
      toast.error((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <p className="text-red text-sm">{error}</p>
      </div>
    )
  }
  if (!company || !cid) {
    return (
      <div className="flex h-dvh items-center justify-center">
        <p className="text-ink-faint font-mono text-sm">loading...</p>
      </div>
    )
  }

  const working = company.status === 'working'

  async function share() {
    if (!cid) return
    let url = company?.share?.url ?? null
    if (!url) {
      try {
        setBusy(true)
        url = (await api.publish(cid)).url
        await refresh()
        toast.success('Published. The link is on your clipboard.')
      } catch (e) {
        toast.error((e as Error).message)
        return
      } finally {
        setBusy(false)
      }
    }
    await navigator.clipboard.writeText(`${window.location.origin}${url}`)
    if (company?.share?.url) toast.success('Link copied.')
  }

  return (
    <div className="flex h-dvh flex-col">
      {/* ------------------------------------------------------------ top bar */}
      <header className="border-rule bg-panel border-b">
        <div className="flex h-12 items-center gap-3 px-3 sm:gap-4 sm:px-4">
          <Link
            to="/companies"
            title="All your companies"
            className="focus-visible:ring-ring shrink-0 focus-visible:ring-2 focus-visible:outline-none"
          >
            <Wordmark className="[&>span:last-child]:hidden xl:[&>span:last-child]:inline" />
          </Link>
          <span className="bg-rule-soft hidden h-5 w-px sm:block" aria-hidden />
          <div className="hidden min-w-0 items-baseline gap-2.5 sm:flex">
            <span className="display truncate text-[0.9375rem]">{company.name}</span>
            <span className="text-ink-faint shrink-0 font-mono text-[0.6875rem]">
              {COMPANY_STATUS[company.status].toLowerCase()}
            </span>
          </div>

          <nav
            aria-label="workspace"
            className="border-rule-soft mx-auto flex shrink-0 border"
          >
            {TABS.map(({ key, label }) => (
              <button
                key={key}
                type="button"
                aria-current={tab === key ? 'page' : undefined}
                onClick={() => {
                  setTab(key)
                  setPane('work')
                }}
                className={cn(
                  'display focus-visible:ring-ring px-3 py-1.5 text-[0.8125rem] focus-visible:ring-2 focus-visible:outline-none sm:px-4',
                  tab === key ? 'bg-ink text-paper' : 'hover:bg-secondary',
                )}
              >
                {label}
              </button>
            ))}
          </nav>

          {allowance?.shifts_left != null && (
            <span
              className="text-ink-faint ml-auto hidden font-mono text-[0.6875rem] lg:block"
              title={`${allowance.label} plan`}
            >
              {allowance.shifts_left} shift{allowance.shifts_left === 1 ? '' : 's'}{' '}
              left
            </span>
          )}

          <span
            className={cn(
              'text-ink-faint hidden items-center gap-1.5 font-mono text-[0.6875rem] md:flex',
              allowance?.shifts_left == null && 'ml-auto',
            )}
            title={connected ? 'live' : 'reconnecting'}
          >
            <Mark shape={connected ? 'circle' : 'ring'} tone={connected ? 'blue' : 'faint'} />
            {connected ? 'live' : 'reconnecting'}
          </span>

          {company.status === 'halted' ? (
            <button
              className="btn btn-primary shrink-0 py-1 text-[0.8125rem]"
              disabled={busy}
              onClick={() => act(() => api.resume(cid))}
            >
              start again
            </button>
          ) : working ? (
            <button
              className="btn btn-danger shrink-0 py-1 text-[0.8125rem]"
              disabled={busy}
              onClick={() =>
                act(() => api.halt(cid), 'Stopped. Everything done so far is saved.')
              }
            >
              stop
            </button>
          ) : (
            <button
              className="btn btn-primary shrink-0 py-1 text-[0.8125rem]"
              disabled={
                busy ||
                company.status === 'blocked' ||
                company.shift_count === 0 ||
                allowance?.shifts_left === 0
              }
              title={
                company.shift_count === 0
                  ? 'Approve the plan in the chat first'
                  : allowance?.shifts_left === 0
                    ? 'You have used the shifts on your plan'
                    : undefined
              }
              onClick={() => act(() => api.startShift(cid), 'Shift started.')}
            >
              start a shift
            </button>
          )}
          <button
            className="btn shrink-0 py-1 text-[0.8125rem]"
            disabled={busy}
            onClick={share}
          >
            share
          </button>
          {/* One company with no visible way to start a second reads as the
              only company the product can build. */}
          <Link
            to="/"
            className="btn hidden shrink-0 py-1 text-[0.8125rem] sm:inline-block"
          >
            new company
          </Link>
        </div>

        {/* Mobile: choose which half of the studio fills the screen. */}
        <div className="border-rule-soft flex border-t lg:hidden">
          {(['chat', 'work'] as const).map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setPane(key)}
              className={cn(
                'display flex-1 py-1.5 text-[0.8125rem]',
                pane === key ? 'bg-ink text-paper' : 'hover:bg-secondary',
              )}
            >
              {key === 'chat' ? 'the team' : 'the work'}
            </button>
          ))}
        </div>
      </header>

      {/* --------------------------------------------------------------- body */}
      <div className="flex min-h-0 flex-1">
        <aside
          className={cn(
            'border-rule w-full flex-col border-r lg:flex lg:w-[400px] lg:shrink-0',
            pane === 'chat' ? 'flex' : 'hidden',
          )}
        >
          <Rail
            company={company}
            events={events}
            attention={attention}
            busy={busy}
            onAnswer={(id, answer) =>
              act(
                () => api.answerAttention(cid, id, answer),
                'Answered. The team continues.',
              )
            }
            onNote={(text) =>
              act(() => api.sendNote(cid, text), 'Noted. The team reads it next shift.')
            }
            onCharter={async (patch) => {
              await api.updateCharter(cid, patch)
              await refresh()
            }}
            onStart={() => act(() => api.startShift(cid), 'Shift 1 started.')}
            allowance={allowance}
          />
        </aside>

        <main
          className={cn(
            'min-h-0 flex-1 flex-col lg:flex',
            pane === 'work' ? 'flex' : 'hidden',
          )}
        >
          {tab === 'plan' && (
            <PlanWork
              company={company}
              artifacts={artifacts}
              objections={objections}
              decisions={decisions}
              shifts={shifts}
              ledger={ledger}
              busy={busy}
              section={planSection}
              onSection={setPlanSection}
              onSetBudget={(cap) => act(() => api.setBudget(cid, cap), 'Budget updated.')}
              onHalt={() =>
                act(() => api.halt(cid), 'Stopped. Everything done so far is saved.')
              }
              onShare={share}
              onUnshare={() =>
                act(() => api.unpublish(cid), 'The public page is down.')
              }
              allowance={allowance}
              onAutonomy={(value) =>
                act(
                  () => api.updateCharter(cid, { autonomy: value }),
                  'Changed. It applies from the next shift.',
                )
              }
            />
          )}
          {tab === 'website' && <Website company={company} artifacts={artifacts} />}
          {tab === 'code' && <Code cid={cid} refreshKey={shifts.length} />}
        </main>
      </div>
    </div>
  )
}
