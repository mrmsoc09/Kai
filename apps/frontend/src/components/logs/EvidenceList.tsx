
import React from 'react'
import type { EvidenceLink } from '../../api/types'

export default function EvidenceList({rows}:{rows: EvidenceLink[]}){
  return <div className='evidence-list' aria-label='Evidence links'>
    {rows.map(e=> <div className='evidence-item' key={e.id}>
      <div>
        <div style={{fontSize:13}}>{e.label}</div>
        <div style={{fontSize:11, color:'#8b949e'}}>{e.path}</div>
      </div>
      <span className='k1-chip cat-evidence'>{e.artifact_type}</span>
    </div>)}
  </div>
}
