
import React from 'react'
import type { ReasoningSummary } from '../../api/types'

export default function SummaryPanel({data}:{data: ReasoningSummary|null}){
  if(!data) return <div className='log-panel'>No summary</div>
  return <div className='log-panel'>
    <div style={{fontSize:13, color:'var(--text-primary)', marginBottom:6}}>{data.title}</div>
    <ul className='summary-list'>
      {data.bullets.map((b,i)=> <li key={i}>• {b}</li>)}
    </ul>
  </div>
}
