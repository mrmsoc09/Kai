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

// Request interceptor: attach Bearer token + CSRF token
api.interceptors.request.use(async (cfg) => {
  cfg.headers = cfg.headers || {}

  const token = useStore.getState().auth.token
  if (token) cfg.headers['Authorization'] = `Bearer ${token}`

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
  const token = useStore.getState().auth.token
  return { userKeySet: !!token, adminKeySet: !!token }
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
