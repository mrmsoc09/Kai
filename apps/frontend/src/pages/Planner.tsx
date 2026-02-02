import React, { useState } from 'react';
import { Planner as PlannerAPI } from '../lib/api';

const examples = [
  'TA0043:T1593', // Search Open Websites/Domains
  'TA0043:T1595', // Active Scanning (plan-mode)
  'TA0005:T1562.001', // Impair defenses (blocked)
  'TA0010:T1048.003', // Exfil over alt channel (muted desc)
];

export default function Planner() {
  const [technique, setTechnique] = useState<string>(examples[0]);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string>('');
  const [busy, setBusy] = useState<boolean>(false);

  const runPlan = async () => {
    setErr(''); setBusy(true);
    try { const j = await PlannerAPI.plan(technique); setResult(j.plan); }
    catch (e:any) { setErr(String(e)); }
    finally { setBusy(false); }
  };

  const disabledExec = true; // execution disabled by policy in this build

  return (
    <div className="p-6 text-sm text-gray-200">
      <h1 className="text-2xl font-bold mb-4">MITRE Planner (Plan-Mode)</h1>
      <div className="flex items-center gap-2 mb-4">
        <input className="bg-black/40 border border-cyan-500/40 rounded px-2 py-1 font-mono w-[280px]" value={technique} onChange={(e)=>setTechnique(e.target.value)} />
        <select className="bg-black/40 border border-cyan-500/40 rounded px-2 py-1" value={technique} onChange={(e)=>setTechnique(e.target.value)}>
          {examples.map((ex) => (<option key={ex} value={ex}>{ex}</option>))}
        </select>
        <button onClick={runPlan} disabled={busy} className="px-3 py-1 rounded bg-cyan-600/70 hover:bg-cyan-600 disabled:opacity-50">Plan</button>
        <button disabled className="px-3 py-1 rounded bg-amber-700/60 opacity-60" title="Execution disabled by policy">Execute (HiL required)</button>
      </div>
      {err && <div className="text-amber-400">{err}</div>}
      {result && (
        <div className="mt-4 space-y-2">
          <div>Technique: <span className="font-mono">{result.technique_id}</span></div>
          <div>Risk: <span className={`font-mono ${result.risk_category==='blocked'?'text-amber-400':'text-emerald-400'}`}>{result.risk_category}</span></div>
          <div>HiL Required: <span className="font-mono">{String(result.hil_required)}</span></div>
          <div className="mt-2">
            <div className="font-semibold">Steps</div>
            <ol className="list-decimal ml-6 space-y-1">
              {result.steps?.map((s:any)=> <li key={s.id}><span className="font-mono text-xs opacity-70">[{s.type}]</span> {s.action}</li>)}
            </ol>
          </div>
          {result.notes?.length>0 && (
            <div className="mt-2">
              <div className="font-semibold">Notes</div>
              <ul className="list-disc ml-6 space-y-1">
                {result.notes.map((n:string,i:number)=> <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
