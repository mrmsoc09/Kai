import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

type Chain = { name: string, steps: { query: string }[] };
export default function Recon(){
  const [target, setTarget] = useState('bughunter.withgoogle.com');
  const [chains, setChains] = useState<Chain[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(()=>{
    api.get('/dorks/chains')
      .then(r=> setChains(r.data.chains||[]))
      .catch(()=> setChains([]));
  },[]);

  const runPlan = async ()=>{
    setBusy(true); setResult(null);
    try{
      const r = await api.post('/dorks/run', { target, chain: selected, mode: 'plan', limit: 5 });
      setResult(r.data);
    }catch(err){ setResult({ error: 'failed' }); }
    finally{ setBusy(false); }
  };

  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-cyan-300'>Recon Planner (Google Dorks)</h2>
      <div className='grid grid-cols-12 gap-3'>
        <div className='col-span-4 p-3 bg-slate-950/60 rounded border border-slate-800'>
          <label className='block text-slate-400 text-sm mb-1'>Target</label>
          <input value={target} onChange={e=>setTarget(e.target.value)} className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
          <label className='block text-slate-400 text-sm mt-3 mb-1'>Chain</label>
          <select value={selected} onChange={e=>setSelected(e.target.value)} className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'>
            <option value=''>-- choose --</option>
            {chains.map((c, i)=> (<option key={i} value={c.name}>{c.name}</option>))}
          </select>
          <button onClick={runPlan} disabled={!selected||busy} className='mt-3 px-3 py-2 rounded bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50'>Plan Run</button>
          <p className='text-xs text-slate-400 mt-2'>Plan mode only. Execute requires HiL + policy enable.</p>
        </div>
        <div className='col-span-8 p-3 bg-slate-950/60 rounded border border-slate-800 h-[60vh] overflow-auto'>
          <pre className='text-slate-200 text-xs'>{JSON.stringify(result, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
