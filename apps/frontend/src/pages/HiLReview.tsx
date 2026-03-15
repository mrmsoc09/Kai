import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { listRuns, finalize, submitHiL, packageReport, dispatchReport, listRecording } from '../api/reports';
import { checklist, decisionTrace } from '../api/ops';
import { useStore } from '../store/system';
import StatusChip from '../components/StatusChip';
import LogList from '../components/LogList';

type RunRow = { id: string; recCount?: number; status?: string; last?: string };

export default function HiLReview() {
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [chk, setChk] = useState<any | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const token = useStore(state => state.auth.token);
  const navigate = useNavigate();

  async function refresh() {
    if (!token) { navigate('/login'); return; }
    const j = await listRuns(token);
    const arr: RunRow[] = await Promise.all((j.runs || []).map(async (id: string) => {
      try {
        const rec = await listRecording(id, token);
        return { id, recCount: (rec.segments || []).length, status: rec.archive ? 'archived' : 'segments' };
      } catch {
        return { id };
      }
    }));
    setRuns(arr);
  }

  async function loadSel(id: string) {
    setSel(id);
    try {
      const c = await checklist(id, token, { finding: {}, evidence: {}, mitigation: {} });
      setChk(c);
      const dl = await decisionTrace(id, token);
      setLogs(dl.decision_trace || []);
    } catch(e) {
      setChk(null);
    }
  }

  useEffect(() => {
    if (!token) { navigate('/login'); return; }
    void refresh();
  }, [token]);

  async function doFlow(id: string) {
    setBusy(id);
    try {
      const fin = await finalize(id, token);
      if (!fin.ok && (fin as any).reason) { alert(`Finalize blocked: ${(fin as any).reason}`); return; }
      await submitHiL(id, token);
      await packageReport(id, token);
      const disp = await dispatchReport(id, token);
      alert(`Dispatched: ${disp.eml || disp.status}`);
    } catch (e: any) {
      alert(`Error: ${e.message}`);
    } finally {
      setBusy(null);
      void refresh();
      if (sel === id) { void loadSel(id); }
    }
  }

  return (
    <div style={{ padding: 20, color: '#8FAF9B' }}>
      <h2>HiL Review & Dispatch</h2>
      <div style={{ display: 'flex', gap: 24 }}>
        <div style={{ flex: 1 }}>
          <button onClick={() => refresh()}>Refresh</button>
          <table style={{ width: '100%', marginTop: 12 }}>
            <thead>
              <tr><th>Run ID</th><th>Recordings</th><th>Status</th><th>Action</th></tr>
            </thead>
            <tbody>
              {runs.map(r => (
                <tr key={r.id} style={{ cursor: 'pointer', background: sel===r.id? '#111827': 'transparent' }} onClick={() => loadSel(r.id)}>
                  <td>{r.id}</td>
                  <td>{r.recCount ?? '-'}</td>
                  <td>{r.status ?? '-'}</td>
                  <td>
                    <button disabled={busy === r.id} onClick={(e) => { e.stopPropagation(); void doFlow(r.id); }}>
                      {busy === r.id ? 'Working...' : 'Finalize → Dispatch'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div style={{ flex: 1 }}>
          <h3>Checklist</h3>
          {chk ? (
            <div style={{ display: 'grid', gap: 8 }}>
              <div><StatusChip ok={!!chk.format_ok} label={`Format: ${chk.format_ok? 'OK':'Fail'}`} /></div>
              <div><StatusChip ok={!!chk.recording_ok} label={`Recording: ${chk.recording_ok? 'OK':'Missing'}`} /></div>
              <div><StatusChip ok={!!chk.mitigation_ok} label={`Mitigation: ${chk.mitigation_ok? 'OK':'Missing'}`} /></div>
              <div><StatusChip ok={chk.duplicate?.status==='clear'} label={`Duplicate: ${chk.duplicate?.status}`} /></div>
              <div>Stakeholder: {chk.stakeholder}</div>
            </div>
          ) : <div>Select a run</div>}

          <h3 style={{ marginTop: 16 }}>Decision Trace</h3>
          <LogList items={logs} />
        </div>
      </div>
    </div>
  );
}
