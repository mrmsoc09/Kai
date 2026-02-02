
import React from 'react'
import type { KnowledgeDeltaEntry } from '../../api/types'

export default function KnowledgeList({rows}:{rows: KnowledgeDeltaEntry[]}){
  return <div className='kdelta' aria-label='Knowledge delta'>
    {rows.map(k=> <div key={k.id} className='log-panel'>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <div style={{fontSize:13}}>{k.summary}</div>
        <span className='k1-chip cat-learning'>Impact {k.impact_score}</span>
      </div>
      <div style={{fontSize:11, color:'#8b949e'}}>Applies to: {k.applies_to.join(', ')}</div>
    </div>)}
  </div>
}
