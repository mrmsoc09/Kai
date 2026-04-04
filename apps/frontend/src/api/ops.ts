import { api } from '../lib/api'

function headers(token?: string, json = false): Record<string, string> {
  const out: Record<string, string> = {}
  if (token) out.Authorization = `Bearer ${token}`
  if (json) out['Content-Type'] = 'application/json'
  return out
}

export async function checklist(run_id: string, token: string | undefined, body: any) {
  const r = await api.post(
    '/api/reports/checklist',
    { run_id, format_id: 'google_vrp', ...body },
    { headers: headers(token, true) },
  )
  return r.data
}
export async function decisionTrace(run_id: string, token?: string) {
  const r = await api.get(`/api/logs/${run_id}/decision_trace`, { headers: headers(token) })
  return r.data
}
export async function listOutbox(token?: string) {
  // Backend doesn't expose a list; we proxy via a lightweight endpoint later; for now try a static index if served
  const r = await api.get('/api/submissions/outbox', { headers: headers(token) })
  return r.data
}
