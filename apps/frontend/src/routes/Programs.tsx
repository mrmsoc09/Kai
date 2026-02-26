import React from 'react'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getTop50, queuePlan, type BBPProgram } from '../api/programs'
import StatusChip from '../components/StatusChip'

export default function Programs(){
  const navigate = useNavigate()
  const [validation, setValidation] = useState<Record<string, boolean>>({})
  useEffect(()=>{ fetch('/programs/bbp/validation').then(r=>r.json()).then(setValidation).catch(()=>setValidation({})) },[])

  const [items, setItems] = useState<BBPProgram[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string|undefined>(undefined)
  const [target, setTarget] = useState('example.com')
  const [chain, setChain] = useState<string>('default_chain')
  const [msg, setMsg] = useState<string>('')
  const [sortKey, setSortKey] = useState<'payout'|'name'>('payout')

  useEffect(()=>{
    let live = true
    setLoading(true)
    getTop50().then(d=>{ if(!live) return; setItems(d.programs||[]); setLoading(false) }).catch(e=>{ if(!live) return; setError(String(e)); setLoading(false) })
    return ()=>{ live=false }
  }, [])

  async function onQueue(){
    setMsg('Queuing plan run...')
    try{
      const r = await queuePlan(target, chain, true)
      setMsg(`Queued job ${r?.job?.id || ''}; auto_run: ${r?.auto_run?.status || ''}`)
      try { if(r?.auto_run?.run_id){ localStorage.setItem('LAST_RUN_ID', r.auto_run.run_id) } } catch(_) {}
      try { navigate('/runs') } catch(_) {}
    }catch(e:any){ setMsg('Error: '+ String(e?.message || e)) }
  }

  return <div className='panel'>
    <div className='widget-title'>Bug Bounty Programs — Top 50</div>
    <div className='row' style={{gap:12, alignItems:'center'}}>
      <input value={target} onChange={e=> setTarget(e.target.value)} placeholder='target domain (e.g., example.com)' className='input'/>
      <input value={chain} onChange={e=> setChain(e.target.value)} placeholder='chain (optional)' className='input'/>
      <button onClick={onQueue} className='btn primary'>Queue Plan Run</button>
      <span className='muted'>Sort:</span>
      <button className='btn' onClick={()=>setSortKey('payout')}>Payout</button>
      <button className='btn' onClick={()=>setSortKey('name')}>Name</button>
      {msg && <span className='muted'>{msg}</span>}
    </div>

    {loading && <div className='muted'>Loading...</div>}
    {error && <div className='error'>{error}</div>}

    {!loading && !error && (
      <div className='table-wrap'>
        <table className='table'>
          <thead>
            <tr>
              <th>#</th>
              <th>Name</th>
              <th>Platform</th>
              <th>Max Payout</th>
              <th>Fit</th>
              <th>Score</th>
              <th>Links</th>
            </tr>
          </thead>
          <tbody>
            {items.map((p, idx)=>
              <tr key={p.id}>
                <td>{idx+1}</td>
                <td>{p.name} {validation[p.id] ? '✅' : ''}</td>
                <td>{p.platform || ''}</td>
                <td>{p.payout_max_usd ?? ''}</td>
                <td>{(p.exploitability_fit ?? 0).toFixed(3)}</td>
                <td><StatusChip status={(p.priority_score||0) >= 0.66 ? 'high' : (p.priority_score||0) >= 0.33 ? 'med' : 'low'} label={(p.priority_score||0).toFixed(3)}/></td>
                <td>
                  {p.program_url && <a href={p.program_url} target='_blank' rel='noreferrer'>program</a>} {' '}
                  {p.scope_url && <a href={p.scope_url} target='_blank' rel='noreferrer'>scope</a>} {' '}
                  {p.policy_url && <a href={p.policy_url} target='_blank' rel='noreferrer'>policy</a>}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    )}
  </div>
}
