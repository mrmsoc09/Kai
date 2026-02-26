import React, { useEffect, useState } from 'react';

const apiBase = import.meta.env.VITE_API_BASE || '';

type Entry = { ts:number, source:string, text:string, client?:string };

export default function AgentZero(){
  const [logs, setLogs] = useState<Entry[]>([]);
  const load = async()=>{
    try{ const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
    const r = await fetch(apiBase + '/agent0/logs', { headers: { ...(tok? { Authorization: 'Bearer ' + tok } : {}) } }); const j = await r.json(); setLogs(j.logs||[]); }catch{}
  };
  useEffect(()=>{ load(); const id = setInterval(load, 5000); return ()=> clearInterval(id); },[]);
  return (
    <div className='h-full'>
      <h2 className='text-xl mb-2 font-semibold text-purple-300'>Agent Zero Communications</h2>
      <div className='grid grid-cols-12 gap-4'>
        <div className='col-span-7 p-3 bg-slate-950/60 rounded border border-slate-800 h-[70vh] overflow-auto'>
          <table className='w-full text-sm'>
            <thead className='text-slate-400'><tr><th className='text-left'>Time</th><th className='text-left'>Client</th><th className='text-left'>Text</th></tr></thead>
            <tbody>
              {logs.map((e,i)=> (
                <tr key={i} className='border-t border-slate-800'>
                  <td className='py-1 pr-2 text-slate-300'>{new Date(e.ts).toLocaleString()}</td>
                  <td className='py-1 pr-2 text-slate-400'>{e.client||'n/a'}</td>
                  <td className='py-1 text-slate-200'>{e.text}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className='col-span-5 space-y-3'>
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400'>Policy</h3>
            <p className='text-slate-300 text-sm'>Human-in-the-Loop required for all external comms and submissions. Agent Zero is the single gateway.</p>
          </section>
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400'>Status</h3>
            <ul className='text-slate-200 text-sm'>
              <li>Relay: <span className='text-cyan-300'>Auto-detect</span></li>
              <li>Audit: <span className='text-cyan-300'>Merkle logged</span></li>
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
