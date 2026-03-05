import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listWorkflows, transitionWorkflow, deleteWorkflow } from '../lib/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface HuntWorkflow {
  id: string
  opportunity_id: string
  program_name: string
  platform: string
  access_type: string
  status: string
  scope_accepted: boolean
  scope_domains: string[]
  findings_count: number
  created_at: string
  updated_at: string
  transitioned_at: Record<string, string>
  run_ids: string[]
  notes: string
  created_by: string
  allowed_transitions: string[]
  is_terminal: boolean
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ACTIVE_STATES = ['SELECTED', 'SCOPING', 'RECON', 'SCANNING', 'TRIAGE', 'HIL_REVIEW']
const KANBAN_COLS = ['SCOPING', 'RECON', 'SCANNING', 'TRIAGE', 'HIL_REVIEW']

const STATE_LABELS: Record<string, string> = {
  SELECTED: 'Selected', SCOPING: 'Scoping', RECON: 'Recon',
  SCANNING: 'Scanning', TRIAGE: 'Triage', HIL_REVIEW: 'HiL Review',
  SUBMITTED: 'Submitted', CLOSED: 'Closed',
}

// Primary forward action per state
const PRIMARY_ACTION: Record<string, { label: string; to: string }> = {
  SELECTED:   { label: 'Accept Scope →',   to: 'SCOPING' },
  SCOPING:    { label: 'Queue Recon →',    to: 'RECON' },
  RECON:      { label: 'Begin Scanning →', to: 'SCANNING' },
  SCANNING:   { label: 'Move to Triage →', to: 'TRIAGE' },
  TRIAGE:     { label: 'Request Review →', to: 'HIL_REVIEW' },
  HIL_REVIEW: { label: 'Mark Submitted →', to: 'SUBMITTED' },
  SUBMITTED:  { label: 'Close Hunt',       to: 'CLOSED' },
}

const PLATFORM_COLORS: Record<string, string> = {
  hackerone: '#25a244', bugcrowd: '#f97316', intigriti: '#7c3aed',
  vrp: '#2563eb', government_cvd: '#0891b2',
}
const PLATFORM_ABBREV: Record<string, string> = {
  hackerone: 'H1', bugcrowd: 'BC', intigriti: 'INT', vrp: 'VRP', government_cvd: 'GOV',
}

function elapsed(ts: string): string {
  if (!ts) return ''
  const ms = Date.now() - new Date(ts).getTime()
  const m = Math.floor(ms / 60_000)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 48) return `${h}h`
  return `${Math.floor(h / 24)}d`
}

// ─── Kanban Card ──────────────────────────────────────────────────────────────

function WFCard({
  wf, onAction, onClose, actingId,
}: {
  wf: HuntWorkflow
  onAction: (wf: HuntWorkflow, to: string) => void
  onClose: (wf: HuntWorkflow) => void
  actingId: string | null
}) {
  const navigate = useNavigate()
  const pc = PLATFORM_COLORS[wf.platform] || '#4a5568'
  const pa = PRIMARY_ACTION[wf.status]
  const busy = actingId === wf.id
  const canAdvance = pa && wf.allowed_transitions.includes(pa.to)
  const canClose = wf.allowed_transitions.includes('CLOSED') && pa?.to !== 'CLOSED'

  return (
    <div style={{
      background: '#0d1117', border: '1px solid #1e2330', borderRadius: 6,
      padding: '0.75rem 0.85rem', marginBottom: 8,
    }}>
      {/* Program name — click to view opportunity */}
      <div
        onClick={() => navigate(`/opportunities`)}
        title='View opportunities'
        style={{
          color: '#e2e8f0', fontWeight: 600, fontSize: '0.82rem', lineHeight: 1.3,
          cursor: 'pointer', marginBottom: 4,
        }}
        onMouseEnter={e => (e.currentTarget.style.color = '#00FF41')}
        onMouseLeave={e => (e.currentTarget.style.color = '#e2e8f0')}
      >
        {wf.program_name}
      </div>

      {/* Meta row */}
      <div style={{ display: 'flex', gap: 5, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{
          background: `${pc}1a`, color: pc, border: `1px solid ${pc}33`,
          fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
        }}>
          {PLATFORM_ABBREV[wf.platform] || wf.platform}
        </span>
        {wf.findings_count > 0 && (
          <span style={{
            background: 'rgba(0,255,65,0.08)', color: '#00FF41',
            border: '1px solid rgba(0,255,65,0.2)',
            fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          }}>
            {wf.findings_count} finding{wf.findings_count !== 1 ? 's' : ''}
          </span>
        )}
        {wf.run_ids.length > 0 && (
          <span style={{ color: '#4a5568', fontSize: '0.62rem' }}>
            {wf.run_ids.length} run{wf.run_ids.length !== 1 ? 's' : ''}
          </span>
        )}
        <span style={{ color: '#2d3748', fontSize: '0.62rem', marginLeft: 'auto' }}>
          {elapsed(wf.transitioned_at[wf.status])}
        </span>
      </div>

      {/* Action row */}
      <div style={{ display: 'flex', gap: 5 }}>
        {canAdvance && (
          <button
            onClick={() => onAction(wf, pa!.to)}
            disabled={busy}
            style={{
              flex: 1, padding: '4px 8px', borderRadius: 3,
              background: '#00FF41', color: '#0d1117',
              border: 'none', fontFamily: 'inherit', fontSize: '0.68rem', fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
            }}
          >
            {busy ? '…' : pa!.label}
          </button>
        )}
        {wf.status === 'HIL_REVIEW' && (
          <button
            onClick={() => navigate('/operations/approvals')}
            style={{
              padding: '4px 8px', borderRadius: 3, background: 'transparent',
              color: '#8892a4', border: '1px solid #2d3748',
              fontFamily: 'inherit', fontSize: '0.68rem', cursor: 'pointer',
            }}
          >
            Approvals
          </button>
        )}
        {canClose && (
          <button
            onClick={() => onClose(wf)}
            title='Close hunt'
            style={{
              padding: '4px 7px', borderRadius: 3, background: 'transparent',
              color: '#4a5568', border: '1px solid #1e2330',
              fontFamily: 'inherit', fontSize: '0.68rem', cursor: 'pointer',
            }}
          >
            ✕
          </button>
        )}
      </div>
    </div>
  )
}

// ─── Kanban Column ────────────────────────────────────────────────────────────

function Column({
  state, workflows, onAction, onClose, actingId,
}: {
  state: string
  workflows: HuntWorkflow[]
  onAction: (wf: HuntWorkflow, to: string) => void
  onClose: (wf: HuntWorkflow) => void
  actingId: string | null
}) {
  return (
    <div style={{ flex: '0 0 210px', minWidth: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
        color: '#8892a4', fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase',
      }}>
        {STATE_LABELS[state]}
        {workflows.length > 0 && (
          <span style={{
            background: '#1e2330', color: '#4a5568',
            borderRadius: 10, padding: '1px 6px', fontSize: '0.6rem',
          }}>
            {workflows.length}
          </span>
        )}
      </div>
      {workflows.length === 0 ? (
        <div style={{
          border: '1px dashed #1e2330', borderRadius: 5,
          padding: '1.25rem', textAlign: 'center',
          color: '#2d3748', fontSize: '0.68rem',
        }}>Empty</div>
      ) : (
        workflows.map(wf => (
          <WFCard key={wf.id} wf={wf} onAction={onAction} onClose={onClose} actingId={actingId} />
        ))
      )}
    </div>
  )
}

// ─── Terminal row ─────────────────────────────────────────────────────────────

function TerminalRow({ wf, onRemove }: { wf: HuntWorkflow; onRemove: (id: string) => void }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '0.45rem 0.75rem', border: '1px solid #1e2330',
      borderRadius: 5, marginBottom: 4,
    }}>
      <span style={{
        background: wf.status === 'SUBMITTED' ? 'rgba(0,255,65,0.08)' : '#1e2330',
        color: wf.status === 'SUBMITTED' ? '#00FF41' : '#4a5568',
        border: wf.status === 'SUBMITTED' ? '1px solid rgba(0,255,65,0.2)' : '1px solid transparent',
        fontSize: '0.6rem', fontWeight: 700, padding: '1px 7px', borderRadius: 3,
      }}>
        {STATE_LABELS[wf.status]}
      </span>
      <span style={{ color: '#8892a4', fontSize: '0.78rem', flex: 1 }}>{wf.program_name}</span>
      {wf.findings_count > 0 && (
        <span style={{ color: '#00FF41', fontSize: '0.7rem' }}>{wf.findings_count} findings</span>
      )}
      <span style={{ color: '#2d3748', fontSize: '0.68rem' }}>
        {new Date(wf.updated_at).toLocaleDateString()}
      </span>
      <button
        onClick={() => onRemove(wf.id)}
        title='Remove'
        style={{
          background: 'none', border: 'none', color: '#2d3748',
          cursor: 'pointer', fontSize: '0.72rem', padding: '1px 5px',
        }}
      >✕</button>
    </div>
  )
}

// ─── Stats bar ────────────────────────────────────────────────────────────────

function StatsBar({ workflows }: { workflows: HuntWorkflow[] }) {
  const active = workflows.filter(w => !w.is_terminal).length
  const submitted = workflows.filter(w => w.status === 'SUBMITTED').length
  const findings = workflows.reduce((s, w) => s + w.findings_count, 0)
  const hil = workflows.filter(w => w.status === 'HIL_REVIEW').length
  const stats = [
    { label: 'Active', value: active, color: '#e2e8f0' },
    { label: 'Pending HiL', value: hil, color: hil > 0 ? '#f59e0b' : '#4a5568' },
    { label: 'Submitted', value: submitted, color: submitted > 0 ? '#00FF41' : '#4a5568' },
    { label: 'Total Findings', value: findings, color: findings > 0 ? '#00FF41' : '#4a5568' },
  ]
  return (
    <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.5rem' }}>
      {stats.map(s => (
        <div key={s.label} style={{ textAlign: 'center' }}>
          <div style={{ color: s.color, fontSize: '1.5rem', fontWeight: 700, lineHeight: 1 }}>{s.value}</div>
          <div style={{ color: '#4a5568', fontSize: '0.65rem', marginTop: 3, letterSpacing: '0.06em' }}>{s.label}</div>
        </div>
      ))}
    </div>
  )
}

// ─── Main Dashboard ───────────────────────────────────────────────────────────

export default function WorkflowDashboard() {
  const navigate = useNavigate()

  const [workflows, setWorkflows] = useState<HuntWorkflow[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await listWorkflows({ limit: 200 })
      setWorkflows(r.data.workflows)
    } catch {
      setError('Failed to load workflows')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleAction = useCallback(async (wf: HuntWorkflow, to: string) => {
    setActingId(wf.id)
    try {
      await transitionWorkflow(wf.id, to)
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || `Transition to ${to} failed`)
    } finally {
      setActingId(null)
    }
  }, [load])

  const handleClose = useCallback(async (wf: HuntWorkflow) => {
    if (!window.confirm(`Close hunt for "${wf.program_name}"?`)) return
    try {
      await transitionWorkflow(wf.id, 'CLOSED')
      await load()
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not close workflow')
    }
  }, [load])

  const handleRemove = useCallback(async (wf_id: string) => {
    if (!window.confirm('Remove this workflow from history?')) return
    try {
      await deleteWorkflow(wf_id)
      setWorkflows(prev => prev.filter(w => w.id !== wf_id))
    } catch {
      setError('Could not remove workflow')
    }
  }, [])

  const byState = (s: string) => workflows.filter(w => w.status === s)
  const pending = byState('SELECTED')
  const terminal = workflows.filter(w => w.is_terminal)
  const hasAny = workflows.length > 0

  return (
    <div style={{ padding: '1.5rem 2rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.2rem' }}>
        <div>
          <h1 style={{ color: '#e2e8f0', margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>
            Active Hunts
          </h1>
          <p style={{ color: '#4a5568', margin: '4px 0 0', fontSize: '0.78rem' }}>
            Workflow lifecycle tracker — scope acceptance through vulnerability submission
          </p>
        </div>
        <button
          onClick={() => navigate('/opportunities')}
          style={{
            padding: '8px 16px', borderRadius: 4, background: '#00FF41',
            color: '#0d1117', border: 'none', fontFamily: 'inherit',
            fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer', letterSpacing: '0.06em',
          }}
        >
          + NEW HUNT
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.25)',
          borderRadius: 6, padding: '0.6rem 1rem', color: '#f87171',
          fontSize: '0.78rem', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between',
        }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {loading ? (
        <div style={{ color: '#4a5568', padding: '4rem', textAlign: 'center', fontSize: '0.85rem' }}>Loading…</div>
      ) : !hasAny ? (
        /* Empty state */
        <div style={{
          border: '1px dashed #1e2330', borderRadius: 8,
          padding: '5rem 2rem', textAlign: 'center',
        }}>
          <div style={{ color: '#4a5568', marginBottom: 4, fontSize: '0.85rem' }}>No active hunts</div>
          <div style={{ color: '#2d3748', fontSize: '0.75rem', marginBottom: 16 }}>
            Start from the Opportunity Hub — public programs begin immediately.
          </div>
          <button
            onClick={() => navigate('/opportunities')}
            style={{
              padding: '8px 18px', borderRadius: 4, background: '#00FF41',
              color: '#0d1117', border: 'none', fontFamily: 'inherit',
              fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
            }}
          >
            Browse Opportunities
          </button>
        </div>
      ) : (
        <>
          <StatsBar workflows={workflows} />

          {/* Pending scope acceptance (invite-only programs) */}
          {pending.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{
                color: '#f59e0b', fontSize: '0.65rem', fontWeight: 700,
                letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8,
              }}>
                Pending Scope Acceptance ({pending.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 8 }}>
                {pending.map(wf => (
                  <WFCard key={wf.id} wf={wf} onAction={handleAction} onClose={handleClose} actingId={actingId} />
                ))}
              </div>
            </div>
          )}

          {/* Main kanban board */}
          <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
            <div style={{ display: 'flex', gap: 10, minWidth: `${KANBAN_COLS.length * 220}px` }}>
              {KANBAN_COLS.map(s => (
                <Column
                  key={s}
                  state={s}
                  workflows={byState(s)}
                  onAction={handleAction}
                  onClose={handleClose}
                  actingId={actingId}
                />
              ))}
            </div>
          </div>

          {/* Terminal history */}
          {terminal.length > 0 && (
            <div style={{ marginTop: '2rem' }}>
              <div style={{
                color: '#4a5568', fontSize: '0.65rem', fontWeight: 700,
                letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8,
              }}>
                History — Submitted / Closed ({terminal.length})
              </div>
              {terminal.map(wf => (
                <TerminalRow key={wf.id} wf={wf} onRemove={handleRemove} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
