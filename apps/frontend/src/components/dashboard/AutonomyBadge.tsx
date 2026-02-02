
import React from 'react'
import ShieldIcon from '../icons/ShieldIcon'

export default function AutonomyBadge({tier}:{tier?: number}){
  const t = tier ?? 0
  const cls = t>=3? 'tier3' : t===2? 'tier2' : t===1? 'tier1' : 'tier0'
  const label = t>=3? 'HARD_STOP' : t===2? 'APPROVE' : t===1? 'NOTIFY' : 'AUTO'
  return <div className={'widget auto '+cls}>
    <div className='widget-title'>Autonomy</div>
    <div className='row'>
      <ShieldIcon className='icon blue' />
      <span className='badge'>{label} (T{t})</span>
    </div>
  </div>
}
