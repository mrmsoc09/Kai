
import React from 'react'
import CommsIcon from '../icons/CommsIcon'

export default function CommsBadge({status}:{status?: 'OPEN'|'CLOSED'|'BLOCKED'}){
  const st = status || 'CLOSED'
  return <div className={'widget comms '+st}>
    <div className='widget-title'>Comms</div>
    <div className='row'>
      <CommsIcon className='icon blue'/>
      <span className='badge'>{st}</span>
    </div>
  </div>
}
