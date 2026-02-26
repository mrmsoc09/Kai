import React, { useEffect, useState } from 'react';
const apiBase = import.meta.env.VITE_API_BASE || '';

export default function ReportBuilder(){
  const [formats, setFormats] = useState<any[]>([]);
  const [fmt, setFmt] = useState('google_vrp');
  const [runId, setRunId] = useState('demo-run-001');
  const [content, setContent] = useState('');
  const [mitigation, setMitigation] = useState('Apply input validation and parameterized queries.');
  const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
  const headers:any = tok? { Authorization: 'Bearer ' + tok } : {};

  useEffect(()=>{
    fetch(apiBase + '/reports/formats', { headers }).then(r=>r.json()).then(j=> setFormats(j.formats||[]));
  },[]);

  const render = async()=>{
    const payload = { format_id: fmt, finding: { title:'Demo Finding', severity:'medium', impact:'Data exposure', summary:'...', scope:'demo', references:[] }, evidence: { repro:'1) ... 2) ...', artifacts: {} }, mitigation: { plan: mitigation, timeline: 'ASAP' } };
    const r = await fetch(apiBase + '/reports/render', { method:'POST', headers: { 'Content-Type':'application/json', ...headers }, body: JSON.stringify(payload)});
    const j = await r.json(); setContent(j.content||'');
  };

  const finalize = async()=>{
    const payload = { run_id: runId, mitigation: { plan: mitigation, timeline: 'ASAP' }, duplicate_check: { status: 'clear' } };
    const r = await fetch(apiBase + '/reports/finalize', { method:'POST', headers: { 'Content-Type':'application/json', ...headers }, body: JSON.stringify(payload)});
    if(!r.ok){ alert('Finalize blocked: ' + (await r.text())); } else { alert('Ready for HiL review.'); }
  };

  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-purple-300'>Report Builder</h2>
      <div className='grid grid-cols-12 gap-3'>
        <div className='col-span-4 p-3 bg-slate-950/60 rounded border border-slate-800'>
          <label className='block text-sm text-slate-400'>Format</label>
          <select value={fmt} onChange={e=>setFmt(e.target.value)} className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'>
            {formats.map((f:any)=> (<option key={f.id} value={f.id}>{f.name}</option>))}
          </select>
          <label className='block text-sm text-slate-400 mt-3'>Run ID</label>
          <input value={runId} onChange={e=>setRunId(e.target.value)} className='w-full bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
          <label className='block text-sm text-slate-400 mt-3'>Mitigation Plan</label>
          <textarea value={mitigation} onChange={e=>setMitigation(e.target.value)} className='w-full h-32 bg-slate-900 border border-slate-700 rounded px-2 py-1'/>
          <div className='mt-3 flex gap-2'>
            <button onClick={render} className='px-3 py-2 rounded bg-cyan-600 hover:bg-cyan-500'>Render Draft</button>
            <button onClick={finalize} className='px-3 py-2 rounded bg-orange-600 hover:bg-orange-500'>Finalize (HiL)</button>
          </div>
          <p className='text-xs text-slate-400 mt-2'>Finalize requires a screen recording linked to the run.</p>
        </div>
        <div className='col-span-8 p-3 bg-slate-950/60 rounded border border-slate-800 h-[60vh] overflow-auto'>
          <pre className='text-xs text-slate-200 whitespace-pre-wrap'>{content}</pre>
        </div>
      </div>
    </div>
  );
}
