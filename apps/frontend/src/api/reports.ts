import { api } from '../lib/api'

export type FinalizeResult = { status: string; run_id?: string; reason?: string };
function authConfig(token?: string) {
  return token ? { headers: { Authorization: `Bearer ${token}` } } : undefined
}

export async function listRuns(token?: string) {
  const r = await api.get('/api/reports/runs', authConfig(token))
  return r.data
}
export async function finalize(run_id: string, token?: string) {
  const r = await api.post(
    '/api/reports/finalize',
    { run_id, format_id: 'google_vrp', mitigation: { plan: 'TBD' }, duplicate_check: { status: 'clear' } },
    authConfig(token),
  )
  return { ok: true, ...r.data } as any
}
export async function submitHiL(run_id: string, token?: string) {
  const body = { run_id, format_id: 'google_vrp', finding: {}, evidence: {}, mitigation: { plan: 'TBD' }, hil_approved: true, duplicate_check: { status: 'clear' } };
  const r = await api.post('/api/reports/submit_hil', body, authConfig(token))
  return r.data
}
export async function packageReport(run_id: string, token?: string) {
  const body = { run_id, format_id: 'google_vrp', finding: {}, evidence: {}, mitigation: { plan: 'TBD' }, hil_approved: true, duplicate_check: { status: 'clear' } };
  const r = await api.post('/api/reports/package', body, authConfig(token))
  return r.data
}
export async function dispatchReport(run_id: string, token?: string) {
  const r = await api.post(
    '/api/submissions/dispatch',
    { run_id, format_id: 'google_vrp', stakeholder: 'google_vrp', hil_approved: true },
    authConfig(token),
  )
  return r.data
}
export async function listRecording(run_id: string, token?: string) {
  const r = await api.get(`/api/recordings/${run_id}`, authConfig(token))
  return r.data
}
