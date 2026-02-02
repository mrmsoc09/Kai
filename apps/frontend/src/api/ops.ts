export async function checklist(run_id: string, token: string, body: any) {
  const r = await fetch('/api/reports/checklist', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ run_id, format_id: 'google_vrp', ...body }) });
  if (!r.ok) throw new Error(`checklist ${r.status}`);
  return r.json();
}
export async function decisionTrace(run_id: string, token: string) {
  const r = await fetch(`/api/logs/${run_id}/decision_trace`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`decision_trace ${r.status}`);
  return r.json();
}
export async function listOutbox(token: string) {
  // Backend doesn't expose a list; we proxy via a lightweight endpoint later; for now try a static index if served
  const r = await fetch('/api/submissions/outbox', { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`outbox ${r.status}`);
  return r.json();
}
