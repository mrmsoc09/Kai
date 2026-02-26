import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080'
const STATE_CHANGING_METHODS = new Set(['post', 'put', 'patch', 'delete'])

let userApiKey: string | undefined
let adminApiKey: string | undefined
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
      .finally(() => {
        csrfTokenRequest = null
      })
  }
  await csrfTokenRequest
  return csrfToken
}

export const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
})

api.interceptors.request.use(async (cfg) => {
  cfg.headers = cfg.headers || {}

  if (userApiKey) cfg.headers['X-API-Key'] = userApiKey
  if (adminApiKey && cfg.url && cfg.url.includes('/hil/findings/') && cfg.url.endsWith('/approve')) {
    cfg.headers['X-API-Key'] = adminApiKey
  }

  const method = (cfg.method || 'get').toLowerCase()
  if (STATE_CHANGING_METHODS.has(method)) {
    const token = await ensureCsrfToken()
    if (token) cfg.headers['X-CSRF-Token'] = token
  }

  return cfg
})

export function setApiKeys(userKey?: string, adminKey?: string){
  userApiKey = userKey || undefined
  adminApiKey = adminKey || undefined
}

export function getApiKeyStatus(){
  return { userKeySet: Boolean(userApiKey), adminKeySet: Boolean(adminApiKey) }
}

export function healthz(){ return api.get('/healthz') }

// Findings
export function createFinding(payload: {program:string,asset:string,title:string,description:string,severity:string}){
  return api.post('/findings/', payload)
}
export function addEvidence(fid: string, payload: {kind:string,uri:string,sha256_hex:string,meta?:any}){
  return api.post(`/findings/${fid}/evidence`, payload)
}

// HIL
export function requestHIL(fid: string, notes?: string){
  return api.post(`/hil/findings/${fid}/request`, {notes})
}
export function approveHIL(fid: string){
  return api.post(`/hil/findings/${fid}/approve`, { checklist: {
    repro_steps:true, http_traces_or_logs:true, poc_or_screencap:true, scope_confirmation:true, impact_rationale:true
  }})
}
export function submitFinding(fid: string, reportHashHex: string){
  return api.post(`/hil/findings/${fid}/submit`, {report_content_hash_hex: reportHashHex})
}

// Scopes
export function getScope(program: string){ return api.get(`/scopes/${encodeURIComponent(program)}`) }
export function upsertScope(program: string, body: any){ return api.post(`/scopes/${encodeURIComponent(program)}`, body) }

// Providers
export function getProviderCatalog(market?: string){
  const params = market ? { market } : undefined
  return api.get('/providers/catalog', { params })
}
export function getProviderSelection(market: string){
  return api.get('/providers/selection', { params: { market } })
}
export function setProviderSelection(market: string, selected_ids: string[]){
  return api.post('/providers/selection', { market, selected_ids })
}
