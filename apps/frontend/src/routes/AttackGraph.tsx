import React, { useEffect, useState } from 'react';
const apiBase = import.meta.env.VITE_API_BASE || '';

type Graph = { nodes: any[], edges: any[] };

export default function AttackGraph(){
  const [g, setG] = useState<Graph>({nodes:[], edges:[]});
  const load = async()=>{
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN');
    try{ const r = await fetch(apiBase + '/graph', { headers: { ...(tok? { Authorization: 'Bearer ' + tok } : {}) } }); const j = await r.json(); setG(j); }catch{}
  };
  useEffect(()=>{ load(); },[]);
  return (
    <div className='space-y-3'>
      <h2 className='text-xl font-semibold text-purple-300'>Attack Graph</h2>
      <div className='grid grid-cols-12 gap-3'>
        <div className='col-span-4 p-3 bg-slate-950/60 rounded border border-slate-800'>
          <div className='text-slate-300'>Nodes: <span className='text-cyan-300'>{g.nodes?.length||0}</span></div>
          <div className='text-slate-300'>Edges: <span className='text-cyan-300'>{g.edges?.length||0}</span></div>
          <ul className='mt-2 h-60 overflow-auto text-xs text-slate-300'>
            {(g.nodes||[]).slice(0,100).map((n:any,i:number)=> (<li key={i} className='border-b border-slate-800 py-1'>{n.id||n.name||JSON.stringify(n)}</li>))}
          </ul>
        </div>
        <div className='col-span-8 p-3 bg-slate-950/60 rounded border border-slate-800 h-[60vh] relative'>
          <div className='absolute inset-0 scanline' />
          <div className='absolute inset-0 flex items-center justify-center text-slate-500'>Force-graph view coming next (WS metrics + cytoscape)</div>
        </div>
      </div>
    </div>
  );
}
