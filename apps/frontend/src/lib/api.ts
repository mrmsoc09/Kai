import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8080'

export const api = axios.create({ baseURL: API_BASE })

export function setApiKeys(userKey?: string, adminKey?: string){
  api.interceptors.request.clear()
  api.interceptors.request.use(cfg => {
    cfg.headers = cfg.headers || {}
    if(userKey) cfg.headers['X-API-Key'] = userKey
    if(adminKey && cfg.url && cfg.url.includes('/hil/findings/') && cfg.url.endsWith('/approve')){
      cfg.headers['X-API-Key'] = adminKey
    }
    return cfg
  })
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
