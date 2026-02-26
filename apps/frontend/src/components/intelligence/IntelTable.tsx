
import React from 'react'
import type { Finding } from '../../api/types'

const sevClass = (s:string)=> s==='low'? 'sev-low' : s==='medium'? 'sev-medium' : s==='high'? 'sev-high' : 'sev-critical'
const stageClass = (s:string)=> 'stage-'+s

export default function IntelTable({rows}:{rows: Finding[]}){
  return <div className='intel-grid'>
    <table className='table'>
      <thead>
        <tr>
          <th>Severity</th><th>Type</th><th>Target Asset</th><th>Chain Value</th><th>Status</th><th>Evidence</th><th>Stage</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(r=> <tr key={r.id}>
          <td><span className={'k1-chip '+sevClass(r.severity)}>{r.severity.toUpperCase()}</span></td>
          <td>{r.type}</td>
          <td>{r.target_asset}</td>
          <td><span className='k1-chip'>{r.chain_value}</span></td>
          <td>{r.status.replace('_',' ')}</td>
          <td><div className='progress'><span style={{width: r.evidence_completeness+'%'}}></span></div></td>
          <td><span className={'k1-chip '+stageClass(r.stage)}>{r.stage}</span></td>
        </tr>)}
      </tbody>
    </table>
    {/* Card mode for small screens */}
    {rows.map(r=> <div key={r.id} className='rowcard'>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
        <div style={{display:'flex',gap:8,alignItems:'center'}}>
          <span className={'k1-chip '+sevClass(r.severity)}>{r.severity.toUpperCase()}</span>
          <div style={{fontSize:13}}>{r.type}</div>
        </div>
        <span className={'k1-chip '+stageClass(r.stage)}>{r.stage}</span>
      </div>
      <div style={{fontSize:12, color:'#8b949e'}}>{r.target_asset}</div>
      <div style={{display:'flex',gap:8,alignItems:'center'}}>
        <span className='k1-chip'>Chain {r.chain_value}</span>
        <div className='progress'><span style={{width: r.evidence_completeness+'%'}}></span></div>
      </div>
    </div>)}
  </div>
}
