import React, { useEffect, useState } from 'react'

type Snapshot = {
  generated_at: string
  reports_submitted: number
  reports_accepted: number
  reports_rejected: number
  acceptance_rate: number
  duplicate_events: number
  duplicate_rate: number
  throughput_reports_per_week: number
  payouts: {
    gross_amount: number
    fees: number
    net_amount: number
  }
}

export default function KPI(){
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/metrics/kpi')
      .then(r => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then(setSnapshot)
      .catch((e) => setError(String(e)))
  }, [])

  if (error) return <div className='k1-panel'>KPI load failed: {error}</div>
  if (!snapshot) return <div className='k1-panel'>Loading KPI snapshot...</div>

  return (
    <div className='k1-panel'>
      <h2>KPI Dashboard</h2>
      <p style={{opacity: 0.75}}>Generated: {snapshot.generated_at}</p>
      <div style={{display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))', gap:12}}>
        <div className='k1-card'><strong>Reports Submitted</strong><div>{snapshot.reports_submitted}</div></div>
        <div className='k1-card'><strong>Reports Accepted</strong><div>{snapshot.reports_accepted}</div></div>
        <div className='k1-card'><strong>Acceptance Rate</strong><div>{(snapshot.acceptance_rate * 100).toFixed(2)}%</div></div>
        <div className='k1-card'><strong>Duplicate Rate</strong><div>{(snapshot.duplicate_rate * 100).toFixed(2)}%</div></div>
        <div className='k1-card'><strong>Throughput / Week</strong><div>{snapshot.throughput_reports_per_week.toFixed(2)}</div></div>
        <div className='k1-card'><strong>Net Payout</strong><div>${snapshot.payouts.net_amount.toFixed(2)}</div></div>
      </div>
      <a className='btn' href='/metrics/kpi/export.csv' target='_blank' rel='noreferrer' style={{marginTop: 16, display:'inline-block'}}>
        Export KPI CSV
      </a>
    </div>
  )
}
