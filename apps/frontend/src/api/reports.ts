export type FinalizeResult = { status: string; run_id?: string; reason?: string };
export async function listRuns(token: string) {
  const r = await fetch('/api/reports/runs', { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`listRuns ${r.status}`);
  return r.json();
}
export async function finalize(run_id: string, token: string) {
  const r = await fetch('/api/reports/finalize', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ run_id, format_id: 'google_vrp', mitigation: { plan: 'TBD' }, duplicate_check: { status: 'clear' } }) });
  const j = await r.json();
  return { ok: r.ok, ...j } as any;
}
export async function submitHiL(run_id: string, token: string) {
  const body = { run_id, format_id: 'google_vrp', finding: {}, evidence: {}, mitigation: { plan: 'TBD' }, hil_approved: true, duplicate_check: { status: 'clear' } };
  const r = await fetch('/api/reports/submit_hil', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`submit_hil ${r.status}`);
  return r.json();
}
export async function packageReport(run_id: string, token: string) {
  const body = { run_id, format_id: 'google_vrp', finding: {}, evidence: {}, mitigation: { plan: 'TBD' }, hil_approved: true, duplicate_check: { status: 'clear' } };
  const r = await fetch('/api/reports/package', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error(`package ${r.status}`);
  return r.json();
}
export async function dispatchReport(run_id: string, token: string) {
  const r = await fetch('/api/submissions/dispatch', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` }, body: JSON.stringify({ run_id, format_id: 'google_vrp', stakeholder: 'google_vrp', hil_approved: true }) });
  if (!r.ok) throw new Error(`dispatch ${r.status}`);
  return r.json();
}
export async function listRecording(run_id: string, token: string) {
  const r = await fetch(`/api/recordings/${run_id}`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error(`recordings ${r.status}`);
  return r.json();
}
