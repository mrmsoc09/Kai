
import React from 'react'

export default function KnowledgeDelta({count}:{count?: number}){
  const c = count||0
  const changed = c>0
  return <div className='widget kdelta pulse' data-active={changed}>
    <div className='widget-title'>Knowledge Δ</div>
    <div className='row' style={{justifyContent:'space-between'}}>
      <div className='count'>{c}</div>
      <div style={{fontSize:12, color:'#8b949e'}}>since last review</div>
    </div>
  </div>
}
