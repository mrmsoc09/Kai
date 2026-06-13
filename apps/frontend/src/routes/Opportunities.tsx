import React, { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  createWorkflow,
  dispatchOpportunityScans,
  getScanQueueSettings,
  getOpportunity,
  getScanSuggestions,
  listOpportunities,
  updateScanQueueSettings,
} from '../lib/api'

type QueueStatus = 'queued' | 'dispatching' | 'dispatched' | 'error'

type CredentialRequirement = {
  kind: string
  label: string
  signup_url: string
  notes: string
  required: boolean
}

type QueueTarget = {
  subject_key: string
  subject_type: string
  label: string
  recommended_workflow: string
}

type AccountPreparation = {
  required_account_types: string[]
  hunter_account_label?: string | null
  hunter_account_signup_url?: string | null
  program_account_label?: string | null
  program_account_signup_url?: string | null
  suggested_username: string
  suggested_email_alias: string
  suggested_password: string
  suggested_pin?: string | null
  recommended_notes: string[]
}

interface Opportunity {
  id: string
  name: string
  organization: string
  platform: string
  access_type: string
  program_url: string
  scope_url: string
  scope_summary: string
  scope_domains: string[]
  max_payout_usd: number
  min_payout_usd: number
  vdp_only: boolean
  response_sla_days: number
  tags: string[]
  vuln_types: string[]
  priority_score: number
  is_public: boolean
  payout_label: string
  notes: string
  credential_requirements: CredentialRequirement[]
  queue_targets: QueueTarget[]
  account_prep: AccountPreparation
  needs_credentials: boolean
}

type QueueItem = {
  id: string
  opportunityId: string
  name: string
  organization: string
  platform: string
  accessType: string
  programUrl: string
  subjectKey: string
  subjectType: string
  recommendedWorkflow: string
  needsCredentials: boolean
  credentialRequirements: CredentialRequirement[]
  accountPrep: AccountPreparation
  status: QueueStatus
  addedAt: string
  lastError?: string | null
}

type GuardAction = {
  kind: 'scan' | 'workflow'
  opportunity: Opportunity
  target: QueueTarget
}

type ScanSuggestion = {
  opportunity_id: string
  name: string
  organization: string
  platform: string
  score: number
  reasons: string[]
  matching_accounts: string[]
}

const PAGE_SIZE = 24
const PLATFORMS = ['', 'hackerone', 'bugcrowd', 'intigriti', 'vrp', 'government_cvd']
type SortKey = 'score' | 'payout' | 'name'
const SCAN_QUEUE_KEY = 'kai.opportunities.scan-queue.v1'

const PLATFORM_COLORS: Record<string, string> = {
  hackerone: '#25a244',
  bugcrowd: '#D97706',
  intigriti: '#0f766e',
  vrp: '#2563eb',
  government_cvd: '#b45309',
}
const PLATFORM_LABELS: Record<string, string> = {
  hackerone: 'HackerOne',
  bugcrowd: 'Bugcrowd',
  intigriti: 'Intigriti',
  vrp: 'VRP',
  government_cvd: 'Gov CVD',
}

function gBtn(v: 'primary' | 'ghost' | 'danger' | 'disabled'): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '7px 12px',
    borderRadius: 6,
    fontFamily: 'inherit',
    fontSize: '0.74rem',
    fontWeight: 700,
    letterSpacing: '0.05em',
    cursor: v === 'disabled' ? 'not-allowed' : 'pointer',
    border: 'none',
    transition: 'transform 0.12s ease, opacity 0.12s ease',
  }
  if (v === 'primary') return { ...base, background: '#b7d77a', color: '#10150f' }
  if (v === 'danger') return { ...base, background: '#7f1d1d', color: '#fca5a5' }
  if (v === 'ghost') return { ...base, background: 'transparent', border: '1px solid #355E3B', color: '#8FAF9B' }
  return { ...base, background: '#27372a', color: '#5f765f' }
}

function badgeStyle(color: string): React.CSSProperties {
  return {
    background: `${color}1f`,
    color,
    border: `1px solid ${color}44`,
    fontSize: '0.62rem',
    fontWeight: 700,
    padding: '2px 7px',
    borderRadius: 999,
    letterSpacing: '0.06em',
  }
}

function fieldCardStyle(): React.CSSProperties {
  return {
    border: '1px solid #2B4030',
    borderRadius: 8,
    background: '#111917',
    padding: '0.7rem 0.8rem',
  }
}

function loadScanQueue(): QueueItem[] {
  if (typeof window === 'undefined') return []
  const raw = window.localStorage.getItem(SCAN_QUEUE_KEY)
  if (!raw) return []
  try {
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter((item): item is QueueItem => (
      item !== null &&
      typeof item === 'object' &&
      typeof item.id === 'string' &&
      typeof item.opportunityId === 'string' &&
      typeof item.subjectKey === 'string' &&
      typeof item.status === 'string'
    ))
  } catch {
    return []
  }
}

function saveScanQueue(items: QueueItem[]) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(SCAN_QUEUE_KEY, JSON.stringify(items))
}

function buildQueueItem(opportunity: Opportunity, target: QueueTarget, existing?: QueueItem): QueueItem {
  return {
    id: existing?.id ?? crypto.randomUUID(),
    opportunityId: opportunity.id,
    name: opportunity.name,
    organization: opportunity.organization,
    platform: opportunity.platform,
    accessType: opportunity.access_type,
    programUrl: opportunity.program_url,
    subjectKey: target.subject_key,
    subjectType: target.subject_type,
    recommendedWorkflow: target.recommended_workflow,
    needsCredentials: opportunity.needs_credentials,
    credentialRequirements: opportunity.credential_requirements,
    accountPrep: opportunity.account_prep,
    status: existing?.status ?? 'queued',
    addedAt: existing?.addedAt ?? new Date().toISOString(),
    lastError: existing?.lastError ?? null,
  }
}

function targetForOpportunity(opportunity: Opportunity, selectedTargets: Record<string, number>): QueueTarget {
  const index = selectedTargets[opportunity.id] ?? 0
  return opportunity.queue_targets[index] ?? opportunity.queue_targets[0] ?? {
    subject_key: opportunity.scope_url || opportunity.program_url,
    subject_type: 'url',
    label: opportunity.scope_url || opportunity.program_url,
    recommended_workflow: 'workflow_passive_triage',
  }
}

function AccessConfirmModal({
  action,
  loading,
  onConfirm,
  onCancel,
}: {
  action: GuardAction
  loading: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  const [checked, setChecked] = useState(false)
  const label = action.kind === 'scan' ? 'Start Scan' : 'Open Workflow'
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.78)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2000, padding: '1rem' }}>
      <div style={{ width: '100%', maxWidth: 520, background: '#101614', border: '1px solid #355E3B', borderRadius: 12, padding: '1.4rem' }}>
        <div style={{ color: '#d97706', fontSize: '0.68rem', fontWeight: 800, letterSpacing: '0.12em', marginBottom: 10 }}>
          ACCESS CONFIRMATION REQUIRED
        </div>
        <div style={{ color: '#dcead8', fontSize: '1rem', fontWeight: 700, marginBottom: 8 }}>{action.opportunity.name}</div>
        <p style={{ color: '#8FAF9B', fontSize: '0.82rem', lineHeight: 1.55, margin: '0 0 10px' }}>
          This opportunity is not marked public. Only continue if you already have explicit authorization or invitation from the program owner.
        </p>
        <p style={{ color: '#6F8E7A', fontSize: '0.76rem', lineHeight: 1.55, margin: '0 0 16px' }}>
          Selected target: <span style={{ color: '#b7d77a' }}>{action.target.label}</span>
        </p>
        <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer', marginBottom: 18 }}>
          <input type='checkbox' checked={checked} onChange={e => setChecked(e.target.checked)} style={{ marginTop: 3 }} />
          <span style={{ color: '#8FAF9B', fontSize: '0.78rem', lineHeight: 1.5 }}>
            I confirm I have authorization to create accounts and run testing for this opportunity.
          </span>
        </label>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button onClick={onCancel} style={gBtn('ghost')}>Cancel</button>
          <button onClick={onConfirm} disabled={!checked || loading} style={gBtn(checked && !loading ? 'primary' : 'disabled')}>
            {loading ? `${label}…` : label}
          </button>
        </div>
      </div>
    </div>
  )
}

function AccountPrepModal({
  opportunity,
  onClose,
}: {
  opportunity: Pick<Opportunity, 'name' | 'organization' | 'program_url' | 'credential_requirements' | 'account_prep' | 'access_type' | 'notes'>
  onClose: () => void
}) {
  const prep = opportunity.account_prep
  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 2100, padding: '1rem' }}>
      <div style={{ width: '100%', maxWidth: 760, maxHeight: '88vh', overflowY: 'auto', background: '#0f1413', border: '1px solid #355E3B', borderRadius: 14, padding: '1.35rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start', marginBottom: 14 }}>
          <div>
            <div style={{ color: '#dcead8', fontSize: '1.05rem', fontWeight: 700 }}>{opportunity.name}</div>
            <div style={{ color: '#6F8E7A', fontSize: '0.76rem', marginTop: 4 }}>{opportunity.organization}</div>
          </div>
          <button onClick={onClose} style={gBtn('ghost')}>Close</button>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 14 }}>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Suggested Username</div>
            <div style={{ color: '#dcead8', fontFamily: 'monospace', fontSize: '0.84rem' }}>{prep.suggested_username}</div>
          </div>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Suggested Email Alias</div>
            <div style={{ color: '#dcead8', fontFamily: 'monospace', fontSize: '0.84rem' }}>{prep.suggested_email_alias}</div>
          </div>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Suggested Password</div>
            <div style={{ color: '#dcead8', fontFamily: 'monospace', fontSize: '0.84rem', wordBreak: 'break-all' }}>{prep.suggested_password}</div>
          </div>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Suggested PIN</div>
            <div style={{ color: '#dcead8', fontFamily: 'monospace', fontSize: '0.84rem' }}>{prep.suggested_pin || 'Not suggested'}</div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: 12, marginBottom: 14 }}>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>BBP Suggested Accounts</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {prep.required_account_types.map(kind => (
                <span key={kind} style={badgeStyle('#b7d77a')}>{kind.replace(/_/g, ' ')}</span>
              ))}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {prep.hunter_account_label && prep.hunter_account_signup_url && (
                <a href={prep.hunter_account_signup_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.8rem' }}>
                  Create {prep.hunter_account_label}
                </a>
              )}
              {prep.program_account_label && prep.program_account_signup_url && (
                <a href={prep.program_account_signup_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.8rem' }}>
                  Create {prep.program_account_label}
                </a>
              )}
              <a href={opportunity.program_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.8rem' }}>
                Open program page
              </a>
            </div>
          </div>
          <div style={fieldCardStyle()}>
            <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Program Notes</div>
            <div style={{ color: '#8FAF9B', fontSize: '0.8rem', lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{opportunity.notes || 'No additional program notes.'}</div>
          </div>
        </div>

        <div style={{ ...fieldCardStyle(), marginBottom: 14 }}>
          <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Credential Requirements</div>
          {opportunity.credential_requirements.length === 0 ? (
            <div style={{ color: '#8FAF9B', fontSize: '0.8rem' }}>No additional credentials are listed for the initial scan.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {opportunity.credential_requirements.map((requirement) => (
                <div key={`${requirement.kind}-${requirement.label}`} style={{ borderTop: '1px solid #203028', paddingTop: 10 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center', marginBottom: 4 }}>
                    <span style={{ color: '#dcead8', fontSize: '0.82rem', fontWeight: 700 }}>{requirement.label}</span>
                    <span style={badgeStyle(requirement.required ? '#f59e0b' : '#6F8E7A')}>{requirement.required ? 'Required' : 'Optional'}</span>
                  </div>
                  <div style={{ color: '#8FAF9B', fontSize: '0.78rem', lineHeight: 1.5 }}>{requirement.notes || 'No extra notes provided.'}</div>
                  {requirement.signup_url && (
                    <div style={{ marginTop: 6 }}>
                      <a href={requirement.signup_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.78rem' }}>
                        Account creation link
                      </a>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={fieldCardStyle()}>
          <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.09em', marginBottom: 8 }}>Agent Recommendations</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {prep.recommended_notes.map((note) => (
              <div key={note} style={{ color: '#8FAF9B', fontSize: '0.8rem', lineHeight: 1.5 }}>
                • {note}
              </div>
            ))}
            <div style={{ color: '#6F8E7A', fontSize: '0.76rem', lineHeight: 1.5, marginTop: 4 }}>
              Access mode: {opportunity.access_type.replace(/_/g, ' ')}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function OpportunityCard({
  opportunity,
  selectedTarget,
  targetIndex,
  queued,
  scanning,
  workflowing,
  onTargetChange,
  onAddToQueue,
  onOpenPrep,
  onStartScan,
  onOpenWorkflow,
}: {
  opportunity: Opportunity
  selectedTarget: QueueTarget
  targetIndex: number
  queued: boolean
  scanning: boolean
  workflowing: boolean
  onTargetChange: (value: number) => void
  onAddToQueue: () => void
  onOpenPrep: () => void
  onStartScan: () => void
  onOpenWorkflow: () => void
}) {
  const platformColor = PLATFORM_COLORS[opportunity.platform] || '#6F8E7A'
  const prep = opportunity.account_prep
  return (
    <div style={{ background: 'linear-gradient(180deg, #111917 0%, #0d1312 100%)', border: '1px solid #29412f', borderRadius: 14, padding: '1rem', display: 'flex', flexDirection: 'column', gap: 12, boxShadow: '0 10px 30px rgba(0,0,0,0.14)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start' }}>
        <div>
          <div style={{ color: '#dcead8', fontWeight: 700, fontSize: '0.95rem', lineHeight: 1.35 }}>{opportunity.name}</div>
          <div style={{ color: '#6F8E7A', fontSize: '0.74rem', marginTop: 3 }}>{opportunity.organization}</div>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, justifyContent: 'flex-end' }}>
          {opportunity.is_public ? <span style={badgeStyle('#4ade80')}>Public</span> : <span style={badgeStyle('#f59e0b')}>Authorized Access</span>}
          <span style={badgeStyle(platformColor)}>{PLATFORM_LABELS[opportunity.platform] || opportunity.platform}</span>
        </div>
      </div>

      <div style={{ color: '#8FAF9B', fontSize: '0.78rem', lineHeight: 1.55 }}>{opportunity.scope_summary}</div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {opportunity.scope_domains.slice(0, 4).map((domain) => (
          <span key={domain} style={badgeStyle('#355E3B')}>{domain}</span>
        ))}
        {opportunity.scope_domains.length === 0 && <span style={badgeStyle('#355E3B')}>Use scope page</span>}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
        <div style={fieldCardStyle()}>
          <div style={{ color: '#6F8E7A', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Payout</div>
          <div style={{ color: '#dcead8', fontSize: '0.78rem', fontWeight: 700 }}>{opportunity.payout_label}</div>
        </div>
        <div style={fieldCardStyle()}>
          <div style={{ color: '#6F8E7A', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Priority</div>
          <div style={{ color: '#dcead8', fontSize: '0.78rem', fontWeight: 700 }}>{Math.round(opportunity.priority_score * 100)} / 100</div>
        </div>
        <div style={fieldCardStyle()}>
          <div style={{ color: '#6F8E7A', fontSize: '0.65rem', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 4 }}>Access</div>
          <div style={{ color: '#dcead8', fontSize: '0.78rem', fontWeight: 700 }}>{opportunity.access_type.replace(/_/g, ' ')}</div>
        </div>
      </div>

      <div style={{ ...fieldCardStyle(), display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center' }}>
          <div style={{ color: '#dcead8', fontSize: '0.8rem', fontWeight: 700 }}>Account Preparation</div>
          {queued && <span style={badgeStyle('#8fd0ff')}>In Queue</span>}
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {prep.required_account_types.map((kind) => (
            <span key={kind} style={badgeStyle('#b7d77a')}>{kind.replace(/_/g, ' ')}</span>
          ))}
          {prep.required_account_types.length === 0 && <span style={badgeStyle('#6F8E7A')}>No account required</span>}
        </div>
        <div style={{ color: '#8FAF9B', fontSize: '0.76rem', lineHeight: 1.5 }}>
          Suggested username: <span style={{ color: '#dcead8', fontFamily: 'monospace' }}>{prep.suggested_username}</span>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {prep.hunter_account_label && prep.hunter_account_signup_url && (
            <a href={prep.hunter_account_signup_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.76rem' }}>
              Create {prep.hunter_account_label}
            </a>
          )}
          {prep.program_account_label && prep.program_account_signup_url && (
            <a href={prep.program_account_signup_url} target='_blank' rel='noreferrer' style={{ color: '#8fd0ff', fontSize: '0.76rem' }}>
              Create {prep.program_account_label}
            </a>
          )}
          <button onClick={onOpenPrep} style={{ ...gBtn('ghost'), padding: '4px 9px', fontSize: '0.68rem' }}>Full Prep</button>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ color: '#6F8E7A', fontSize: '0.68rem', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Scan Target</div>
        <select
          value={targetIndex}
          onChange={(event) => onTargetChange(Number(event.target.value))}
          style={{ background: '#0d1312', border: '1px solid #29412f', borderRadius: 8, color: '#dcead8', fontFamily: 'inherit', fontSize: '0.78rem', padding: '8px 10px' }}
        >
          {opportunity.queue_targets.map((target, index) => (
            <option key={`${opportunity.id}-${target.subject_key}`} value={index}>{target.label} ({target.subject_type})</option>
          ))}
        </select>
        <div style={{ color: '#8FAF9B', fontSize: '0.74rem' }}>
          Workflow: <span style={{ color: '#dcead8' }}>{selectedTarget.recommended_workflow}</span>
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button onClick={onAddToQueue} style={gBtn('ghost')}>{queued ? 'Queued' : 'Add To Queue'}</button>
        <button onClick={onStartScan} disabled={scanning} style={gBtn(scanning ? 'disabled' : 'primary')}>
          {scanning ? 'Starting Scan…' : 'Start Scan'}
        </button>
        <button onClick={onOpenWorkflow} disabled={workflowing} style={gBtn(workflowing ? 'disabled' : 'ghost')}>
          {workflowing ? 'Opening…' : 'Open Workflow'}
        </button>
      </div>
    </div>
  )
}

export default function Opportunities() {
  const navigate = useNavigate()

  const [opportunities, setOpportunities] = useState<Opportunity[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const [platform, setPlatform] = useState('')
  const [publicOnly, setPublicOnly] = useState(false)
  const [sort, setSort] = useState<SortKey>('score')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  const [queueItems, setQueueItems] = useState<QueueItem[]>([])
  const [scanSuggestions, setScanSuggestions] = useState<ScanSuggestion[]>([])
  const [suggestionsLoading, setSuggestionsLoading] = useState(true)
  const [selectedTargets, setSelectedTargets] = useState<Record<string, number>>({})
  const [scanLoadingIds, setScanLoadingIds] = useState<Record<string, boolean>>({})
  const [workflowLoadingIds, setWorkflowLoadingIds] = useState<Record<string, boolean>>({})
  const [guardAction, setGuardAction] = useState<GuardAction | null>(null)
  const [prepOpportunity, setPrepOpportunity] = useState<Opportunity | null>(null)

  const [settingsLoading, setSettingsLoading] = useState(true)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [minConcurrent, setMinConcurrent] = useState(1)
  const [maxConcurrent, setMaxConcurrent] = useState(3)
  const [settingsError, setSettingsError] = useState<string | null>(null)

  useEffect(() => {
    setQueueItems(loadScanQueue())
  }, [])

  useEffect(() => {
    saveScanQueue(queueItems)
  }, [queueItems])

  useEffect(() => {
    if (!notice) return
    const timeout = window.setTimeout(() => setNotice(null), 4000)
    return () => window.clearTimeout(timeout)
  }, [notice])

  const loadOpportunities = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await listOpportunities({
        platform: platform || undefined,
        public_only: publicOnly || undefined,
        search: search || undefined,
        sort_by: sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      setOpportunities(response.data.opportunities)
      setTotal(response.data.total)
    } catch {
      setError('Failed to load opportunities. Verify the backend is running and the route is reachable.')
    } finally {
      setLoading(false)
    }
  }, [page, platform, publicOnly, search, sort])

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true)
    setSettingsError(null)
    try {
      const response = await getScanQueueSettings()
      setMinConcurrent(response.data.min_concurrent)
      setMaxConcurrent(response.data.max_concurrent)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setSettingsError(typeof detail === 'string' ? detail : 'Unable to load queue concurrency settings.')
    } finally {
      setSettingsLoading(false)
    }
  }, [])

  const loadSuggestions = useCallback(async () => {
    setSuggestionsLoading(true)
    try {
      const response = await getScanSuggestions(8)
      setScanSuggestions(Array.isArray(response.data?.items) ? response.data.items : [])
    } catch {
      setScanSuggestions([])
    } finally {
      setSuggestionsLoading(false)
    }
  }, [])

  useEffect(() => { void loadOpportunities() }, [loadOpportunities])
  useEffect(() => { void loadSettings() }, [loadSettings])
  useEffect(() => { void loadSuggestions() }, [loadSuggestions])
  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setSearch(searchInput)
      setPage(0)
    }, 300)
    return () => window.clearTimeout(timeout)
  }, [searchInput])
  useEffect(() => { setPage(0) }, [platform, publicOnly, sort])

  const queueLookup = new Set(queueItems.map(item => `${item.opportunityId}::${item.subjectKey}`))

  const getQueuedItem = useCallback((opportunityId: string, subjectKey: string) => {
    return queueItems.find(item => item.opportunityId === opportunityId && item.subjectKey === subjectKey) ?? null
  }, [queueItems])

  const upsertQueueItem = useCallback((opportunity: Opportunity, target: QueueTarget) => {
    const existing = getQueuedItem(opportunity.id, target.subject_key)
    const nextItem = buildQueueItem(opportunity, target, existing ?? undefined)
    setQueueItems((current) => {
      const matchIndex = current.findIndex(item => item.opportunityId === opportunity.id && item.subjectKey === target.subject_key)
      if (matchIndex >= 0) {
        const next = [...current]
        next[matchIndex] = nextItem
        return next
      }
      return [...current, nextItem]
    })
    return nextItem
  }, [getQueuedItem])

  const updateQueueItem = useCallback((id: string, patch: Partial<QueueItem>) => {
    setQueueItems((current) => current.map(item => item.id === id ? { ...item, ...patch } : item))
  }, [])

  const dispatchItems = useCallback(async (items: QueueItem[]) => {
    if (items.length === 0) return
    const nextLoading: Record<string, boolean> = {}
    items.forEach(item => { nextLoading[item.id] = true })
    setScanLoadingIds((current) => ({ ...current, ...nextLoading }))
    setQueueItems((current) => current.map(item => (
      items.some(candidate => candidate.id === item.id)
        ? { ...item, status: 'dispatching', lastError: null }
        : item
    )))
    try {
      const response = await dispatchOpportunityScans({
        items: items.map((item) => ({
          opportunity_id: item.opportunityId,
          subject_key: item.subjectKey,
          subject_type: item.subjectType,
          recommended_workflow: item.recommendedWorkflow,
        })),
        force: true,
        safe_mode: true,
      })
      const queued = Array.isArray(response.data?.queued) ? response.data.queued : []
      const errors = Array.isArray(response.data?.errors) ? response.data.errors : []

      setQueueItems((current) => current.map((item) => {
        const localIndex = items.findIndex(candidate => candidate.id === item.id)
        if (localIndex < 0) return item
        const queuedMatch = queued.find((row: { item_index: number }) => row.item_index === localIndex)
        if (queuedMatch) {
          return { ...item, status: 'dispatched', lastError: null }
        }
        const errorMatch = errors.find((row: { index: number; error?: string }) => row.index === localIndex)
        return {
          ...item,
          status: 'error',
          lastError: typeof errorMatch?.error === 'string' ? errorMatch.error : 'Dispatch failed',
        }
      }))

      if (errors.length > 0) {
        setError(errors.map((row: { error?: string }) => row.error || 'Dispatch failed').join(' | '))
      }
      if (queued.length > 0) {
        setNotice(`${queued.length} scan${queued.length === 1 ? '' : 's'} dispatched to the backend scan queue.`)
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      const message = typeof detail === 'string' ? detail : 'Unable to dispatch scan queue items.'
      setError(message)
      setQueueItems((current) => current.map(item => (
        items.some(candidate => candidate.id === item.id)
          ? { ...item, status: 'error', lastError: message }
          : item
      )))
    } finally {
      setScanLoadingIds((current) => {
        const next = { ...current }
        items.forEach(item => { delete next[item.id] })
        return next
      })
    }
  }, [])

  const handleAddToQueue = useCallback((opportunity: Opportunity) => {
    const target = targetForOpportunity(opportunity, selectedTargets)
    const existing = getQueuedItem(opportunity.id, target.subject_key)
    upsertQueueItem(opportunity, target)
    setNotice(existing ? 'Scan target already existed in the queue. Its details were refreshed.' : 'Opportunity added to the scan queue.')
  }, [getQueuedItem, selectedTargets, upsertQueueItem])

  const launchFromOpportunity = useCallback(async (opportunity: Opportunity) => {
    const target = targetForOpportunity(opportunity, selectedTargets)
    if (!opportunity.is_public) {
      setGuardAction({ kind: 'scan', opportunity, target })
      return
    }
    const queueItem = upsertQueueItem(opportunity, target)
    await dispatchItems([queueItem])
  }, [dispatchItems, selectedTargets, upsertQueueItem])

  const launchQueuedItem = useCallback(async (item: QueueItem) => {
    await dispatchItems([item])
  }, [dispatchItems])

  const launchAllQueued = useCallback(async () => {
    const queued = queueItems.filter(item => item.status === 'queued' || item.status === 'error')
    await dispatchItems(queued)
  }, [dispatchItems, queueItems])

  const handleWorkflowCreate = useCallback(async (opportunity: Opportunity) => {
    const target = targetForOpportunity(opportunity, selectedTargets)
    if (!opportunity.is_public) {
      setGuardAction({ kind: 'workflow', opportunity, target })
      return
    }
    setWorkflowLoadingIds((current) => ({ ...current, [opportunity.id]: true }))
    try {
      await createWorkflow(opportunity.id)
      navigate('/workflows')
    } catch (err: any) {
      if (err?.response?.status === 409) {
        navigate('/workflows')
        return
      }
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Unable to open workflow for this opportunity.')
    } finally {
      setWorkflowLoadingIds((current) => {
        const next = { ...current }
        delete next[opportunity.id]
        return next
      })
    }
  }, [navigate, selectedTargets])

  const confirmGuardAction = useCallback(async () => {
    if (!guardAction) return
    const { kind, opportunity, target } = guardAction
    setGuardAction(null)
    if (kind === 'scan') {
      const queueItem = upsertQueueItem(opportunity, target)
      await dispatchItems([queueItem])
      return
    }
    await handleWorkflowCreate(opportunity)
  }, [dispatchItems, guardAction, handleWorkflowCreate, upsertQueueItem])

  const saveSettings = useCallback(async () => {
    if (minConcurrent > maxConcurrent) {
      setSettingsError('Minimum concurrent scans cannot exceed the maximum.')
      return
    }
    setSettingsSaving(true)
    setSettingsError(null)
    try {
      const response = await updateScanQueueSettings({ min_concurrent: minConcurrent, max_concurrent: maxConcurrent })
      setMinConcurrent(response.data.min_concurrent)
      setMaxConcurrent(response.data.max_concurrent)
      setNotice('Parallel scan settings saved to the backend.')
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setSettingsError(typeof detail === 'string' ? detail : 'Unable to save queue settings.')
    } finally {
      setSettingsSaving(false)
    }
  }, [maxConcurrent, minConcurrent])

  const queueSuggestedOpportunity = useCallback(async (suggestion: ScanSuggestion) => {
    try {
      const inView = opportunities.find((item) => item.id === suggestion.opportunity_id)
      const opportunity = inView ?? (await getOpportunity(suggestion.opportunity_id)).data
      const target = targetForOpportunity(opportunity, selectedTargets)
      upsertQueueItem(opportunity, target)
      setNotice(`Queued suggested opportunity: ${opportunity.name}`)
    } catch {
      setError('Unable to queue the suggested opportunity.')
    }
  }, [opportunities, selectedTargets, upsertQueueItem])

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const queuedCount = queueItems.filter(item => item.status === 'queued' || item.status === 'error').length
  const dispatchedCount = queueItems.filter(item => item.status === 'dispatched').length

  return (
    <div style={{ padding: '1.5rem 1.8rem', maxWidth: 1600 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.2rem' }}>
        <div>
          <h1 style={{ color: '#dcead8', margin: 0, fontSize: '1.5rem', fontWeight: 800, letterSpacing: '-0.03em' }}>Opportunity Queue Console</h1>
          <p style={{ color: '#6F8E7A', margin: '6px 0 0', fontSize: '0.82rem', maxWidth: 860, lineHeight: 1.55 }}>
            Add opportunities to the scan queue, set how many scans may run in parallel, start individual opportunities, and review BBP-suggested account creation details before deeper authenticated scanning.
          </p>
        </div>
        <Link to='/scan-pool' style={{ ...gBtn('ghost'), textDecoration: 'none', display: 'inline-flex', alignItems: 'center' }}>Open Scan Pool</Link>
      </div>

      {error && (
        <div style={{ background: 'rgba(127,29,29,0.25)', border: '1px solid rgba(248,113,113,0.28)', borderRadius: 10, padding: '0.8rem 1rem', color: '#fca5a5', fontSize: '0.8rem', marginBottom: '1rem' }}>
          {error}
        </div>
      )}
      {notice && (
        <div style={{ background: 'rgba(183,215,122,0.12)', border: '1px solid rgba(183,215,122,0.28)', borderRadius: 10, padding: '0.8rem 1rem', color: '#dcead8', fontSize: '0.8rem', marginBottom: '1rem' }}>
          {notice}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.8fr) minmax(320px, 0.9fr)', gap: 16, alignItems: 'start' }}>
        <div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: '1rem', alignItems: 'center' }}>
            <input
              type='text'
              placeholder='Search programs, organizations, domains…'
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
              style={{ background: '#0f1413', border: '1px solid #29412f', borderRadius: 8, color: '#dcead8', fontFamily: 'inherit', fontSize: '0.8rem', padding: '8px 11px', width: 260 }}
            />
            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
              {PLATFORMS.map((value) => (
                <button key={value} onClick={() => setPlatform(value)} style={{ ...gBtn(platform === value ? 'primary' : 'ghost'), padding: '6px 10px', fontSize: '0.69rem' }}>
                  {PLATFORM_LABELS[value] || 'All'}
                </button>
              ))}
            </div>
            <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)} style={{ background: '#0f1413', border: '1px solid #29412f', borderRadius: 8, color: '#dcead8', fontFamily: 'inherit', fontSize: '0.76rem', padding: '7px 10px' }}>
              <option value='score'>Sort: Score</option>
              <option value='payout'>Sort: Payout</option>
              <option value='name'>Sort: Name</option>
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#8FAF9B', fontSize: '0.76rem' }}>
              <input type='checkbox' checked={publicOnly} onChange={(event) => setPublicOnly(event.target.checked)} />
              Public only
            </label>
            {!loading && (
              <span style={{ color: '#6F8E7A', fontSize: '0.74rem', marginLeft: 'auto' }}>
                {total} opportunities • page {page + 1} / {totalPages}
              </span>
            )}
          </div>

          {loading ? (
            <div style={{ color: '#6F8E7A', textAlign: 'center', padding: '4rem 0', fontSize: '0.85rem' }}>Loading opportunities…</div>
          ) : opportunities.length === 0 ? (
            <div style={{ border: '1px dashed #29412f', borderRadius: 12, padding: '3rem', color: '#8FAF9B', textAlign: 'center' }}>
              No opportunities matched the current filters.
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14 }}>
              {opportunities.map((opportunity) => {
                const selectedTarget = targetForOpportunity(opportunity, selectedTargets)
                const queued = queueLookup.has(`${opportunity.id}::${selectedTarget.subject_key}`)
                const queueItem = getQueuedItem(opportunity.id, selectedTarget.subject_key)
                const scanBusy = Boolean(queueItem && scanLoadingIds[queueItem.id])
                const workflowBusy = Boolean(workflowLoadingIds[opportunity.id])
                return (
                  <OpportunityCard
                    key={opportunity.id}
                    opportunity={opportunity}
                    selectedTarget={selectedTarget}
                    targetIndex={selectedTargets[opportunity.id] ?? 0}
                    queued={queued}
                    scanning={scanBusy}
                    workflowing={workflowBusy}
                    onTargetChange={(value) => setSelectedTargets((current) => ({ ...current, [opportunity.id]: value }))}
                    onAddToQueue={() => handleAddToQueue(opportunity)}
                    onOpenPrep={() => setPrepOpportunity(opportunity)}
                    onStartScan={() => void launchFromOpportunity(opportunity)}
                    onOpenWorkflow={() => void handleWorkflowCreate(opportunity)}
                  />
                )
              })}
            </div>
          )}

          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: 8, justifyContent: 'center', marginTop: '1.2rem' }}>
              <button onClick={() => setPage(current => Math.max(0, current - 1))} disabled={page === 0} style={gBtn(page === 0 ? 'disabled' : 'ghost')}>Prev</button>
              <span style={{ color: '#8FAF9B', fontSize: '0.8rem', padding: '8px 4px' }}>{page + 1} / {totalPages}</span>
              <button onClick={() => setPage(current => Math.min(totalPages - 1, current + 1))} disabled={page >= totalPages - 1} style={gBtn(page >= totalPages - 1 ? 'disabled' : 'ghost')}>Next</button>
            </div>
          )}
        </div>

        <aside style={{ position: 'sticky', top: 16, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ background: '#0f1413', border: '1px solid #29412f', borderRadius: 14, padding: '1rem' }}>
            <div style={{ color: '#dcead8', fontSize: '0.95rem', fontWeight: 700, marginBottom: 4 }}>Suggested Queue</div>
            <div style={{ color: '#6F8E7A', fontSize: '0.76rem', lineHeight: 1.5, marginBottom: 12 }}>
              Rank opportunities that already have imported hunter accounts or credential coverage.
            </div>
            {suggestionsLoading ? (
              <div style={{ color: '#6F8E7A', fontSize: '0.78rem' }}>Loading suggestions…</div>
            ) : scanSuggestions.length === 0 ? (
              <div style={{ border: '1px dashed #29412f', borderRadius: 10, padding: '1rem', color: '#8FAF9B', fontSize: '0.78rem' }}>
                No account-backed queue suggestions are available yet.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {scanSuggestions.map((suggestion) => {
                  const color = PLATFORM_COLORS[suggestion.platform] || '#6F8E7A'
                  const liveOpportunity = opportunities.find((item) => item.id === suggestion.opportunity_id)
                  return (
                    <div key={suggestion.opportunity_id} style={{ border: '1px solid #203028', borderRadius: 10, padding: '0.85rem', background: '#111917' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start', marginBottom: 8 }}>
                        <div>
                          <div style={{ color: '#dcead8', fontSize: '0.8rem', fontWeight: 700 }}>{suggestion.name}</div>
                          <div style={{ color: '#6F8E7A', fontSize: '0.7rem', marginTop: 3 }}>{suggestion.organization}</div>
                        </div>
                        <span style={badgeStyle(color)}>Score {suggestion.score}</span>
                      </div>
                      <div style={{ color: '#8FAF9B', fontSize: '0.74rem', marginBottom: 8 }}>
                        {suggestion.matching_accounts.join(', ') || 'Imported account coverage'}
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: 10 }}>
                        {suggestion.reasons.slice(0, 3).map((reason) => (
                          <div key={reason} style={{ color: '#8FAF9B', fontSize: '0.72rem', lineHeight: 1.4 }}>• {reason}</div>
                        ))}
                      </div>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <button onClick={() => void queueSuggestedOpportunity(suggestion)} style={gBtn('primary')}>
                          Queue Suggestion
                        </button>
                        {liveOpportunity && (
                          <button onClick={() => setPrepOpportunity(liveOpportunity)} style={gBtn('ghost')}>
                            Review Accounts
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          <div style={{ background: '#0f1413', border: '1px solid #29412f', borderRadius: 14, padding: '1rem' }}>
            <div style={{ color: '#dcead8', fontSize: '0.95rem', fontWeight: 700, marginBottom: 4 }}>Scan Queue Controls</div>
            <div style={{ color: '#6F8E7A', fontSize: '0.76rem', lineHeight: 1.5, marginBottom: 12 }}>
              Backend queue settings for how many scans can stay active in parallel for this user and tenant.
            </div>
            {settingsError && <div style={{ color: '#fca5a5', fontSize: '0.74rem', marginBottom: 10 }}>{settingsError}</div>}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10, marginBottom: 12 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, color: '#8FAF9B', fontSize: '0.74rem' }}>
                Min Parallel
                <input type='number' min={1} max={20} value={minConcurrent} onChange={(event) => setMinConcurrent(Number(event.target.value) || 1)} disabled={settingsLoading} style={{ background: '#111917', border: '1px solid #29412f', borderRadius: 8, color: '#dcead8', fontFamily: 'inherit', padding: '8px 10px' }} />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 6, color: '#8FAF9B', fontSize: '0.74rem' }}>
                Max Parallel
                <input type='number' min={1} max={20} value={maxConcurrent} onChange={(event) => setMaxConcurrent(Number(event.target.value) || 1)} disabled={settingsLoading} style={{ background: '#111917', border: '1px solid #29412f', borderRadius: 8, color: '#dcead8', fontFamily: 'inherit', padding: '8px 10px' }} />
              </label>
            </div>
            <button onClick={() => void saveSettings()} disabled={settingsLoading || settingsSaving} style={gBtn(settingsLoading || settingsSaving ? 'disabled' : 'primary')}>
              {settingsSaving ? 'Saving…' : 'Save Parallelism'}
            </button>
          </div>

          <div style={{ background: '#0f1413', border: '1px solid #29412f', borderRadius: 14, padding: '1rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'center', marginBottom: 10 }}>
              <div>
                <div style={{ color: '#dcead8', fontSize: '0.95rem', fontWeight: 700 }}>Queued Opportunities</div>
                <div style={{ color: '#6F8E7A', fontSize: '0.74rem', marginTop: 4 }}>{queueItems.length} items • {queuedCount} ready • {dispatchedCount} dispatched</div>
              </div>
              <button onClick={() => void launchAllQueued()} disabled={queuedCount === 0} style={gBtn(queuedCount === 0 ? 'disabled' : 'primary')}>
                Start Ready
              </button>
            </div>

            {queueItems.length === 0 ? (
              <div style={{ border: '1px dashed #29412f', borderRadius: 10, padding: '1rem', color: '#8FAF9B', fontSize: '0.78rem' }}>
                Add opportunities from the left column to build the scan queue.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {queueItems.map((item, index) => {
                  const platformColor = PLATFORM_COLORS[item.platform] || '#6F8E7A'
                  const running = Boolean(scanLoadingIds[item.id])
                  return (
                    <div key={item.id} style={{ border: '1px solid #203028', borderRadius: 10, padding: '0.85rem', background: '#111917' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start', marginBottom: 8 }}>
                        <div>
                          <div style={{ color: '#dcead8', fontSize: '0.8rem', fontWeight: 700 }}>{item.name}</div>
                          <div style={{ color: '#6F8E7A', fontSize: '0.7rem', marginTop: 3 }}>{item.organization}</div>
                        </div>
                        <span style={badgeStyle(platformColor)}>{PLATFORM_LABELS[item.platform] || item.platform}</span>
                      </div>
                      <div style={{ color: '#8FAF9B', fontSize: '0.75rem', marginBottom: 6 }}>Target: {item.subjectType} • {item.subjectKey}</div>
                      <div style={{ color: '#8FAF9B', fontSize: '0.74rem', marginBottom: 10 }}>Workflow: {item.recommendedWorkflow}</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
                        <span style={badgeStyle(item.status === 'error' ? '#f87171' : item.status === 'dispatched' ? '#8fd0ff' : item.status === 'dispatching' ? '#f59e0b' : '#b7d77a')}>
                          {item.status}
                        </span>
                        {item.needsCredentials && <span style={badgeStyle('#f59e0b')}>Account Prep Suggested</span>}
                      </div>
                      {item.lastError && <div style={{ color: '#fca5a5', fontSize: '0.72rem', marginBottom: 10 }}>{item.lastError}</div>}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                        <button onClick={() => void launchQueuedItem(item)} disabled={running} style={gBtn(running ? 'disabled' : 'primary')}>
                          {running ? 'Starting…' : 'Start'}
                        </button>
                        <button onClick={() => setPrepOpportunity({
                          id: item.opportunityId,
                          name: item.name,
                          organization: item.organization,
                          platform: item.platform,
                          access_type: item.accessType,
                          program_url: item.programUrl,
                          scope_url: '',
                          scope_summary: '',
                          scope_domains: [item.subjectKey],
                          max_payout_usd: 0,
                          min_payout_usd: 0,
                          vdp_only: false,
                          response_sla_days: 0,
                          tags: [],
                          vuln_types: [],
                          priority_score: 0,
                          is_public: item.accessType === 'public' || item.accessType === 'public_program',
                          payout_label: '',
                          notes: '',
                          credential_requirements: item.credentialRequirements,
                          queue_targets: [],
                          account_prep: item.accountPrep,
                          needs_credentials: item.needsCredentials,
                        })} style={gBtn('ghost')}>
                          Prep
                        </button>
                        <button onClick={() => setQueueItems((current) => current.filter(candidate => candidate.id !== item.id))} style={gBtn('danger')}>
                          Remove
                        </button>
                        {index > 0 && (
                          <button onClick={() => setQueueItems((current) => {
                            const next = [...current]
                            const swap = next[index - 1]
                            next[index - 1] = next[index]
                            next[index] = swap
                            return next
                          })} style={gBtn('ghost')}>
                            Move Up
                          </button>
                        )}
                        {index < queueItems.length - 1 && (
                          <button onClick={() => setQueueItems((current) => {
                            const next = [...current]
                            const swap = next[index + 1]
                            next[index + 1] = next[index]
                            next[index] = swap
                            return next
                          })} style={gBtn('ghost')}>
                            Move Down
                          </button>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </aside>
      </div>

      {guardAction && (
        <AccessConfirmModal
          action={guardAction}
          loading={false}
          onConfirm={() => void confirmGuardAction()}
          onCancel={() => setGuardAction(null)}
        />
      )}
      {prepOpportunity && <AccountPrepModal opportunity={prepOpportunity} onClose={() => setPrepOpportunity(null)} />}
    </div>
  )
}
