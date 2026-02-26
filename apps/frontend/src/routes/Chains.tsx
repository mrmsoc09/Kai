import React, { useState } from 'react';
const apiBase = import.meta.env.VITE_API_BASE || '';
export default function Chains(){
  const [findingsJson, setFindingsJson] = useState('[\n  {"id":"F1","assets":["app"],"severity_score":2},\n  {"id":"F2","assets":["app"],"severity_score":3},\n  {"id":"F3","assets":["api"],"severity_score":2}\n]');
  const [chains, setChains] = useState<any[]>([]);
  const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
  const headers:any = tok? { Authorization: 'Bearer ' + tok } : {};
  const propose = async()=>{
    const r = await fetch(apiBase + '/chains/propose', { method:'POST', headers: { 'Content-Type':'application/json', ...headers }, body: JSON.stringify({ findings: JSON.parse(findingsJson) })});
    const j = await r.json(); setChains(j.chains||[]);
  };
  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-cyan-300'>Chain Builder</h2>
      <div className='grid grid-cols-12 gap-3'>
        <div className='col-span-5 p-3 bg-slate-950/60 rounded border border-slate-800'>
          <label className='block text-sm text-slate-400 mb-1'>Findings JSON</label>
          <textarea value={findingsJson} onChange={e=>setFindingsJson(e.target.value)} className='w-full h-64 bg-slate-900 border border-slate-700 rounded px-2 py-1 font-mono text-xs'/>
          <button onClick={propose} className='mt-3 px-3 py-2 rounded bg-cyan-600 hover:bg-cyan-500'>Propose Chains</button>
        </div>
        <div className='col-span-7 p-3 bg-slate-950/60 rounded border border-slate-800 h-[60vh] overflow-auto'>
          <pre className='text-xs text-slate-200'>{JSON.stringify(chains, null, 2)}</pre>
        </div>
      </div>
    </div>
  );
}
