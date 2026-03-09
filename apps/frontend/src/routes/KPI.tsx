import React, { useEffect, useState } from 'react'
import { COLORS } from '@/theme/branding'

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
  const [placeholder, setPlaceholder] = useState(false)

  useEffect(() => {
    fetch('/metrics/kpi', { headers: { Accept: 'application/json' } })
      .then(async (r) => {
        const contentType = r.headers.get('content-type') || ''
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        if (!contentType.includes('application/json')) {
          throw new Error('Backend returned non-JSON (check proxy/back-end).')
        }
        return r.json()
      })
      .then(setSnapshot)
      .catch((e) => {
        setError(String(e))
        setPlaceholder(true)
        setSnapshot({
          generated_at: new Date().toISOString(),
          reports_submitted: 0,
          reports_accepted: 0,
          reports_rejected: 0,
          acceptance_rate: 0,
          duplicate_events: 0,
          duplicate_rate: 0,
          throughput_reports_per_week: 0,
          payouts: { gross_amount: 0, fees: 0, net_amount: 0 },
        })
      })
  }, [])

  if (!snapshot) return <div style={{ color: COLORS.textSecondary, padding: '2rem' }}>Loading KPI snapshot…</div>

  const rejectionRate = snapshot.reports_submitted
    ? (snapshot.reports_rejected / snapshot.reports_submitted)
    : 0
  const netMargin = snapshot.payouts.gross_amount
    ? snapshot.payouts.net_amount / snapshot.payouts.gross_amount
    : 0

  return (
    <div style={{ display: 'grid', gap: 16 }}>
      <div style={{ padding: '16px', border: `2px solid ${COLORS.border}`, borderRadius: 12, background: COLORS.surface }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h2 style={{ margin: 0, color: COLORS.text }}>KPI Dashboard</h2>
            <p style={{ opacity: 0.8, color: COLORS.textSecondary, marginTop: 6 }}>
              Generated: {new Date(snapshot.generated_at).toLocaleString()}
            </p>
            {placeholder && (
              <p style={{ color: COLORS.status.high, fontSize: '0.8rem', marginTop: 6 }}>
                Backend KPI feed unavailable. Showing placeholder structure.
              </p>
            )}
            {error && (
              <p style={{ color: COLORS.status.critical, fontSize: '0.75rem', marginTop: 4 }}>
                {error}
              </p>
            )}
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <a className='btn btn-secondary' href='/metrics/kpi/export.csv' target='_blank' rel='noreferrer'>
              Export KPI CSV
            </a>
          </div>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))', gap:12 }}>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Reports Submitted</strong>
          <div style={{ fontSize: '1.6rem' }}>{snapshot.reports_submitted}</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Reports Accepted</strong>
          <div style={{ fontSize: '1.6rem' }}>{snapshot.reports_accepted}</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Acceptance Rate</strong>
          <div style={{ fontSize: '1.6rem' }}>{(snapshot.acceptance_rate * 100).toFixed(2)}%</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Rejection Rate</strong>
          <div style={{ fontSize: '1.6rem' }}>{(rejectionRate * 100).toFixed(2)}%</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Duplicate Rate</strong>
          <div style={{ fontSize: '1.6rem' }}>{(snapshot.duplicate_rate * 100).toFixed(2)}%</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Throughput / Week</strong>
          <div style={{ fontSize: '1.6rem' }}>{snapshot.throughput_reports_per_week.toFixed(2)}</div>
        </div>
      </div>

      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(260px,1fr))', gap:12 }}>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Payouts (Gross)</strong>
          <div style={{ fontSize: '1.4rem', color: COLORS.status.high }}>${snapshot.payouts.gross_amount.toFixed(2)}</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Fees</strong>
          <div style={{ fontSize: '1.4rem', color: COLORS.status.critical }}>${snapshot.payouts.fees.toFixed(2)}</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Net Payout</strong>
          <div style={{ fontSize: '1.4rem', color: COLORS.primary.main }}>${snapshot.payouts.net_amount.toFixed(2)}</div>
          <div style={{ fontSize: '0.75rem', color: COLORS.textSecondary }}>Net margin {(netMargin * 100).toFixed(1)}%</div>
        </div>
        <div style={{ padding: 12, border: `2px solid ${COLORS.border}`, borderRadius: 10, background: COLORS.surface }}>
          <strong>Duplicate Events</strong>
          <div style={{ fontSize: '1.4rem' }}>{snapshot.duplicate_events}</div>
        </div>
      </div>
    </div>
  )
}
