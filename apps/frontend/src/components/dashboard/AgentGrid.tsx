
import React, { useEffect, useState } from 'react'
import api from '../../api/client'
import AgentIcon from '../icons/AgentIcon'
import type { AgentState } from '../../api/types'

const colorFor = (status?:string)=>{
  if(status==='active') return 'green'
  if(status==='paused') return 'orange'
  if(status==='inactive') return 'gray'
  if(status==='error') return 'red'
  return 'blue'
}

export default function AgentGrid(){
  const [agents, setAgents] = useState<AgentState[]>([])
  useEffect(()=>{ api.get('/state/agents').then(r=> setAgents(r.data)).catch(()=>{}) },[])
  return <div className='widget'>
    <div className='widget-title'>Active Units</div>
    <div className='agent-grid'>
      {agents.map(a=> <div key={a.id} className='agent-card'>
        <div className='agent-name'><AgentIcon className={'icon '+colorFor(a.status)} /> {a.name}</div>
        <div className='agent-status'>{a.role} — {a.status}</div>
      </div>)}
    </div>
  </div>
}
