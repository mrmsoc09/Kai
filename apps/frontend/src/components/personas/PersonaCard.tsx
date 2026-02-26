
import React from 'react'
import type { Persona } from '../../api/types'
import Sparkline from './Sparkline'

function fmtDate(s:string){ try{ const d = new Date(s); return d.toLocaleDateString() }catch{ return s } }

export default function PersonaCard({p}:{p: Persona}){
  return <div className='persona-card'>
    <div className='persona-head'>
      <div className='role'>{p.role}</div>
      <div className='plan'>{p.plan}</div>
    </div>
    <div className='statline'>
      <div className='meta'>
        <span className='k1-chip mem'>Obsidian vault</span>
        <span className='k1-chip ing'>Distilled ingest</span>
        <span className='k1-chip maturity'>{p.maturity}</span>
      </div>
      <Sparkline values={p.confidence_trend} />
    </div>
    <div className='statline'>
      <div className='stat'>Knowledge: <strong>{p.knowledge_count}</strong></div>
      <div className='stat'>Last update: <strong>{fmtDate(p.last_training_update)}</strong></div>
    </div>
  </div>
}
