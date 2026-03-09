import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listWorkflows, transitionWorkflow, deleteWorkflow, submitCredentials, getOpportunity } from '../lib/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface CredentialRequirement {
  kind: string        // "signup" | "api_key" | "oauth" | "paid_plan" | "vpn" | "other"
  label: string
  signup_url: string
  notes: string
  required: boolean
}

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
  credentials_collected: boolean
  vault_path: string
  outcome: string
  outcome_payout_usd: number
  outcome_note: string
  outcome_at: string
}

// ─── Constants ────────────────────────────────────────────────────────────────

const ACTIVE_STATES = ['SELECTED', 'SCOPING', 'CREDENTIAL_SETUP', 'RECON', 'SCANNING', 'TRIAGE', 'HIL_REVIEW']
const KANBAN_COLS = ['SCOPING', 'CREDENTIAL_SETUP', 'RECON', 'SCANNING', 'TRIAGE', 'HIL_REVIEW']

const STATE_LABELS: Record<string, string> = {
  SELECTED: 'Selected', SCOPING: 'Scoping', CREDENTIAL_SETUP: 'Cred Setup',
  RECON: 'Recon', SCANNING: 'Scanning', TRIAGE: 'Triage', HIL_REVIEW: 'HiL Review',
  SUBMITTED: 'Submitted', CLOSED: 'Closed',
}

// Primary forward action per state (CREDENTIAL_SETUP handled separately via panel)
const PRIMARY_ACTION: Record<string, { label: string; to: string }> = {
  SELECTED:   { label: 'Accept Scope →',   to: 'SCOPING' },
  SCOPING:    { label: 'Queue Recon →',    to: 'CREDENTIAL_SETUP' },
  RECON:      { label: 'Begin Scanning →', to: 'SCANNING' },
  SCANNING:   { label: 'Move to Triage →', to: 'TRIAGE' },
  TRIAGE:     { label: 'Request Review →', to: 'HIL_REVIEW' },
  HIL_REVIEW: { label: 'Mark Submitted →', to: 'SUBMITTED' },
  SUBMITTED:  { label: 'Close Hunt',       to: 'CLOSED' },
}

const PLATFORM_COLORS: Record<string, string> = {
  hackerone: '#25a244', bugcrowd: '#D97706', intigriti: '#7c3aed',
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

// ─── Credential Setup Panel ───────────────────────────────────────────────────

const KIND_LABELS: Record<string, string> = {
  signup: 'Account Signup', api_key: 'API Key', oauth: 'OAuth Token',
  paid_plan: 'Paid Plan', vpn: 'VPN Access', other: 'Other',
}

function CredentialSetupPanel({
  wf, onClose, onSuccess,
}: {
  wf: HuntWorkflow
  onClose: () => void
  onSuccess: () => void
}) {
  const [credReqs, setCredReqs] = useState<CredentialRequirement[]>([])
  const [loadingReqs, setLoadingReqs] = useState(true)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [oauthToken, setOauthToken] = useState('')
  const [notes, setNotes] = useState('')
  const [skipMode, setSkipMode] = useState(false)
  const [skipReason, setSkipReason] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    getOpportunity(wf.opportunity_id)
      .then(r => setCredReqs(r.data.credential_requirements ?? []))
      .catch(() => setCredReqs([]))
      .finally(() => setLoadingReqs(false))
  }, [wf.opportunity_id])

  const handleSubmit = async () => {
    setSubmitting(true)
    setError(null)
    try {
      await submitCredentials(wf.id, {
        username, password, api_key: apiKey, oauth_token: oauthToken,
        notes, skip_reason: skipMode ? skipReason : '',
      })
      onSuccess()
      onClose()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : JSON.stringify(detail) || 'Submission failed')
    } finally {
      setSubmitting(false)
    }
  }

  const canSubmit = !submitting && (skipMode ? skipReason.trim().length > 0 : true)

  const inputStyle: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box', background: '#111316',
    border: '1px solid #355E3B', borderRadius: 4, color: '#8FAF9B',
    padding: '6px 10px', fontFamily: 'inherit', fontSize: '0.8rem',
    outline: 'none',
  }
  const labelStyle: React.CSSProperties = {
    display: 'block', color: '#8FAF9B', fontSize: '0.68rem',
    fontWeight: 600, letterSpacing: '0.08em', marginBottom: 4,
  }

  return (
    /* Modal backdrop */
    <div
      onClick={e => { if (e.target === e.currentTarget) onClose() }}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '1rem',
      }}
    >
      <div style={{
        background: '#111316', border: '1px solid #355E3B', borderRadius: 8,
        width: '100%', maxWidth: 560, maxHeight: '90vh', overflowY: 'auto',
        padding: '1.5rem',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
          <div>
            <div style={{ color: '#8FAF9B', fontWeight: 700, fontSize: '1rem' }}>Credential Setup</div>
            <div style={{ color: '#6F8E7A', fontSize: '0.72rem', marginTop: 3 }}>{wf.program_name}</div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#6F8E7A', cursor: 'pointer', fontSize: '1rem', padding: '2px 6px' }}
          >✕</button>
        </div>

        {/* Program requirements */}
        {loadingReqs ? (
          <div style={{ color: '#6F8E7A', fontSize: '0.78rem', marginBottom: '1rem' }}>Loading requirements…</div>
        ) : credReqs.length > 0 ? (
          <div style={{ marginBottom: '1.25rem' }}>
            <div style={{ color: '#8FAF9B', fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
              Program Requirements
            </div>
            {credReqs.map((cr, i) => (
              <div key={i} style={{
                background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 5,
                padding: '0.6rem 0.85rem', marginBottom: 6,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{
                    background: cr.required ? 'rgba(239,68,68,0.1)' : 'rgba(74,85,104,0.2)',
                    color: cr.required ? '#f87171' : '#8FAF9B',
                    border: `1px solid ${cr.required ? 'rgba(239,68,68,0.25)' : '#355E3B'}`,
                    fontSize: '0.58rem', fontWeight: 700, padding: '1px 6px', borderRadius: 3,
                  }}>
                    {cr.required ? 'REQUIRED' : 'OPTIONAL'}
                  </span>
                  <span style={{ color: '#8FAF9B', fontSize: '0.62rem' }}>{KIND_LABELS[cr.kind] || cr.kind}</span>
                </div>
                <div style={{ color: '#8FAF9B', fontSize: '0.78rem', fontWeight: 600, marginBottom: 4 }}>{cr.label}</div>
                {cr.notes && (
                  <div style={{ color: '#6F8E7A', fontSize: '0.72rem', marginBottom: 4 }}>{cr.notes}</div>
                )}
                {cr.signup_url && (
                  <a
                    href={cr.signup_url}
                    target='_blank'
                    rel='noopener noreferrer'
                    style={{ color: '#355E3B', fontSize: '0.72rem', textDecoration: 'none' }}
                  >
                    → {cr.signup_url.replace(/^https?:\/\//, '')}
                  </a>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{
            background: 'rgba(95,143,107,0.04)', border: '1px solid rgba(95,143,107,0.12)',
            borderRadius: 5, padding: '0.6rem 0.85rem', marginBottom: '1.25rem',
            color: '#6F8E7A', fontSize: '0.75rem',
          }}>
            No specific credential requirements listed for this program.
          </div>
        )}

        {/* Skip toggle */}
        <div style={{ marginBottom: '1rem' }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
            <input
              type='checkbox'
              checked={skipMode}
              onChange={e => setSkipMode(e.target.checked)}
              style={{ accentColor: '#355E3B', width: 14, height: 14 }}
            />
            <span style={{ color: '#8FAF9B', fontSize: '0.75rem' }}>
              Skip credential setup — surface-level scan only
            </span>
          </label>
        </div>

        {skipMode ? (
          <div style={{ marginBottom: '1rem' }}>
            <label style={labelStyle}>Reason for skipping *</label>
            <textarea
              rows={2}
              value={skipReason}
              onChange={e => setSkipReason(e.target.value)}
              placeholder='e.g. No authentication required for this scope'
              style={{ ...inputStyle, resize: 'vertical' }}
            />
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: '1rem' }}>
              <div>
                <label style={labelStyle}>Username / Email</label>
                <input type='text' value={username} onChange={e => setUsername(e.target.value)}
                  placeholder='test@example.com' style={inputStyle} autoComplete='off' />
              </div>
              <div>
                <label style={labelStyle}>Password</label>
                <input type='password' value={password} onChange={e => setPassword(e.target.value)}
                  placeholder='••••••••' style={inputStyle} autoComplete='new-password' />
              </div>
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={labelStyle}>API Key / Token</label>
              <input type='text' value={apiKey} onChange={e => setApiKey(e.target.value)}
                placeholder='sk-...' style={inputStyle} autoComplete='off' />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={labelStyle}>OAuth Token</label>
              <input type='text' value={oauthToken} onChange={e => setOauthToken(e.target.value)}
                placeholder='ya29...' style={inputStyle} autoComplete='off' />
            </div>
            <div style={{ marginBottom: '1rem' }}>
              <label style={labelStyle}>Notes</label>
              <textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)}
                placeholder='Account tier, limitations, expiry date…'
                style={{ ...inputStyle, resize: 'vertical' }} />
            </div>
          </>
        )}

        {/* Security notice */}
        <div style={{
          background: 'rgba(74,85,104,0.1)', border: '1px solid #355E3B', borderRadius: 4,
          padding: '0.5rem 0.75rem', marginBottom: '1rem',
          color: '#6F8E7A', fontSize: '0.68rem', lineHeight: 1.5,
        }}>
          Credentials are encrypted and stored in HashiCorp Vault. Never use production or personal accounts for testing.
        </div>

        {error && (
          <div style={{
            background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.25)',
            borderRadius: 4, padding: '0.5rem 0.75rem', color: '#f87171',
            fontSize: '0.75rem', marginBottom: '1rem',
          }}>
            {error}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{
              padding: '7px 14px', borderRadius: 4, background: 'transparent',
              color: '#8FAF9B', border: '1px solid #3A4F43',
              fontFamily: 'inherit', fontSize: '0.78rem', cursor: 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            style={{
              padding: '7px 16px', borderRadius: 4,
              background: canSubmit ? '#355E3B' : '#355E3B',
              color: canSubmit ? '#111316' : '#6F8E7A',
              border: 'none', fontFamily: 'inherit', fontSize: '0.78rem',
              fontWeight: 700, cursor: canSubmit ? 'pointer' : 'not-allowed',
            }}
          >
            {submitting ? 'Submitting…' : skipMode ? 'Skip & Proceed to Recon' : 'Save to Vault & Start Recon'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Kanban Card ──────────────────────────────────────────────────────────────

function WFCard({
  wf, onAction, onClose, onOpenCredPanel, actingId,
}: {
  wf: HuntWorkflow
  onAction: (wf: HuntWorkflow, to: string) => void
  onClose: (wf: HuntWorkflow) => void
  onOpenCredPanel: (wf: HuntWorkflow) => void
  actingId: string | null
}) {
  const navigate = useNavigate()
  const pc = PLATFORM_COLORS[wf.platform] || '#6F8E7A'
  const pa = PRIMARY_ACTION[wf.status]
  const busy = actingId === wf.id
  const isCredSetup = wf.status === 'CREDENTIAL_SETUP'
  const canAdvance = !isCredSetup && pa && wf.allowed_transitions.includes(pa.to)
  const canClose = wf.allowed_transitions.includes('CLOSED') && pa?.to !== 'CLOSED'

  return (
    <div style={{
      background: '#111316', border: '1px solid #355E3B', borderRadius: 6,
      padding: '0.75rem 0.85rem', marginBottom: 8,
    }}>
      {/* Program name — click to view opportunity */}
      <div
        onClick={() => navigate(`/opportunities`)}
        title='View opportunities'
        style={{
          color: '#8FAF9B', fontWeight: 600, fontSize: '0.82rem', lineHeight: 1.3,
          cursor: 'pointer', marginBottom: 4,
        }}
        onMouseEnter={e => (e.currentTarget.style.color = '#355E3B')}
        onMouseLeave={e => (e.currentTarget.style.color = '#8FAF9B')}
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
            background: 'rgba(95,143,107,0.08)', color: '#355E3B',
            border: '1px solid rgba(95,143,107,0.2)',
            fontSize: '0.58rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
          }}>
            {wf.findings_count} finding{wf.findings_count !== 1 ? 's' : ''}
          </span>
        )}
        {wf.run_ids.length > 0 && (
          <span style={{ color: '#6F8E7A', fontSize: '0.62rem' }}>
            {wf.run_ids.length} run{wf.run_ids.length !== 1 ? 's' : ''}
          </span>
        )}
        <span style={{ color: '#3A4F43', fontSize: '0.62rem', marginLeft: 'auto' }}>
          {elapsed(wf.transitioned_at[wf.status])}
        </span>
      </div>

      {/* Action row */}
      <div style={{ display: 'flex', gap: 5 }}>
        {isCredSetup ? (
          <button
            onClick={() => onOpenCredPanel(wf)}
            disabled={busy}
            style={{
              flex: 1, padding: '4px 8px', borderRadius: 3,
              background: 'rgba(217,119,6,0.15)', color: '#D97706',
              border: '1px solid rgba(217,119,6,0.3)',
              fontFamily: 'inherit', fontSize: '0.68rem', fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Setup Credentials →
          </button>
        ) : canAdvance ? (
          <button
            onClick={() => onAction(wf, pa!.to)}
            disabled={busy}
            style={{
              flex: 1, padding: '4px 8px', borderRadius: 3,
              background: '#355E3B', color: '#111316',
              border: 'none', fontFamily: 'inherit', fontSize: '0.68rem', fontWeight: 700,
              cursor: busy ? 'not-allowed' : 'pointer',
              opacity: busy ? 0.5 : 1,
            }}
          >
            {busy ? '…' : pa!.label}
          </button>
        ) : null}
        {wf.status === 'HIL_REVIEW' && (
          <button
            onClick={() => navigate('/operations/approvals')}
            style={{
              padding: '4px 8px', borderRadius: 3, background: 'transparent',
              color: '#8FAF9B', border: '1px solid #3A4F43',
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
              color: '#6F8E7A', border: '1px solid #355E3B',
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
  state, workflows, onAction, onClose, onOpenCredPanel, actingId,
}: {
  state: string
  workflows: HuntWorkflow[]
  onAction: (wf: HuntWorkflow, to: string) => void
  onClose: (wf: HuntWorkflow) => void
  onOpenCredPanel: (wf: HuntWorkflow) => void
  actingId: string | null
}) {
  const isCredCol = state === 'CREDENTIAL_SETUP'
  return (
    <div style={{ flex: '0 0 210px', minWidth: 0 }}>
      <div style={{
        display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8,
        color: isCredCol ? '#D97706' : '#8FAF9B',
        fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.1em',
        textTransform: 'uppercase',
      }}>
        {STATE_LABELS[state]}
        {workflows.length > 0 && (
          <span style={{
            background: isCredCol ? 'rgba(217,119,6,0.1)' : '#355E3B',
            color: isCredCol ? '#D97706' : '#6F8E7A',
            borderRadius: 10, padding: '1px 6px', fontSize: '0.6rem',
          }}>
            {workflows.length}
          </span>
        )}
      </div>
      {workflows.length === 0 ? (
        <div style={{
          border: `1px dashed ${isCredCol ? 'rgba(217,119,6,0.2)' : '#355E3B'}`,
          borderRadius: 5, padding: '1.25rem', textAlign: 'center',
          color: '#3A4F43', fontSize: '0.68rem',
        }}>Empty</div>
      ) : (
        workflows.map(wf => (
          <WFCard key={wf.id} wf={wf} onAction={onAction} onClose={onClose}
            onOpenCredPanel={onOpenCredPanel} actingId={actingId} />
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
      padding: '0.45rem 0.75rem', border: '1px solid #355E3B',
      borderRadius: 5, marginBottom: 4,
    }}>
      <span style={{
        background: wf.status === 'SUBMITTED' ? 'rgba(95,143,107,0.08)' : '#355E3B',
        color: wf.status === 'SUBMITTED' ? '#355E3B' : '#6F8E7A',
        border: wf.status === 'SUBMITTED' ? '1px solid rgba(95,143,107,0.2)' : '1px solid transparent',
        fontSize: '0.6rem', fontWeight: 700, padding: '1px 7px', borderRadius: 3,
      }}>
        {STATE_LABELS[wf.status]}
      </span>
      <span style={{ color: '#8FAF9B', fontSize: '0.78rem', flex: 1 }}>{wf.program_name}</span>
      {wf.findings_count > 0 && (
        <span style={{ color: '#355E3B', fontSize: '0.7rem' }}>{wf.findings_count} findings</span>
      )}
      <span style={{ color: '#3A4F43', fontSize: '0.68rem' }}>
        {new Date(wf.updated_at).toLocaleDateString()}
      </span>
      <button
        onClick={() => onRemove(wf.id)}
        title='Remove'
        style={{
          background: 'none', border: 'none', color: '#3A4F43',
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
  const credSetup = workflows.filter(w => w.status === 'CREDENTIAL_SETUP').length
  const stats = [
    { label: 'Active', value: active, color: '#8FAF9B' },
    { label: 'Cred Setup', value: credSetup, color: credSetup > 0 ? '#D97706' : '#6F8E7A' },
    { label: 'Pending HiL', value: hil, color: hil > 0 ? '#D97706' : '#6F8E7A' },
    { label: 'Submitted', value: submitted, color: submitted > 0 ? '#355E3B' : '#6F8E7A' },
    { label: 'Total Findings', value: findings, color: findings > 0 ? '#355E3B' : '#6F8E7A' },
  ]
  return (
    <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.5rem' }}>
      {stats.map(s => (
        <div key={s.label} style={{ textAlign: 'center' }}>
          <div style={{ color: s.color, fontSize: '1.5rem', fontWeight: 700, lineHeight: 1 }}>{s.value}</div>
          <div style={{ color: '#6F8E7A', fontSize: '0.65rem', marginTop: 3, letterSpacing: '0.06em' }}>{s.label}</div>
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
  const [credPanelWf, setCredPanelWf] = useState<HuntWorkflow | null>(null)

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
      {credPanelWf && (
        <CredentialSetupPanel
          wf={credPanelWf}
          onClose={() => setCredPanelWf(null)}
          onSuccess={load}
        />
      )}
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.2rem' }}>
        <div>
          <h1 style={{ color: '#8FAF9B', margin: 0, fontSize: '1.4rem', fontWeight: 700 }}>
            Active Hunts
          </h1>
          <p style={{ color: '#6F8E7A', margin: '4px 0 0', fontSize: '0.78rem' }}>
            Workflow lifecycle tracker — scope acceptance through vulnerability submission
          </p>
        </div>
        <button
          onClick={() => navigate('/opportunities')}
          style={{
            padding: '8px 16px', borderRadius: 4, background: '#355E3B',
            color: '#111316', border: 'none', fontFamily: 'inherit',
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
        <div style={{ color: '#6F8E7A', padding: '4rem', textAlign: 'center', fontSize: '0.85rem' }}>Loading…</div>
      ) : !hasAny ? (
        /* Empty state */
        <div style={{
          border: '1px dashed #355E3B', borderRadius: 8,
          padding: '5rem 2rem', textAlign: 'center',
        }}>
          <div style={{ color: '#6F8E7A', marginBottom: 4, fontSize: '0.85rem' }}>No active hunts</div>
          <div style={{ color: '#3A4F43', fontSize: '0.75rem', marginBottom: 16 }}>
            Start from the Opportunity Hub — public programs begin immediately.
          </div>
          <button
            onClick={() => navigate('/opportunities')}
            style={{
              padding: '8px 18px', borderRadius: 4, background: '#355E3B',
              color: '#111316', border: 'none', fontFamily: 'inherit',
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
                color: '#D97706', fontSize: '0.65rem', fontWeight: 700,
                letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 8,
              }}>
                Pending Scope Acceptance ({pending.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(210px, 1fr))', gap: 8 }}>
                {pending.map(wf => (
                  <WFCard key={wf.id} wf={wf} onAction={handleAction} onClose={handleClose}
                    onOpenCredPanel={setCredPanelWf} actingId={actingId} />
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
                  onOpenCredPanel={setCredPanelWf}
                  actingId={actingId}
                />
              ))}
            </div>
          </div>

          {/* Terminal history */}
          {terminal.length > 0 && (
            <div style={{ marginTop: '2rem' }}>
              <div style={{
                color: '#6F8E7A', fontSize: '0.65rem', fontWeight: 700,
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
