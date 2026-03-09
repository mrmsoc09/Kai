/**
 * HUNT OPS — Merged Opportunity Browser + Workflow Dashboard + Credential Setup.
 * Consolidates /opportunities and /workflows into a single tactical hub.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  listOpportunities, createWorkflow,
  listWorkflows, transitionWorkflow, deleteWorkflow, submitCredentials, getOpportunity,
} from '../lib/api'

// ─── Design tokens ────────────────────────────────────────────────────────────

const C = {
  bg: '#0B0C0D', card: '#111316', border: '#355E3B', borderDim: '#24352A',
  green: '#355E3B', greenDim: '#2D4E33', greenGlow: 'rgba(95,143,107,0.15)',
  amber: '#D97706', red: '#A12B2B', cyan: '#5A2E8A', purple: '#6D3AA6',
  text: '#8FAF9B', textSub: '#8FAF9B', textMute: '#6F8E7A', textDead: '#3A4F43',
}
const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"

// ─── Shared ───────────────────────────────────────────────────────────────────

function TabBar({ tabs, active, onChange }: {
  tabs: { id: string; label: string; badge?: number }[]
  active: string; onChange: (id: string) => void
}) {
  return (
    <div style={{ display: 'flex', gap: 2, borderBottom: `1px solid ${C.border}`, background: C.card }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            padding: '10px 16px', background: 'transparent', border: 'none',
            borderBottom: `2px solid ${active === t.id ? C.green : 'transparent'}`,
            color: active === t.id ? C.green : C.textMute,
            fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700,
            letterSpacing: '0.12em', cursor: 'pointer', transition: 'all 0.12s',
            display: 'flex', alignItems: 'center', gap: 6,
          }}
        >
          {t.label}
          {t.badge !== undefined && t.badge > 0 && (
            <span style={{
              background: active === t.id ? C.greenGlow : 'rgba(148,163,184,0.08)',
              color: active === t.id ? C.green : C.textMute,
              border: `1px solid ${active === t.id ? 'rgba(95,143,107,0.3)' : C.border}`,
              borderRadius: 10, padding: '0 5px', fontSize: '0.58rem',
            }}>{t.badge}</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ─── OPPORTUNITY BROWSER ─────────────────────────────────────────────────────

const PLATFORM_COLORS: Record<string, string> = {
  hackerone: '#25a244', bugcrowd: '#D97706', intigriti: '#7c3aed', vrp: '#2563eb', government_cvd: '#0891b2',
}
const SEVERITY_SCORE_COLORS = (s: number) =>
  s >= 0.7 ? C.green : s >= 0.5 ? C.amber : s >= 0.3 ? '#8FAF9B' : C.textMute

interface Opportunity {
  id: string; name: string; organization: string; platform: string
  access_type: string; max_payout_usd: number; min_payout_usd: number
  vdp_only: boolean; vuln_types: string[]; priority_score: number
  is_public: boolean; payout_label: string; scope_domains: string[]
  tags: string[]; needs_credentials: boolean
  credential_requirements?: any[]
}

function OpportunityBrowser({ onHuntLaunched }: { onHuntLaunched: () => void }) {
  const [opps, setOpps] = useState<Opportunity[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [filterPlatform, setFilterPlatform] = useState('')
  const [filterAccess, setFilterAccess] = useState('')
  const [launchingId, setLaunchingId] = useState<string | null>(null)
  const [inviteOpp, setInviteOpp] = useState<Opportunity | null>(null)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    listOpportunities({ limit: 100, sort_by: 'score' })
      .then(r => setOpps(r.data?.opportunities ?? r.data ?? []))
      .finally(() => setLoading(false))
  }, [])

  const launchHunt = async (opp: Opportunity) => {
    if (!opp.is_public) { setInviteOpp(opp); return }
    setLaunchingId(opp.id)
    try {
      await createWorkflow(opp.id)
      onHuntLaunched()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Failed to start hunt')
    } finally {
      setLaunchingId(null)
    }
  }

  const filtered = opps.filter(o => {
    if (search && !o.name.toLowerCase().includes(search.toLowerCase()) &&
      !o.organization.toLowerCase().includes(search.toLowerCase())) return false
    if (filterPlatform && o.platform !== filterPlatform) return false
    if (filterAccess === 'public' && !o.is_public) return false
    if (filterAccess === 'private' && o.is_public) return false
    return true
  })

  const platforms = [...new Set(opps.map(o => o.platform))].sort()

  if (loading) return (
    <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>
      ▓▒░ LOADING OPPORTUNITIES…
    </div>
  )

  return (
    <div style={{ padding: '1.25rem 1.5rem' }}>
      {/* Filter bar */}
      <div style={{ display: 'flex', gap: 8, marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search programs…"
          style={{
            flex: 1, minWidth: 180, background: '#0B0C0D', border: `1px solid ${C.border}`,
            borderRadius: 4, color: C.text, padding: '7px 12px', fontFamily: MONO, fontSize: '0.75rem', outline: 'none',
          }}
        />
        <select
          value={filterPlatform}
          onChange={e => setFilterPlatform(e.target.value)}
          style={{ background: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, color: C.textSub, padding: '7px 10px', fontFamily: MONO, fontSize: '0.7rem', outline: 'none' }}
        >
          <option value="">All Platforms</option>
          {platforms.map(p => <option key={p} value={p}>{p.toUpperCase()}</option>)}
        </select>
        <select
          value={filterAccess}
          onChange={e => setFilterAccess(e.target.value)}
          style={{ background: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, color: C.textSub, padding: '7px 10px', fontFamily: MONO, fontSize: '0.7rem', outline: 'none' }}
        >
          <option value="">All Access</option>
          <option value="public">Public</option>
          <option value="private">Private</option>
        </select>
        <span style={{ color: C.textMute, fontSize: '0.65rem', fontFamily: MONO }}>
          {filtered.length} programs
        </span>
      </div>

      {/* Opportunity grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 8 }}>
        {filtered.map(opp => {
          const pc = PLATFORM_COLORS[opp.platform] || '#6F8E7A'
          const expanded = expandedId === opp.id
          const scoreColor = SEVERITY_SCORE_COLORS(opp.priority_score)

          return (
            <div
              key={opp.id}
              style={{
                background: C.card, border: `1px solid ${C.border}`, borderRadius: 6,
                padding: '12px 14px', transition: 'border-color 0.12s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = '#3A4F43'}
              onMouseLeave={e => e.currentTarget.style.borderColor = C.border}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 8 }}>
                <div style={{ flex: 1 }}>
                  <div style={{ color: C.text, fontWeight: 700, fontSize: '0.82rem', marginBottom: 3 }}>
                    {opp.name}
                  </div>
                  <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                    <span style={{
                      background: `${pc}1a`, color: pc, border: `1px solid ${pc}33`,
                      fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                    }}>
                      {opp.platform.toUpperCase()}
                    </span>
                    {!opp.is_public && (
                      <span style={{
                        background: 'rgba(217,119,6,0.1)', color: C.amber,
                        border: '1px solid rgba(217,119,6,0.25)',
                        fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                      }}>INVITE</span>
                    )}
                    {opp.vdp_only && (
                      <span style={{
                        background: 'rgba(100,100,100,0.1)', color: C.textMute,
                        border: `1px solid ${C.border}`,
                        fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                      }}>VDP</span>
                    )}
                    {opp.needs_credentials && (
                      <span style={{
                        background: 'rgba(90,46,138,0.1)', color: C.cyan,
                        border: '1px solid rgba(90,46,138,0.25)',
                        fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3,
                      }}>NEEDS CREDS</span>
                    )}
                  </div>
                </div>
                {/* Score */}
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  <div style={{ color: scoreColor, fontSize: '1.1rem', fontWeight: 700, fontFamily: MONO }}>
                    {Math.round(opp.priority_score * 100)}
                  </div>
                  <div style={{ color: C.textMute, fontSize: '0.52rem', letterSpacing: '0.06em' }}>SCORE</div>
                </div>
              </div>

              {/* Payout */}
              {!opp.vdp_only && (
                <div style={{ color: C.green, fontSize: '0.72rem', fontFamily: MONO, marginBottom: 8 }}>
                  {opp.payout_label || `$${opp.min_payout_usd}–$${opp.max_payout_usd.toLocaleString()}`}
                </div>
              )}

              {/* Vuln types */}
              <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
                {opp.vuln_types.slice(0, 5).map(v => (
                  <span key={v} style={{ color: C.textMute, fontSize: '0.58rem', background: '#0B0C0D', border: `1px solid ${C.border}`, padding: '1px 5px', borderRadius: 3 }}>
                    {v}
                  </span>
                ))}
                {opp.vuln_types.length > 5 && (
                  <span style={{ color: C.textMute, fontSize: '0.58rem' }}>+{opp.vuln_types.length - 5} more</span>
                )}
              </div>

              {/* Expand toggle */}
              {opp.scope_domains.length > 0 && (
                <div>
                  <button
                    onClick={() => setExpandedId(expanded ? null : opp.id)}
                    style={{
                      background: 'none', border: 'none', color: C.textMute, fontFamily: MONO,
                      fontSize: '0.6rem', cursor: 'pointer', padding: 0, letterSpacing: '0.06em',
                      display: 'flex', alignItems: 'center', gap: 4,
                    }}
                  >
                    {expanded ? '▼' : '▶'} {opp.scope_domains.length} scope domains
                  </button>
                  {expanded && (
                    <div style={{ marginTop: 6, padding: '6px 10px', background: '#0B0C0D', borderRadius: 4, border: `1px solid ${C.border}` }}>
                      {opp.scope_domains.map(d => (
                        <div key={d} style={{ color: C.textSub, fontSize: '0.65rem', fontFamily: MONO, lineHeight: 1.7 }}>
                          {d}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Launch button */}
              <div style={{ marginTop: 10 }}>
                <button
                  onClick={() => launchHunt(opp)}
                  disabled={launchingId === opp.id}
                  style={{
                    width: '100%', padding: '7px', borderRadius: 4, border: 'none',
                    background: launchingId === opp.id ? C.border : C.green,
                    color: launchingId === opp.id ? C.textMute : '#0B0C0D',
                    fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700,
                    letterSpacing: '0.08em', cursor: launchingId === opp.id ? 'not-allowed' : 'pointer',
                  }}
                >
                  {launchingId === opp.id ? 'LAUNCHING…' : opp.is_public ? 'LAUNCH HUNT →' : 'REQUEST ACCESS →'}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Invite modal */}
      {inviteOpp && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
        }}>
          <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, padding: '2rem', maxWidth: 440, width: '90%' }}>
            <div style={{ color: C.amber, fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 8 }}>
              INVITE-ONLY PROGRAM
            </div>
            <div style={{ color: C.text, fontWeight: 700, marginBottom: 10 }}>{inviteOpp.name}</div>
            <div style={{ color: C.textMute, fontSize: '0.78rem', lineHeight: 1.6, marginBottom: '1.25rem' }}>
              This is a private/invite-only program. You must have a valid invitation before testing.
              By proceeding, you confirm you have received an authorized invitation.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setInviteOpp(null)}
                style={{ flex: 1, padding: '8px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 4, color: C.textSub, fontFamily: MONO, fontSize: '0.68rem', cursor: 'pointer' }}
              >
                CANCEL
              </button>
              <button
                onClick={async () => {
                  const opp = inviteOpp; setInviteOpp(null)
                  setLaunchingId(opp.id)
                  try { await createWorkflow(opp.id); onHuntLaunched() }
                  catch (e: any) { alert(e?.response?.data?.detail || 'Failed') }
                  finally { setLaunchingId(null) }
                }}
                style={{ flex: 1, padding: '8px', background: C.amber, border: 'none', borderRadius: 4, color: '#0B0C0D', fontFamily: MONO, fontSize: '0.68rem', fontWeight: 700, cursor: 'pointer' }}
              >
                I HAVE AUTHORIZATION
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ─── WORKFLOW KANBAN ─────────────────────────────────────────────────────────

interface HuntWorkflow {
  id: string; opportunity_id: string; program_name: string; platform: string
  status: string; scope_domains: string[]; findings_count: number
  created_at: string; updated_at: string; transitioned_at: Record<string, string>
  run_ids: string[]; notes: string; allowed_transitions: string[]; is_terminal: boolean
  credentials_collected: boolean; vault_path: string; outcome: string
}

interface CredentialRequirement {
  kind: string; label: string; signup_url: string; notes: string; required: boolean
}

const STATE_LABELS: Record<string, string> = {
  SELECTED: 'Selected', SCOPING: 'Scoping', CREDENTIAL_SETUP: 'Cred Setup',
  RECON: 'Recon', SCANNING: 'Scanning', TRIAGE: 'Triage', HIL_REVIEW: 'HiL Review',
  SUBMITTED: 'Submitted', CLOSED: 'Closed',
}
const KANBAN_COLS = ['SCOPING', 'CREDENTIAL_SETUP', 'RECON', 'SCANNING', 'TRIAGE', 'HIL_REVIEW']
const PRIMARY_ACTION: Record<string, { label: string; to: string }> = {
  SELECTED: { label: 'Accept Scope →', to: 'SCOPING' },
  SCOPING: { label: 'Queue Recon →', to: 'CREDENTIAL_SETUP' },
  RECON: { label: 'Begin Scanning →', to: 'SCANNING' },
  SCANNING: { label: 'Move to Triage →', to: 'TRIAGE' },
  TRIAGE: { label: 'Request Review →', to: 'HIL_REVIEW' },
  HIL_REVIEW: { label: 'Mark Submitted →', to: 'SUBMITTED' },
  SUBMITTED: { label: 'Close Hunt', to: 'CLOSED' },
}

const KIND_LABELS: Record<string, string> = {
  signup: 'Account Signup', api_key: 'API Key', oauth: 'OAuth',
  paid_plan: 'Paid Plan', vpn: 'VPN', other: 'Other',
}

function CredPanel({ wf, onClose, onSuccess }: { wf: HuntWorkflow; onClose: () => void; onSuccess: () => void }) {
  const [credReqs, setCredReqs] = useState<CredentialRequirement[]>([])
  const [loading, setLoading] = useState(true)
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
      .finally(() => setLoading(false))
  }, [wf.opportunity_id])

  const handleSubmit = async () => {
    setSubmitting(true); setError(null)
    try {
      await submitCredentials(wf.id, { username, password, api_key: apiKey, oauth_token: oauthToken, notes, skip_reason: skipMode ? skipReason : '' })
      onSuccess(); onClose()
    } catch (e: any) {
      const d = e?.response?.data?.detail
      setError(typeof d === 'string' ? d : 'Submission failed')
    } finally { setSubmitting(false) }
  }

  const inp: React.CSSProperties = {
    width: '100%', boxSizing: 'border-box', background: C.bg, border: `1px solid ${C.border}`,
    borderRadius: 4, color: C.text, padding: '7px 11px', fontFamily: MONO, fontSize: '0.78rem', outline: 'none',
  }
  const lbl: React.CSSProperties = { display: 'block', color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 5 }

  return (
    <div onClick={e => { if (e.target === e.currentTarget) onClose() }} style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 300 }}>
      <div style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 8, width: '100%', maxWidth: 540, maxHeight: '90vh', overflowY: 'auto', padding: '1.5rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
          <div>
            <div style={{ color: C.text, fontWeight: 700 }}>Credential Setup</div>
            <div style={{ color: C.textMute, fontSize: '0.7rem', marginTop: 2 }}>{wf.program_name}</div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: C.textMute, cursor: 'pointer', fontSize: '1rem' }}>✕</button>
        </div>

        {loading ? (
          <div style={{ color: C.textMute, fontSize: '0.75rem', marginBottom: '1rem' }}>Loading requirements…</div>
        ) : credReqs.length > 0 ? (
          <div style={{ marginBottom: '1rem' }}>
            <div style={{ color: C.textMute, fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.14em', marginBottom: 8 }}>PROGRAM REQUIREMENTS</div>
            {credReqs.map((cr, i) => (
              <div key={i} style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 5, padding: '8px 12px', marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                  <span style={{ background: cr.required ? 'rgba(239,68,68,0.1)' : 'rgba(74,85,104,0.15)', color: cr.required ? C.red : C.textMute, border: `1px solid ${cr.required ? 'rgba(239,68,68,0.25)' : C.border}`, fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3 }}>
                    {cr.required ? 'REQUIRED' : 'OPTIONAL'}
                  </span>
                  <span style={{ color: C.textMute, fontSize: '0.6rem' }}>{KIND_LABELS[cr.kind] || cr.kind}</span>
                </div>
                <div style={{ color: C.text, fontSize: '0.75rem', fontWeight: 600, marginBottom: 3 }}>{cr.label}</div>
                {cr.notes && <div style={{ color: C.textMute, fontSize: '0.68rem', marginBottom: 4 }}>{cr.notes}</div>}
                {cr.signup_url && (
                  <a href={cr.signup_url} target="_blank" rel="noopener noreferrer" style={{ color: C.green, fontSize: '0.68rem', textDecoration: 'none' }}>
                    → {cr.signup_url.replace(/^https?:\/\//, '')}
                  </a>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div style={{ background: 'rgba(95,143,107,0.04)', border: '1px solid rgba(95,143,107,0.12)', borderRadius: 5, padding: '8px 12px', marginBottom: '1rem', color: C.textMute, fontSize: '0.72rem' }}>
            No specific requirements listed — proceed with test account.
          </div>
        )}

        <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: '1rem' }}>
          <input type="checkbox" checked={skipMode} onChange={e => setSkipMode(e.target.checked)} style={{ accentColor: C.green }} />
          <span style={{ color: C.textSub, fontSize: '0.72rem' }}>Skip — surface scan only</span>
        </label>

        {skipMode ? (
          <div style={{ marginBottom: '1rem' }}>
            <label style={lbl}>REASON FOR SKIPPING *</label>
            <textarea rows={2} value={skipReason} onChange={e => setSkipReason(e.target.value)} placeholder="e.g. No auth required for this scope" style={{ ...inp, resize: 'vertical' }} />
          </div>
        ) : (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div><label style={lbl}>USERNAME / EMAIL</label><input type="text" value={username} onChange={e => setUsername(e.target.value)} style={inp} autoComplete="off" /></div>
              <div><label style={lbl}>PASSWORD</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} style={inp} autoComplete="new-password" /></div>
            </div>
            <div style={{ marginBottom: 12 }}><label style={lbl}>API KEY / TOKEN</label><input type="text" value={apiKey} onChange={e => setApiKey(e.target.value)} style={inp} autoComplete="off" /></div>
            <div style={{ marginBottom: 12 }}><label style={lbl}>OAUTH TOKEN</label><input type="text" value={oauthToken} onChange={e => setOauthToken(e.target.value)} style={inp} autoComplete="off" /></div>
            <div style={{ marginBottom: 12 }}><label style={lbl}>NOTES</label><textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)} style={{ ...inp, resize: 'vertical' }} placeholder="Account tier, limitations, expiry…" /></div>
          </>
        )}

        <div style={{ background: 'rgba(74,85,104,0.1)', border: `1px solid ${C.border}`, borderRadius: 4, padding: '7px 11px', marginBottom: '1rem', color: C.textMute, fontSize: '0.62rem', lineHeight: 1.5 }}>
          Credentials stored encrypted in HashiCorp Vault. Never use personal or production accounts.
        </div>

        {error && <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.25)', borderRadius: 4, padding: '7px 11px', color: C.red, fontSize: '0.72rem', marginBottom: '1rem' }}>{error}</div>}

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '7px 14px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 4, color: C.textSub, fontFamily: MONO, fontSize: '0.68rem', cursor: 'pointer' }}>CANCEL</button>
          <button
            onClick={handleSubmit}
            disabled={submitting || (skipMode && !skipReason.trim())}
            style={{ padding: '7px 16px', background: submitting ? C.border : C.green, color: submitting ? C.textMute : '#0B0C0D', border: 'none', borderRadius: 4, fontFamily: MONO, fontSize: '0.68rem', fontWeight: 700, cursor: submitting ? 'not-allowed' : 'pointer' }}
          >
            {submitting ? 'SAVING…' : skipMode ? 'SKIP → RECON' : 'SAVE TO VAULT → RECON'}
          </button>
        </div>
      </div>
    </div>
  )
}

function elapsed(ts: string) {
  if (!ts) return ''
  const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60000)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  return h < 48 ? `${h}h` : `${Math.floor(h / 24)}d`
}

function WorkflowKanban({ refresh }: { refresh: number }) {
  const [workflows, setWorkflows] = useState<HuntWorkflow[]>([])
  const [loading, setLoading] = useState(true)
  const [actingId, setActingId] = useState<string | null>(null)
  const [credPanelWf, setCredPanelWf] = useState<HuntWorkflow | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await listWorkflows({ limit: 200 })
      setWorkflows(r.data.workflows ?? [])
    } catch { setError('Failed to load workflows') }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load, refresh])

  const handleAction = async (wf: HuntWorkflow, to: string) => {
    setActingId(wf.id)
    try { await transitionWorkflow(wf.id, to); await load() }
    catch (e: any) { setError(e?.response?.data?.detail || `Transition to ${to} failed`) }
    finally { setActingId(null) }
  }

  const handleClose = async (wf: HuntWorkflow) => {
    if (!window.confirm(`Close hunt for "${wf.program_name}"?`)) return
    try { await transitionWorkflow(wf.id, 'CLOSED'); await load() }
    catch (e: any) { setError(e?.response?.data?.detail || 'Could not close') }
  }

  const byState = (s: string) => workflows.filter(w => w.status === s)
  const pending = byState('SELECTED')
  const terminal = workflows.filter(w => w.is_terminal)

  if (loading) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>▓▒░ LOADING HUNTS…</div>

  return (
    <div style={{ padding: '1.25rem 1.5rem' }}>
      {credPanelWf && <CredPanel wf={credPanelWf} onClose={() => setCredPanelWf(null)} onSuccess={load} />}

      {error && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 5, padding: '8px 14px', color: C.red, fontSize: '0.75rem', marginBottom: 12, display: 'flex', justifyContent: 'space-between' }}>
          <span>{error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: C.red, cursor: 'pointer' }}>✕</button>
        </div>
      )}

      {/* Stats */}
      <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.25rem' }}>
        {[
          { label: 'Active', value: workflows.filter(w => !w.is_terminal).length, color: C.text },
          { label: 'Cred Setup', value: byState('CREDENTIAL_SETUP').length, color: byState('CREDENTIAL_SETUP').length > 0 ? C.amber : C.textMute },
          { label: 'HiL Review', value: byState('HIL_REVIEW').length, color: byState('HIL_REVIEW').length > 0 ? C.amber : C.textMute },
          { label: 'Submitted', value: workflows.filter(w => w.status === 'SUBMITTED').length, color: C.green },
          { label: 'Findings', value: workflows.reduce((s, w) => s + w.findings_count, 0), color: C.green },
        ].map(s => (
          <div key={s.label} style={{ textAlign: 'center' }}>
            <div style={{ color: s.color, fontSize: '1.4rem', fontWeight: 700, lineHeight: 1, fontFamily: MONO }}>{s.value}</div>
            <div style={{ color: C.textMute, fontSize: '0.6rem', marginTop: 3, letterSpacing: '0.06em' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Pending */}
      {pending.length > 0 && (
        <div style={{ marginBottom: '1.25rem' }}>
          <div style={{ color: C.amber, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 8 }}>
            PENDING SCOPE ACCEPTANCE ({pending.length})
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
            {pending.map(wf => <WFCard key={wf.id} wf={wf} onAction={handleAction} onClose={handleClose} onCredPanel={setCredPanelWf} actingId={actingId} />)}
          </div>
        </div>
      )}

      {/* Kanban */}
      <div style={{ overflowX: 'auto', paddingBottom: 8 }}>
        <div style={{ display: 'flex', gap: 10, minWidth: `${KANBAN_COLS.length * 215}px` }}>
          {KANBAN_COLS.map(s => {
            const wfs = byState(s)
            const isCredCol = s === 'CREDENTIAL_SETUP'
            return (
              <div key={s} style={{ flex: '0 0 205px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 8, color: isCredCol ? C.amber : C.textMute, fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
                  {STATE_LABELS[s]}
                  {wfs.length > 0 && (
                    <span style={{ background: isCredCol ? 'rgba(217,119,6,0.1)' : '#355E3B', color: isCredCol ? C.amber : C.textMute, borderRadius: 10, padding: '0 5px', fontSize: '0.55rem' }}>
                      {wfs.length}
                    </span>
                  )}
                </div>
                {wfs.length === 0 ? (
                  <div style={{ border: `1px dashed ${isCredCol ? 'rgba(217,119,6,0.2)' : C.border}`, borderRadius: 5, padding: '1.25rem', textAlign: 'center', color: C.textDead, fontSize: '0.65rem' }}>
                    Empty
                  </div>
                ) : (
                  wfs.map(wf => <WFCard key={wf.id} wf={wf} onAction={handleAction} onClose={handleClose} onCredPanel={setCredPanelWf} actingId={actingId} />)
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Terminal */}
      {terminal.length > 0 && (
        <div style={{ marginTop: '1.5rem' }}>
          <div style={{ color: C.textMute, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 8 }}>
            HISTORY — SUBMITTED / CLOSED ({terminal.length})
          </div>
          {terminal.map(wf => (
            <div key={wf.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 12px', border: `1px solid ${C.border}`, borderRadius: 5, marginBottom: 4 }}>
              <span style={{ fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: 3, background: wf.status === 'SUBMITTED' ? 'rgba(95,143,107,0.08)' : '#355E3B', color: wf.status === 'SUBMITTED' ? C.green : C.textMute }}>{STATE_LABELS[wf.status]}</span>
              <span style={{ color: C.textSub, fontSize: '0.75rem', flex: 1 }}>{wf.program_name}</span>
              {wf.findings_count > 0 && <span style={{ color: C.green, fontSize: '0.65rem' }}>{wf.findings_count} findings</span>}
              <span style={{ color: C.textMute, fontSize: '0.62rem' }}>{new Date(wf.updated_at).toLocaleDateString()}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function WFCard({ wf, onAction, onClose, onCredPanel, actingId }: {
  wf: HuntWorkflow; onAction: (wf: HuntWorkflow, to: string) => void
  onClose: (wf: HuntWorkflow) => void; onCredPanel: (wf: HuntWorkflow) => void; actingId: string | null
}) {
  const navigate = useNavigate()
  const pa = PRIMARY_ACTION[wf.status]
  const busy = actingId === wf.id
  const isCredSetup = wf.status === 'CREDENTIAL_SETUP'
  const canAdvance = !isCredSetup && pa && wf.allowed_transitions.includes(pa.to)
  const canClose = wf.allowed_transitions.includes('CLOSED') && pa?.to !== 'CLOSED'
  const pc = PLATFORM_COLORS[wf.platform] || C.textMute

  return (
    <div style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6, padding: '10px 12px', marginBottom: 8 }}>
      <div style={{ color: C.text, fontWeight: 600, fontSize: '0.78rem', marginBottom: 5, lineHeight: 1.3 }}>{wf.program_name}</div>
      <div style={{ display: 'flex', gap: 5, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
        <span style={{ background: `${pc}1a`, color: pc, border: `1px solid ${pc}33`, fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3 }}>
          {wf.platform.toUpperCase().slice(0, 3)}
        </span>
        {wf.findings_count > 0 && (
          <span style={{ background: 'rgba(95,143,107,0.08)', color: C.green, border: '1px solid rgba(95,143,107,0.2)', fontSize: '0.55rem', fontWeight: 700, padding: '1px 5px', borderRadius: 3 }}>
            {wf.findings_count} findings
          </span>
        )}
        <span style={{ color: C.textDead, fontSize: '0.58rem', marginLeft: 'auto' }}>
          {elapsed(wf.transitioned_at?.[wf.status] || wf.updated_at)}
        </span>
      </div>
      <div style={{ display: 'flex', gap: 5 }}>
        {isCredSetup ? (
          <button onClick={() => onCredPanel(wf)} style={{ flex: 1, padding: '4px 8px', borderRadius: 3, background: 'rgba(217,119,6,0.15)', color: C.amber, border: '1px solid rgba(217,119,6,0.3)', fontFamily: MONO, fontSize: '0.62rem', fontWeight: 700, cursor: 'pointer' }}>
            Setup Creds →
          </button>
        ) : canAdvance ? (
          <button onClick={() => onAction(wf, pa!.to)} disabled={busy} style={{ flex: 1, padding: '4px 8px', borderRadius: 3, background: busy ? C.border : C.green, color: busy ? C.textMute : '#0B0C0D', border: 'none', fontFamily: MONO, fontSize: '0.62rem', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer', opacity: busy ? 0.6 : 1 }}>
            {busy ? '…' : pa!.label}
          </button>
        ) : null}
        {wf.status === 'HIL_REVIEW' && (
          <button onClick={() => navigate('/findings')} style={{ padding: '4px 8px', borderRadius: 3, background: 'transparent', color: C.textSub, border: `1px solid ${C.border}`, fontFamily: MONO, fontSize: '0.62rem', cursor: 'pointer' }}>Review</button>
        )}
        {canClose && (
          <button onClick={() => onClose(wf)} style={{ padding: '4px 7px', borderRadius: 3, background: 'transparent', color: C.textMute, border: `1px solid ${C.border}`, fontFamily: MONO, fontSize: '0.62rem', cursor: 'pointer' }}>✕</button>
        )}
      </div>
    </div>
  )
}

// ─── Main HuntOps page ────────────────────────────────────────────────────────

export default function HuntOps() {
  const [tab, setTab] = useState<'browse' | 'hunts'>('hunts')
  const [huntRefresh, setHuntRefresh] = useState(0)
  const navigate = useNavigate()

  const tabs = [
    { id: 'hunts',  label: 'ACTIVE HUNTS' },
    { id: 'browse', label: 'BROWSE PROGRAMS' },
  ]

  return (
    <div style={{ background: C.bg, minHeight: '100vh', fontFamily: MONO, display: 'flex', flexDirection: 'column' }}>
      {/* Header */}
      <div style={{ padding: '1rem 1.5rem 0', background: C.card, borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 2 }}>
          <span style={{ color: C.green, fontSize: '1.2rem' }}>◈</span>
          <h1 style={{ color: C.text, margin: 0, fontSize: '1.1rem', fontWeight: 700, letterSpacing: '0.05em' }}>HUNT OPS</h1>
          <span style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.1em' }}>Programs · Workflows · Credentials</span>
          <div style={{ marginLeft: 'auto' }}>
            <button
              onClick={() => { setTab('browse') }}
              style={{ padding: '5px 12px', borderRadius: 4, background: C.green, color: '#0B0C0D', border: 'none', fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer', letterSpacing: '0.08em' }}
            >
              + NEW HUNT
            </button>
          </div>
        </div>
        <TabBar tabs={tabs} active={tab} onChange={(id) => setTab(id as any)} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {tab === 'browse' && <OpportunityBrowser onHuntLaunched={() => { setTab('hunts'); setHuntRefresh(r => r + 1) }} />}
        {tab === 'hunts'  && <WorkflowKanban refresh={huntRefresh} />}
      </div>
    </div>
  )
}
