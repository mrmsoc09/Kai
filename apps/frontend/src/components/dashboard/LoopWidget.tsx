
import React from 'react'
import LoopIcon from '../icons/LoopIcon'
import StatusBadge from '../StatusBadge'
import type { SystemState } from '../../api/types'

export default function LoopWidget({system}:{system?: SystemState}){
  const s = system?.loop
  const gpee = s?.strategic?.name || 'Plan'
  const ooda = s?.tactical?.name || 'Orient'
  const active = ooda==='Decide' || ooda==='Act'
  return <div className='widget pulse' data-active={active}> 
    <div className='widget-title'>System Loop</div>
    <div className='row' style={{alignItems:'center', justifyContent:'space-between'}}>
      <div className='row'>
        <LoopIcon className='icon blue'/>
        <div className='loop-ring'>{gpee}</div>
      </div>
      <div className='ooda'>
        {['Observe','Orient','Decide','Act'].map(step=> <span key={step} className={'step '+(step===ooda? 'active':'')}>{step}</span>)}
      </div>
    </div>
  </div>
}
