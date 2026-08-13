/**
 * The only place that talks to the engine.
 *
 * Every URL is origin-relative: in dev, Vite proxies to uvicorn; in production
 * FastAPI serves this bundle itself. There is no build-time backend URL.
 */

import type { components } from './types.gen'

export type Company = components['schemas']['Company']
export type Shift = components['schemas']['Shift']
export type ShiftEvent = components['schemas']['ShiftEvent']
export type Artifact = components['schemas']['Artifact']
export type Decision = components['schemas']['Decision']
export type Task = components['schemas']['Task']
export type LedgerEntry = components['schemas']['LedgerEntry']
export type MoneyModel = components['schemas']['MoneyModel']

/** The error envelope the API guarantees. Never a traceback. */
export interface ApiError {
  code: string
  message: string
  hint: string | null
  request_id: string
}

export class WerkhausApiError extends Error {
  status: number
  detail: ApiError

  constructor(status: number, detail: ApiError) {
    super(detail.message)
    this.status = status
    this.detail = detail
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new WerkhausApiError(
      response.status,
      body?.error ?? {
        code: 'internal',
        message: 'Something went wrong on our side.',
        hint: null,
        request_id: response.headers.get('X-Request-Id') ?? 'req_unknown',
      },
    )
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T)
}

export type Objection = components['schemas']['Objection']
export type AttentionRequest = components['schemas']['AttentionRequest']
export type Budget = components['schemas']['Budget']
export type VaultItem = components['schemas']['VaultItem']
export type WorkspaceFile = components['schemas']['WorkspaceFile']
export type ShareLink = components['schemas']['ShareLink']
export type Allowance = components['schemas']['Allowance']
export type IntegrationSpec = components['schemas']['IntegrationSpec']
export type IntegrationState = components['schemas']['IntegrationState']
export type Connection = components['schemas']['Connection']
export type WalkStep = components['schemas']['WalkStep']
export type CredentialField = components['schemas']['CredentialField']
export type ProvisionedResource = components['schemas']['ProvisionedResource']
export type BrainProvider = components['schemas']['BrainProvider']
export type BrainChoice = components['schemas']['BrainChoice']
export type DirectoryEntry = components['schemas']['DirectoryEntry']
export type McpConnection = components['schemas']['McpConnection']

export const api = {
  listCompanies: () => request<Company[]>('/companies'),
  getCompany: (cid: string) => request<Company>(`/companies/${cid}`),
  createCompany: (idea: string, name?: string) =>
    request<Company>('/companies', {
      method: 'POST',
      body: JSON.stringify({ idea, name: name ?? null }),
    }),
  updateCharter: (cid: string, patch: Record<string, unknown>) =>
    request<Company>(`/companies/${cid}/charter`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    }),
  startShift: (cid: string, focus?: string) =>
    request<Shift>(`/companies/${cid}/shifts`, {
      method: 'POST',
      body: JSON.stringify({ focus: focus ?? null }),
    }),
  stopShift: (sid: string) =>
    request<Shift>(`/shifts/${sid}/stop`, {
      method: 'POST',
      body: JSON.stringify({ reason: 'user' }),
    }),
  halt: (cid: string) => request<Company>(`/companies/${cid}/halt`, { method: 'POST' }),
  resume: (cid: string) =>
    request<Company>(`/companies/${cid}/resume`, { method: 'POST' }),
  setBudget: (cid: string, cap: number) =>
    request<Budget>(`/companies/${cid}/budget`, {
      method: 'PUT',
      body: JSON.stringify({ cap: cap.toFixed(2) }),
    }),
  sendNote: (cid: string, text: string) =>
    request<void>(`/companies/${cid}/notes`, {
      method: 'POST',
      body: JSON.stringify({ text }),
    }),
  answerAttention: (cid: string, requestId: string, answer: string) =>
    request<void>(`/companies/${cid}/attention/${requestId}`, {
      method: 'POST',
      body: JSON.stringify({ answer }),
    }),
  listShifts: (cid: string) => request<Shift[]>(`/companies/${cid}/shifts`),
  listArtifacts: (cid: string) => request<Artifact[]>(`/companies/${cid}/artifacts`),
  listDecisions: (cid: string) => request<Decision[]>(`/companies/${cid}/decisions`),
  listObjections: (cid: string) => request<Objection[]>(`/companies/${cid}/objections`),
  listAttention: (cid: string) =>
    request<AttentionRequest[]>(`/companies/${cid}/attention`),
  listTasks: (cid: string) => request<Task[]>(`/companies/${cid}/tasks`),
  /** Account-wide, never per company. */
  getAllowance: () => request<Allowance>('/allowance'),
  listIntegrations: (cid: string) =>
    request<IntegrationState[]>(`/companies/${cid}/integrations`),
  connectIntegration: (cid: string, provider: string, values: Record<string, string>) =>
    request<IntegrationState>(`/companies/${cid}/integrations/${provider}`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    }),
  verifyIntegration: (cid: string, provider: string) =>
    request<IntegrationState>(`/companies/${cid}/integrations/${provider}/verify`, {
      method: 'POST',
    }),
  disconnectIntegration: (cid: string, provider: string) =>
    request<void>(`/companies/${cid}/integrations/${provider}`, { method: 'DELETE' }),
  listBrains: () => request<BrainProvider[]>('/brains'),
  searchDirectory: (q: string, limit = 12) =>
    request<DirectoryEntry[]>(
      `/mcp/directory?q=${encodeURIComponent(q)}&limit=${limit}`,
    ),
  mcpCategories: () =>
    request<{ categories: string[]; total: number }>('/mcp/categories'),
  listMcp: (cid: string) => request<McpConnection[]>(`/companies/${cid}/mcp`),
  addMcp: (
    cid: string,
    body: {
      name: string
      label: string
      transport?: string
      url?: string
      command?: string
      env?: Record<string, string>
      directory_url?: string
    },
  ) =>
    request<McpConnection>(`/companies/${cid}/mcp`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  removeMcp: (cid: string, name: string) =>
    request<void>(`/companies/${cid}/mcp/${name}`, { method: 'DELETE' }),
  getBrain: (cid: string) => request<BrainChoice>(`/companies/${cid}/brain`),
  setBrain: (
    cid: string,
    body: { provider: string; model: string; key: string; base_url?: string },
  ) =>
    request<BrainChoice>(`/companies/${cid}/brain`, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  listResources: (cid: string) =>
    request<ProvisionedResource[]>(`/companies/${cid}/resources`),
  listLedger: (cid: string) => request<LedgerEntry[]>(`/companies/${cid}/ledger`),
  /** What the business would earn. Null until somebody has modelled it. */
  getMoney: (cid: string) =>
    request<MoneyModel | null>(`/companies/${cid}/finances`),
  /** Cold load: a shift is fully reconstructible without a live socket. */
  replay: (cid: string, sinceSeq = 0) =>
    request<ShiftEvent[]>(`/companies/${cid}/events?since_seq=${sinceSeq}`),
  readArtifact: async (aid: string): Promise<string> => {
    const response = await fetch(`/api/v1/artifacts/${aid}/content`)
    return response.ok ? response.text() : ''
  },
  listVault: (cid: string) => request<VaultItem[]>(`/companies/${cid}/vault`),
  setVault: (cid: string, name: string, value: string) =>
    request<VaultItem>(`/companies/${cid}/vault/${encodeURIComponent(name)}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    }),
  deleteVault: (cid: string, name: string) =>
    request<void>(`/companies/${cid}/vault/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    }),
  listFiles: (cid: string) => request<WorkspaceFile[]>(`/companies/${cid}/files`),
  readFile: async (cid: string, path: string): Promise<string> => {
    const response = await fetch(
      `/api/v1/companies/${cid}/files/content?path=${encodeURIComponent(path)}`,
    )
    return response.ok ? response.text() : ''
  },
  publish: (cid: string) =>
    request<ShareLink>(`/companies/${cid}/share`, {
      method: 'POST',
      body: JSON.stringify({ include_shifts: true, include_artifacts: true }),
    }),
  unpublish: (cid: string) =>
    request<void>(`/companies/${cid}/share`, { method: 'DELETE' }),
}

/** Where the built site is served. Ends in a slash so relative assets work. */
export function siteUrl(cid: string): string {
  return `/api/v1/companies/${cid}/site/`
}

/** Stub-only. Present in dev so the whole failure matrix is demoable. */
/**
 * Live events, with resume.
 *
 * The socket is a nicety, not the source of truth: we remember the last seq and
 * reconnect with `?since_seq=`, so a dropped connection costs nothing.
 */
export function openCompanySocket(
  cid: string,
  onEvent: (event: ShiftEvent) => void,
  opts: { sinceSeq?: number; onStatus?: (up: boolean) => void } = {},
): () => void {
  let lastSeq = opts.sinceSeq ?? 0
  let closed = false
  let socket: WebSocket | null = null
  let retry = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const connect = () => {
    if (closed) return
    const scheme = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${scheme}://${window.location.host}/ws/companies/${cid}?since_seq=${lastSeq}`
    socket = new WebSocket(url)

    socket.onopen = () => {
      retry = 0
      opts.onStatus?.(true)
    }
    socket.onmessage = (message) => {
      const event = JSON.parse(message.data) as ShiftEvent
      lastSeq = Math.max(lastSeq, event.seq)
      onEvent(event)
    }
    socket.onclose = () => {
      opts.onStatus?.(false)
      if (closed) return
      const delay = Math.min(30_000, 500 * 2 ** retry++)
      timer = setTimeout(connect, delay)
    }
  }

  connect()
  return () => {
    closed = true
    if (timer) clearTimeout(timer)
    socket?.close()
  }
}
