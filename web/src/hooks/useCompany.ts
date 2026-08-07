import { useCallback, useEffect, useRef, useState } from 'react'
import {
  api,
  openCompanySocket,
  type Company,
  type ShiftEvent,
} from '@/api/client'

/** The feed keeps a window, not a transcript. A firehose shift emits thousands. */
const FEED_WINDOW = 250

export interface LiveCompany {
  company: Company | null
  events: ShiftEvent[]
  activity: Record<string, string>
  connected: boolean
  error: string | null
  refresh: () => Promise<void>
}

/** Kinds that change something the REST models hold, so we re-read after them. */
const REFETCH_ON = new Set([
  'shift.started',
  'shift.phase',
  'shift.completed',
  'shift.failed',
  'progress.updated',
  'budget.exceeded',
  'attention.needed',
  'artifact.created',
  'artifact.updated',
  'decision.made',
  'decision.contested',
])

/** Noise the feed suppresses. Budget ticks drive the meter, not the story. */
const HIDDEN = new Set(['budget.spent', 'heartbeat'])

export function useCompany(cid: string | undefined): LiveCompany {
  const [company, setCompany] = useState<Company | null>(null)
  const [events, setEvents] = useState<ShiftEvent[]>([])
  const [activity, setActivity] = useState<Record<string, string>>({})
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const pending = useRef(false)

  const refresh = useCallback(async () => {
    if (!cid) return
    try {
      setCompany(await api.getCompany(cid))
    } catch (e) {
      setError((e as Error).message)
    }
  }, [cid])

  useEffect(() => {
    if (!cid) return
    let alive = true
    setEvents([])
    setActivity({})

    // Cold load first: a shift must be fully reconstructible from REST with no
    // socket at all, which is what makes "leave and come back" work.
    void (async () => {
      try {
        const [fresh, history] = await Promise.all([
          api.getCompany(cid),
          api.replay(cid, 0),
        ])
        if (!alive) return
        setCompany(fresh)
        setEvents(history.filter((e) => !HIDDEN.has(e.kind)).slice(-FEED_WINDOW))
      } catch (e) {
        if (alive) setError((e as Error).message)
      }
    })()

    return () => {
      alive = false
    }
  }, [cid])

  useEffect(() => {
    if (!cid) return
    return openCompanySocket(
      cid,
      (event) => {
        if (event.role_id && event.kind === 'role.activity') {
          setActivity((prev) => ({ ...prev, [event.role_id!]: event.text }))
        }
        if (
          event.role_id &&
          (event.kind === 'role.finished' ||
            event.kind === 'role.failed' ||
            event.kind === 'shift.completed')
        ) {
          setActivity((prev) => {
            const next = { ...prev }
            if (event.role_id) delete next[event.role_id]
            return next
          })
        }

        if (!HIDDEN.has(event.kind)) {
          setEvents((prev) => {
            // Coalesce a run of one employee's activity into a single line.
            // Without this a firehose shift is an unreadable wall.
            const last = prev[prev.length - 1]
            if (
              last &&
              last.kind === 'role.activity' &&
              event.kind === 'role.activity' &&
              last.role_id === event.role_id
            ) {
              return [...prev.slice(0, -1), event].slice(-FEED_WINDOW)
            }
            return [...prev, event].slice(-FEED_WINDOW)
          })
        }

        if (REFETCH_ON.has(event.kind) && !pending.current) {
          pending.current = true
          // Coalesce bursts into one read rather than one per event.
          setTimeout(() => {
            pending.current = false
            void refresh()
          }, 250)
        }
      },
      { onStatus: setConnected },
    )
  }, [cid, refresh])

  return { company, events, activity, connected, error, refresh }
}
