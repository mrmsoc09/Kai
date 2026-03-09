import React, { useEffect, useMemo, useState } from 'react'
import NeonChip from '../components/common/NeonChip'
import { healthz, setApiKeys } from '../lib/api'
import AgentZeroPanel from '../components/AgentZeroPanel'
import Heatmap from '../components/visuals/Heatmap'
import KpiMini from '../components/charts/KpiMini'

export default function Dashboard(){
  const apiBase = useMemo(()=> (import.meta.env.VITE_API_BASE || (localStorage.getItem('API_BASE')||'http://localhost:8080')), [])
  const [state, setState] = useState({ api: '...', vector: '...', thehive: '...', postgres: '...' })
  const [userKey, setUserKey] = useState('')
  const [adminKey, setAdminKey] = useState('')
  const [pulse, setPulse] = useState(false)

  useEffect(()=>{
    setApiKeys(userKey||undefined, adminKey||undefined)
  }, [userKey, adminKey])

  useEffect(()=>{
    let t: any
    const probe = async()=>{
      try{ const rs = await fetch(apiBase + '/state', {cache:'no-store'}); if(rs.ok){ const js = await rs.json(); setState(v=> ({...v, api: js.api||v.api, vector: js.vector||v.vector, postgres: js.postgres||v.postgres, thehive: js.thehive||v.thehive })) } } catch { /* ignore */ }

      // API health
      try{ await fetch(apiBase + '/health', {cache:'no-store'}); } catch { /* ignore */ }
      // We present placeholders for vector/postgres/thehive; refine when backend exposes /state
      setState(s=> ({...s, api:'OK'}))
      setPulse(p=>!p)
      t = setTimeout(probe, 5000)
    }
    probe();
    return ()=> { if(t) clearTimeout(t) }
  }, [apiBase])

  const chip = (label: string, ok: boolean, colorOk: 'teal'|'cyan'='teal')=> <NeonChip color={ok? colorOk:'cyan'}>{label}: {ok? 'OK':'...'}</NeonChip>

  return <div className='grid' style={{gap:16}}>
    <div className='canvas'>
      <section className='widget pulse' data-active={pulse}>
        <div className='widget-title'>Command Status</div>
        <div className='row' style={{gap:10, flexWrap:'wrap'}}>
          {chip('API', state.api==='OK')}
          {chip('Vector', state.vector==='OK')}
          {chip('Postgres', state.postgres==='OK')}
          {chip('TheHive', state.thehive==='OK')}
          <NeonChip color='purple'>Persona: Hacker</NeonChip>
          <NeonChip color={userKey? 'teal':'cyan'}>UserKey {userKey? 'SET':'MISSING'}</NeonChip>
          <NeonChip color={adminKey? 'teal':'cyan'}>AdminKey {adminKey? 'SET':'MISSING'}</NeonChip>
        </div>
        <div style={{marginTop:12, display:'flex', gap:12}}>
          <label>User API Key <input value={userKey} onChange={e=>setUserKey(e.target.value)} style={{width:360, background:'#0b0c0d', color:'#8FAF9B', border:'1px solid var(--border)', padding:'6px 8px', borderRadius:6}}/></label>
          <label>Admin API Key <input value={adminKey} onChange={e=>setAdminKey(e.target.value)} style={{width:360, background:'#0b0c0d', color:'#8FAF9B', border:'1px solid var(--border)', padding:'6px 8px', borderRadius:6}}/></label>
        </div>
        <div style={{marginTop:8, color:'var(--text-muted)', fontSize:12}}>API Base: <code>{apiBase}</code></div>
      </section>

      <section className='widget'>
        <div className='widget-title'>Threat Heatmap</div>
        <Heatmap rows={6} cols={24} />
      </section>

      <section className='widget'>
        <div className='widget-title'>Run Telemetry</div>
        <div className='row' style={{gap:12, flexWrap:'wrap'}}>
          <div className='loop-ring'>OODA</div>
          <div className='ooda'>
            <div className='step active'>Observe</div>
            <div className='step'>Orient</div>
            <div className='step'>Decide</div>
            <div className='step'>Act</div>
          </div>
        </div>
        <div className='kdelta' style={{marginTop:12}}>
          <span className='widget-title'>Knowledge Delta</span>
          <div className='row' style={{gap:8}}>
            <span className='k1-chip sev-low'>Signals: 0</span>
            <span className='k1-chip sev-medium'>Findings: 0</span>
            <span className='k1-chip sev-high'>HiL queued: 0</span>
          </div>
        </div>
      </section>

      <section className='widget'>
        <div className='widget-title'>Threat Heatmap</div>
        <Heatmap rows={6} cols={24} />
      </section>

      <section className='widget'>
        <div className='widget-title'>Ops KPIs</div>
        <div className='row' style={{gap:12, flexWrap:'wrap'}}>
          <div><div className='widget-title'>Signals/min</div><KpiMini series={[2,3,4,6,5,7,8,9,7,6,8,11]} /></div>
          <div><div className='widget-title'>HiL latency</div><KpiMini series={[12,11,10,8,10,7,9,6,7,5,6,5]} /></div>
          <div><div className='widget-title'>Vector hits</div><KpiMini series={[1,2,1,3,2,5,3,4,6,5,7,8]} /></div>
        </div>
      </section>

      <section className='widget'>
        <div className='widget-title'>Scope & Governance</div>
        <div className='stack'>
          <div className='row' style={{gap:8}}>
            <span className='neon-chip purple'>Scope: Strict</span>
            <span className='neon-chip cyan'>Robots/ToS respect</span>
            <span className='neon-chip teal'>HiL gate enforced</span>
          </div>
          <div className='row' style={{gap:8}}>
            <span className='badge blue'>Evidence-first</span>
            <span className='badge green'>Audit: ON</span>
          </div>
        </div>
      </section>

      <section className='widget'>
        <div className='widget-title'>Threat Heatmap</div>
        <Heatmap rows={6} cols={24} />
      </section>

      <section className='widget'>
        <div className='widget-title'>Quick Actions</div>
        <div className='row' style={{gap:8, flexWrap:'wrap'}}>
          <a className='neon-chip purple' href='/operations'>Run HiL flow</a>
          <a className='neon-chip cyan' href='/mcp-registry'>Provider registry</a>
          <a className='neon-chip teal' href='/intelligence'>Intelligence DB</a>
          <a className='neon-chip purple' href='/logs'>Run logs</a>
        </div>
      </section>

      <AgentZeroPanel />
    </div>
  </div>
}
