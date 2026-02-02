import React, { useEffect, useState } from 'react'
import api from '../api/client'

type RunRec = {
  run_id: string
  module?: string
  target?: string
  mode?: string
  timestamp?: string
  results?: any
}

export default function Runs(){
  const last = (typeof localStorage!=='undefined' && localStorage.getItem('LAST_RUN_ID')) || ''
  const [rows, setRows] = useState<RunRec[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string|undefined>()

  useEffect(()=>{
    let live = true
    setLoading(true)
    api.get('/runs').then(r=>{ if(!live) return; setRows(r.data||[]); setLoading(false) }).catch(e=>{ if(!live) return; setError(String(e)); setLoading(false) })
    return ()=>{ live=false }
  }, [])

  return <div className='panel'>
    <div className='widget-title'>Recent Runs</div>
    {loading && <div className='muted'>Loading...</div>}
    {error && <div className='error'>{error}</div>}
    {!loading && !error && (
      <div className='table-wrap'>
        <table className='table'>
          <thead>
            <tr>
              <th>#</th>
              <th>Run ID</th>
              <th>Target</th>
              <th>Module</th>
              <th>Mode</th>
              <th>Timestamp (UTC)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i)=> (
              <tr key={r.run_id} style={{background: (r.run_id===last?'rgba(0,229,255,0.08)':'transparent')}}>
                <td>{i+1}</td>
                <td>{r.run_id}</td>
                <td>{r.target || ''}</td>
                <td>{r.module || ''}</td>
                <td>{r.mode || ''}</td>
                <td>{r.timestamp || ''}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )}
  </div>
}
