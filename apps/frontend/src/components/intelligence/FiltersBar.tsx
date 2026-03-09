
import React from 'react'
import type { ChainPotential, Stage } from '../../api/types'

type Props = { stage: Stage|null, onStage: (s: Stage|null)=>void, chain: ChainPotential|null, onChain: (c: ChainPotential|null)=>void }

export default function FiltersBar({stage, onStage, chain, onChain}: Props){
  const stages: (Stage|null)[] = [null,'discovered','validated','exploited','mitigated']
  const chains: (ChainPotential|null)[] = [null,'low','medium','high']
  return <div className='intel-controls'>
    <div className='segment'>
      {stages.map(s=> <button key={String(s)} className={s===stage? 'active':''} onClick={()=> onStage(s)}>{s? s: 'all stages'}</button>)}
    </div>
    <div style={{display:'grid',gap:6}}>
      <label style={{fontSize:12, color:'#8b949e'}}>Chain potential</label>
      <select value={chain||''} onChange={e=> onChain((e.target.value||null) as any)} style={{background:'#0b0c0d',color:'#8FAF9B',border:'1px solid #202326',padding:'8px',borderRadius:6}}>
        {chains.map(c=> <option key={String(c)} value={c||''}>{c? c: 'all'}</option>)}
      </select>
    </div>
  </div>
}
