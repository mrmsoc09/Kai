
import React, { useState } from 'react';
import { api } from '../lib/api';

const examples = ['TA0043:T1593','TA0043:T1595','TA0005:T1562.001','TA0010:T1048.003'];

export default function Plans(){
  const [technique, setTechnique] = useState(examples[0]);
  const [plan, setPlan] = useState<any>(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  const runPlan = async ()=>{
    setErr(''); setBusy(true);
    try{
      const r = await api.post('/planner/plan', { technique_id: technique });
      setPlan(r.data.plan);
    }catch(e:any){ setErr(String(e)); }
    finally{ setBusy(false); }
  };

  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-teal-300'>MITRE Planner (Plan-Mode)</h2>
      <div className='flex gap-3 items-end'>
        <div className='flex items-center gap-2'>
          <input className='bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono w-[280px]' value={technique} onChange={e=>setTechnique(e.target.value)} />
          <select className='bg-slate-900 border border-slate-700 rounded px-2 py-1' value={technique} onChange={e=>setTechnique(e.target.value)}>
            {examples.map(ex => <option key={ex} value={ex}>{ex}</option>)}
          </select>
        </div>
        <button onClick={runPlan} disabled={busy} className='px-3 py-2 rounded bg-teal-600 hover:bg-teal-500 disabled:opacity-50'>Generate Plan</button>
        <button disabled className='px-3 py-2 rounded bg-amber-700/60 opacity-60' title='Execution disabled by policy'>Execute (HiL required)</button>
      </div>
      {err && <div className='text-amber-400'>{err}</div>}
      {plan && (
        <div className='p-3 bg-slate-950/60 rounded border border-slate-800 space-y-2'>
          <div>Technique: <span className='font-mono'>{plan.technique_id}</span></div>
          <div>Risk: <span className={`font-mono ${plan.risk_category==='blocked'?'text-amber-400':'text-emerald-400'}`}>{plan.risk_category}</span></div>
          <div>HiL Required: <span className='font-mono'>{String(plan.hil_required)}</span></div>
          <div>
            <div className='font-semibold'>Steps</div>
            <ol className='list-decimal ml-6 space-y-1'>
              {plan.steps?.map((s:any)=> <li key={s.id}><span className='font-mono text-xs opacity-70'>[{s.type}]</span> {s.action}</li>)}
            </ol>
          </div>
          {!!(plan.notes?.length) && (
            <div>
              <div className='font-semibold'>Notes</div>
              <ul className='list-disc ml-6 space-y-1'>
                {plan.notes.map((n:string,i:number)=> <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
