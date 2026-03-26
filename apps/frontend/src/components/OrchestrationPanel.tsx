/**
 * Kaison Composer Link widget.
 * Shows orchestration relay status in the dashboard sidebar.
 *
 * Orchestration is handled by Gemini CLI. See orchestration/gemini_orchestrator.py.
 */
import React from 'react'
import NeonChip from './common/NeonChip'

export default function OrchestrationPanel() {
  const callsign = 'Kaison Composer — Spectre-1'
  const mode = 'HiL Relay'
  const inbound = 'Routed via Orchestration'
  const outbound = 'Routed via Orchestration'
  return (
    <div className='widget'>
      <div className='widget-title'>Kaison Composer Link</div>
      <div className='row' style={{ gap: 8, flexWrap: 'wrap' }}>
        <NeonChip color='purple'>{callsign}</NeonChip>
        <NeonChip color='teal'>{mode}</NeonChip>
        <NeonChip color='cyan'>Inbound: {inbound}</NeonChip>
        <NeonChip color='cyan'>Outbound: {outbound}</NeonChip>
      </div>
      <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>
        All communications in/out traverse Kaison Composer HiL relay. Scope and governance policies enforced here.
      </div>
    </div>
  )
}
