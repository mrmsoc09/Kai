import axios from 'axios'
import { useStore } from '../store/system'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const STATE_CHANGING_METHODS = new Set(['post', 'put', 'patch', 'delete'])

let csrfToken: string | undefined
let csrfTokenRequest: Promise<void> | null = null

async function ensureCsrfToken(): Promise<string | undefined> {
  if (csrfToken) return csrfToken
  if (!csrfTokenRequest) {
    csrfTokenRequest = fetch(`${API_BASE}/auth/csrf-token`, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    })
      .then(async (response) => {
        if (!response.ok) return
        const payload = await response.json()
        if (typeof payload?.csrf_token === 'string' && payload.csrf_token.length > 0) {
          csrfToken = payload.csrf_token
        }
      })
      .catch(() => undefined)
      .finally(() => { csrfTokenRequest = null })
  }
  await csrfTokenRequest
  return csrfToken
}

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  timeout: 30_000,
})

// Request interceptor: attach CSRF token
api.interceptors.request.use(async (cfg) => {
  cfg.headers = cfg.headers || {}

  // Note: JWT is now handled by HttpOnly cookie; Bearer token header removed.
  const method = (cfg.method || 'get').toLowerCase()
  if (STATE_CHANGING_METHODS.has(method)) {
    const csrf = await ensureCsrfToken()
    if (csrf) cfg.headers['X-CSRF-Token'] = csrf
  }

  return cfg
})

// Response interceptor: 401 → clear session and redirect to /login
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      csrfToken = undefined
      useStore.getState().logout()
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  },
)

export function clearCsrfToken() { csrfToken = undefined }

export function healthz() { return api.get('/healthz') }

// Findings
export function createFinding(payload: { program: string; asset: string; title: string; description: string; severity: string }) {
  return api.post('/findings/', payload)
}
export function addEvidence(fid: string, payload: { kind: string; uri: string; sha256_hex: string; meta?: any }) {
  return api.post(`/findings/${fid}/evidence`, payload)
}
export function listFindings(params?: { severity?: string; status?: string; program?: string; page?: number; page_size?: number }) {
  return api.get('/findings/', { params })
}
export function getFinding(fid: string) {
  return api.get(`/findings/${fid}`)
}

// HIL
export function requestHIL(fid: string, notes?: string) {
  return api.post(`/hil/findings/${fid}/request`, { notes })
}
export function approveHIL(fid: string) {
  return api.post(`/hil/findings/${fid}/approve`, {
    checklist: {
      repro_steps: true, http_traces_or_logs: true, poc_or_screencap: true,
      scope_confirmation: true, impact_rationale: true,
    },
  })
}
export function submitFinding(fid: string, reportHashHex: string) {
  return api.post(`/hil/findings/${fid}/submit`, { report_content_hash_hex: reportHashHex })
}

// Auth
export function authLogout() {
  return api.post('/auth/logout', {})
}

// Scopes
export function getScope(program: string) { return api.get(`/scopes/${encodeURIComponent(program)}`) }
export function upsertScope(program: string, body: any) { return api.post(`/scopes/${encodeURIComponent(program)}`, body) }

// Legacy compat shims (referenced by older components)
export function getApiKeyStatus() {
  const auth = useStore.getState().auth
  return { userKeySet: !!auth.user, adminKeySet: !!auth.user }
}
/** @deprecated Use useStore.getState().auth.token instead */
export function setApiKeys(_userKey: string, _adminKey: string) { /* no-op */ }
/** @deprecated Use useStore instead */
export const Planner = null
/** @deprecated Use useStore instead */
export const State = null

// Opportunities
export function listOpportunities(params?: {
  platform?: string
  access_type?: string
  min_payout?: number
  tag?: string
  search?: string
  public_only?: boolean
  sort_by?: 'score' | 'payout' | 'name'
  limit?: number
  offset?: number
}) {
  return api.get('/opportunities', { params })
}
export function getRankedOpportunities(params?: { limit?: number; public_only?: boolean }) {
  return api.get('/opportunities/ranked', { params })
}
export function getOpportunity(id: string) {
  return api.get(`/opportunities/${encodeURIComponent(id)}`)
}
export function getOpportunityStats() {
  return api.get('/opportunities/stats')
}
export function getScanQueueSettings() {
  return api.get('/opportunities/scan-queue/settings')
}
export function updateScanQueueSettings(payload: { min_concurrent: number; max_concurrent: number }) {
  return api.put('/opportunities/scan-queue/settings', payload)
}
export function dispatchOpportunityScans(payload: {
  items: Array<{
    opportunity_id: string
    subject_key?: string | null
    subject_type?: string | null
    recommended_workflow?: string | null
  }>
  force?: boolean
  safe_mode?: boolean
  dry_run?: boolean
  workflow_override?: string | null
}) {
  return api.post('/opportunities/scan-queue/dispatch', payload)
}

// Workflows
export function listWorkflows(params?: {
  status?: string
  platform?: string
  opportunity_id?: string
  created_by?: string
  limit?: number
  offset?: number
}) {
  return api.get('/workflows', { params })
}
export function createWorkflow(opportunity_id: string, notes?: string) {
  return api.post('/workflows', { opportunity_id, notes: notes ?? '' })
}
export function getWorkflow(wf_id: string) {
  return api.get(`/workflows/${wf_id}`)
}
export function updateWorkflow(wf_id: string, notes: string) {
  return api.patch(`/workflows/${wf_id}`, { notes })
}
export function transitionWorkflow(wf_id: string, to_state: string, notes?: string) {
  return api.post(`/workflows/${wf_id}/transition`, { to_state, notes: notes ?? '' })
}
export function linkWorkflowRun(wf_id: string, run_id: string) {
  return api.post(`/workflows/${wf_id}/link-run`, { run_id })
}
export function getWorkflowScope(wf_id: string) {
  return api.get(`/workflows/${wf_id}/scope`)
}
export function deleteWorkflow(wf_id: string) {
  return api.delete(`/workflows/${wf_id}`)
}
export function submitCredentials(wf_id: string, payload: {
  username?: string
  password?: string
  api_key?: string
  oauth_token?: string
  extra?: Record<string, string>
  notes?: string
  skip_reason?: string
}) {
  return api.post(`/workflows/${wf_id}/credentials`, {
    username: payload.username ?? '',
    password: payload.password ?? '',
    api_key: payload.api_key ?? '',
    oauth_token: payload.oauth_token ?? '',
    extra: payload.extra ?? {},
    notes: payload.notes ?? '',
    skip_reason: payload.skip_reason ?? '',
  })
}
export function submitOutcome(wf_id: string, payload: {
  outcome: string
  payout_usd?: number
  note?: string
}) {
  return api.post(`/workflows/${wf_id}/outcome`, {
    outcome: payload.outcome,
    payout_usd: payload.payout_usd ?? 0,
    note: payload.note ?? '',
  })
}

// Platform / LLM Settings
export function getLLMConfig() {
  return api.get('/settings/llm')
}
export function saveLLMConfig(payload: {
  provider: string
  model: string
  api_key?: string
  base_url?: string
  temperature?: number
  notes?: string
}) {
  return api.post('/settings/llm', {
    provider: payload.provider,
    model: payload.model,
    api_key: payload.api_key ?? '',
    base_url: payload.base_url ?? '',
    temperature: payload.temperature ?? 0.3,
    notes: payload.notes ?? '',
  })
}
export function getLLMProviders() {
  return api.get('/settings/llm/providers')
}

// Providers
export function getProviderCatalog(market?: string) {
  const params = market ? { market } : undefined
  return api.get('/providers/catalog', { params })
}
export function getProviderSelection(market: string) {
  return api.get('/providers/selection', { params: { market } })
}
export function setProviderSelection(market: string, selected_ids: string[]) {
  return api.post('/providers/selection', { market, selected_ids })
}
