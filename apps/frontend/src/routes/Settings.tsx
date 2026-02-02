import React, { useEffect, useState } from 'react';
export default function Settings(){
  const [api, setApi] = useState('');
  const [tok, setTok] = useState('');
  useEffect(()=>{ setApi(localStorage.getItem('api_base')||''); setTok(localStorage.getItem('k1_token')||localStorage.getItem('K1_DEV_TOKEN')||''); },[]);
  const save = ()=>{
    if(api) localStorage.setItem('api_base', api);
    if(tok) { localStorage.setItem('k1_token', tok); localStorage.setItem('K1_DEV_TOKEN', tok); }
    alert('Saved. Refresh the app to apply API base env if needed.');
  };
  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-orange-300'>Settings</h2>
      <div className='grid grid-cols-12 gap-3'>
        <div className='col-span-6 p-3 bg-slate-950/60 rounded border border-slate-800'>
          <label className='block text-slate-400 text-sm mb-1'>API Base</label>
          <input value={api} onChange={e=>setApi(e.target.value)} placeholder='http://localhost:8080' className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
          <label className='block text-slate-400 text-sm mt-3 mb-1'>Bearer Token</label>
          <input value={tok} onChange={e=>setTok(e.target.value)} placeholder='devtoken123' className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
          <button onClick={save} className='mt-3 px-3 py-2 rounded bg-orange-600 hover:bg-orange-500'>Save</button>
          <p className='text-xs text-slate-400 mt-2'>Token is used in Authorization header for protected endpoints.</p>
        </div>
      </div>
    </div>
  );
}


function ProviderDiagnostics(){
  const [cfg, setCfg] = React.useState<any>(null);
  const [err, setErr] = React.useState<string>('');
  React.useEffect(()=>{
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || '';
    fetch('/state/config', { headers: { 'Authorization': tok? ('Bearer ' + tok): '' }})
      .then(r=>{ if(!r.ok) throw new Error(String(r.status)); return r.json(); })
      .then(setCfg)
      .catch(e=> setErr(String(e)));
  }, []);
  if(err) return <div className='text-amber-400 mt-3'>Diagnostics error: {err}</div>;
  if(!cfg) return <div className='opacity-70 mt-3'>Loading diagnostics…</div>;
  return (
    <div className='grid grid-cols-12 gap-3 mt-3'>
      <div className='col-span-6 p-3 bg-slate-950/60 rounded border border-slate-800'>
        <div className='font-semibold text-slate-300 mb-2'>Providers / Models</div>
        <div className='grid grid-cols-1 md:grid-cols-2 gap-2'>
          {Object.entries(cfg.providers.models).map(([k,v]: any)=> (
            <div key={k} className={`p-2 rounded border ${v.valid? 'border-emerald-500/40':'border-amber-500/40'} bg-black/30`}>
              <div className='flex justify-between'><span className='font-mono'>{k}</span><span className={`px-2 py-0.5 rounded text-xs ${v.valid? 'bg-emerald-600/40':'bg-amber-600/40'}`}>{v.valid? 'valid':'invalid'}</span></div>
              <div className='opacity-70 text-xs mt-1'>{v.name || 'unset'}</div>
            </div>
          ))}
        </div>
      </div>
      <div className='col-span-6 p-3 bg-slate-950/60 rounded border border-slate-800'>
        <div className='font-semibold text-slate-300 mb-2'>Vector Backend</div>
        <div>Backend: <span className='font-mono'>{cfg.vector.backend}</span></div>
        <div>Memory entries: <span className='font-mono'>{cfg.vector.mem_count}</span></div>
        <div className='mt-2 text-xs text-slate-400'>HiL Gate: <span className='font-mono'>{String(cfg.hil_gate_enforced)}</span>; Scope: <span className='font-mono'>{cfg.scope_policy}</span></div>
      </div>
    </div>
  );
}
