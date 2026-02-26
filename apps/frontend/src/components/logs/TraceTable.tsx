
import React from 'react'
import type { DecisionTraceEntry } from '../../api/types'

export default function TraceTable({rows}:{rows: DecisionTraceEntry[]}){
  return <table className='log-table' aria-label='Decision trace table'>
    <thead><tr><th>Time</th><th>Loop</th><th>Action</th><th>Outcome</th><th>Score</th><th>Category</th></tr></thead>
    <tbody>
      {rows.map(r=> <tr key={r.id}>
        <td>{new Date(r.ts).toLocaleString()}</td>
        <td>{r.gpee_step}/{r.ooda_step}</td>
        <td>{r.action}</td>
        <td>{r.outcome}</td>
        <td>{typeof r.score==='object'? Object.entries(r.score).map(([k,v])=> `${k}:${v}`).join(' ') : r.score as any}</td>
        <td><span className={'k1-chip cat-'+r.category}>{r.category}</span></td>
      </tr>)}
    </tbody>
  </table>
}
