import React from 'react'
import NeonChip from './common/NeonChip'
export default function AgentZeroPanel(){
  const callsign = 'Agent Zero — Spectre-1'
  const mode = 'HiL Relay'
  const inbound = 'Routed via A0'
  const outbound = 'Routed via A0'
  return <div className='widget'>
    <div className='widget-title'>Agent Zero Link</div>
    <div className='row' style={{gap:8, flexWrap:'wrap'}}>
      <NeonChip color='purple'>{callsign}</NeonChip>
      <NeonChip color='teal'>{mode}</NeonChip>
      <NeonChip color='cyan'>Inbound: {inbound}</NeonChip>
      <NeonChip color='cyan'>Outbound: {outbound}</NeonChip>
    </div>
    <div style={{marginTop:8, fontSize:12, color:'var(--text-muted)'}}>All communications in/out traverse Agent Zero HiL relay. Scope and governance policies enforced here.</div>
  </div>
}
