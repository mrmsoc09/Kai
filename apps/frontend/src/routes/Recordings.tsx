import React, { useEffect, useState } from 'react';
const apiBase = import.meta.env.VITE_API_BASE || '';

export default function Recordings(){
  const [runId, setRunId] = useState('demo-run-001');
  const [list, setList] = useState<any[]>([]);
  const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
  const headers:any = tok? { Authorization: 'Bearer ' + tok } : {};
  const load = async()=>{
    const r = await fetch(apiBase + '/recordings/list?run_id=' + encodeURIComponent(runId), { headers });
    const j = await r.json(); setList(j.segments||[]);
  };
  const start = async()=>{ await fetch(apiBase + '/recordings/start', { method:'POST', headers: { 'Content-Type':'application/json', ...headers }, body: JSON.stringify({ run_id: runId })}); load(); };
  const stop = async()=>{ await fetch(apiBase + '/recordings/stop', { method:'POST', headers: { 'Content-Type':'application/json', ...headers }, body: JSON.stringify({ run_id: runId })}); load(); };
  useEffect(()=>{ load(); },[]);
  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-cyan-300'>Screen Recordings</h2>
      <div className='flex gap-2 items-end'>
        <div>
          <label className='block text-sm text-slate-400'>Run ID</label>
          <input value={runId} onChange={e=>setRunId(e.target.value)} className='bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
        </div>
        <button onClick={start} className='px-3 py-2 rounded bg-cyan-600 hover:bg-cyan-500'>Start Segment</button>
        <button onClick={stop} className='px-3 py-2 rounded bg-purple-600 hover:bg-purple-500'>Stop Segment</button>
      </div>
      <div className='p-3 bg-slate-950/60 rounded border border-slate-800'>
        <table className='w-full text-sm'>
          <thead className='text-slate-400'><tr><th className='text-left'>Label</th><th>Started</th><th>Stopped</th><th>Video</th></tr></thead>
          <tbody>
            {list.map((s,i)=> (
              <tr key={i} className='border-t border-slate-800'>
                <td className='py-1 text-slate-200'>{s.label}</td>
                <td className='py-1 text-slate-400'>{s.started_at}</td>
                <td className='py-1 text-slate-400'>{s.stopped_at||'-'}</td>
                <td className='py-1'><code className='text-xs'>{s.video_path}</code></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
