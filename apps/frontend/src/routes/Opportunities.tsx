import React, { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listOpportunities, createWorkflow } from '../lib/api'

// ─── Types ───────────────────────────────────────────────────────────────────

interface Opportunity {
  id: string
  name: string
  organization: string
  platform: string
  access_type: string
  program_url: string
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
}

// ─── Invite-Only Modal ────────────────────────────────────────────────────────

function InviteModal({
  opp, onConfirm, onCancel, loading,
}: {
  opp: Opportunity; onConfirm: () => void; onCancel: () => void; loading: boolean
}) {
  const [checked, setChecked] = useState(false)
  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }}>
      <div style={{
        background: '#0d1117', border: '1px solid #2d3748', borderRadius: 8,
        padding: '2rem', maxWidth: 480, width: '90%',
      }}>
        <div style={{ color: '#f59e0b', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.1em', marginBottom: 8 }}>
          INVITE-ONLY PROGRAM
        </div>
        <div style={{ color: '#e2e8f0', fontWeight: 700, marginBottom: 8 }}>{opp.name}</div>
        <p style={{ color: '#8892a4', fontSize: '0.82rem', lineHeight: 1.55, margin: '0 0 16px' }}>
          This is a private/invite-only program. You must have received a valid invitation
          from the program owner before any testing activity.
        </p>
        <label style={{ display: 'flex', gap: 10, alignItems: 'flex-start', cursor: 'pointer', marginBottom: 20 }}>
          <input type='checkbox' checked={checked} onChange={e => setChecked(e.target.checked)} style={{ marginTop: 3 }} />
          <span style={{ color: '#8892a4', fontSize: '0.78rem', lineHeight: 1.45 }}>
            I confirm I have received a valid invitation and that unauthorized testing
            is prohibited. I accept full legal responsibility for my actions.
          </span>
        </label>
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
          <button onClick={onCancel} style={gBtn('ghost')}>Cancel</button>
          <button
            onClick={onConfirm}
            disabled={!checked || loading}
            style={gBtn(checked && !loading ? 'primary' : 'disabled')}
          >
            {loading ? 'Creating…' : 'Confirm & Start Hunt'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ─── Shared helpers ───────────────────────────────────────────────────────────

function gBtn(v: 'primary' | 'ghost' | 'disabled'): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, fontFamily: 'inherit',
    fontSize: '0.75rem', fontWeight: 600, letterSpacing: '0.06em',
    cursor: v === 'disabled' ? 'not-allowed' : 'pointer', border: 'none',
  }
  if (v === 'primary') return { ...base, background: '#00FF41', color: '#0d1117' }
  if (v === 'ghost') return { ...base, background: 'transparent', border: '1px solid #2d3748', color: '#8892a4' }
  return { ...base, background: '#1e2330', color: '#4a5568' }
}

const PLATFORM_COLORS: Record<string, string> = {
  hackerone: '#25a244', bugcrowd: '#f97316', intigriti: '#7c3aed',
  vrp: '#2563eb', government_cvd: '#0891b2',
}
const PLATFORM_LABELS: Record<string, string> = {
  hackerone: 'HackerOne', bugcrowd: 'Bugcrowd', intigriti: 'Intigriti',
  vrp: 'VRP', government_cvd: 'Gov CVD',
}

// ─── Opportunity Card ─────────────────────────────────────────────────────────

function OppCard({ opp, onStart, loading }: {
  opp: Opportunity; onStart: (o: Opportunity) => void; loading: boolean
}) {
  const pc = PLATFORM_COLORS[opp.platform] || '#4a5568'
  return (
    <div style={{
      background: '#0d1117', border: '1px solid #1e2330', borderRadius: 8,
      padding: '1rem 1.1rem', display: 'flex', flexDirection: 'column', gap: 10,
      transition: 'border-color 0.15s',
    }}
      onMouseEnter={e => (e.currentTarget.style.borderColor = '#2d3748')}
      onMouseLeave={e => (e.currentTarget.style.borderColor = '#1e2330')}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div>
          <div style={{ color: '#e2e8f0', fontWeight: 600, fontSize: '0.88rem', lineHeight: 1.3 }}>{opp.name}</div>
          <div style={{ color: '#4a5568', fontSize: '0.7rem', marginTop: 2 }}>{opp.organization}</div>
        </div>
        <div style={{ display: 'flex', gap: 5, flexShrink: 0, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          {opp.is_public && (
            <span style={{
              background: 'rgba(0,255,65,0.1)', color: '#00FF41',
              border: '1px solid rgba(0,255,65,0.25)',
              fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: 3, letterSpacing: '0.08em',
            }}>PUBLIC</span>
          )}
          <span style={{
            background: `${pc}1a`, color: pc,
            border: `1px solid ${pc}44`,
            fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: 3,
          }}>{PLATFORM_LABELS[opp.platform] || opp.platform}</span>
        </div>
      </div>

      {/* Scope preview */}
      <div style={{ color: '#4a8fa8', fontSize: '0.72rem', lineHeight: 1.4 }}>
        {opp.scope_domains.slice(0, 2).join(', ')}
        {opp.scope_domains.length > 2 && (
          <span style={{ color: '#2d3748' }}> +{opp.scope_domains.length - 2} more</span>
        )}
        {opp.scope_domains.length === 0 && <span style={{ color: '#2d3748' }}>See program scope page</span>}
      </div>

      {/* Payout */}
      <div style={{ color: opp.vdp_only ? '#4a5568' : '#00FF41', fontSize: '0.8rem', fontWeight: 600 }}>
        {opp.payout_label}
      </div>

      {/* Tags */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
        {opp.tags.slice(0, 5).map(t => (
          <span key={t} style={{
            background: '#1e2330', color: '#4a5568', fontSize: '0.62rem',
            padding: '2px 6px', borderRadius: 3,
          }}>{t}</span>
        ))}
      </div>

      {/* Priority bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div style={{ flex: 1, height: 3, background: '#1e2330', borderRadius: 2 }}>
          <div style={{
            width: `${Math.round(opp.priority_score * 100)}%`,
            height: '100%', background: '#00FF41', borderRadius: 2,
          }} />
        </div>
        <span style={{ color: '#4a5568', fontSize: '0.62rem', minWidth: 24, textAlign: 'right' }}>
          {Math.round(opp.priority_score * 100)}
        </span>
      </div>

      {/* CTA */}
      <button
        onClick={() => onStart(opp)}
        disabled={loading}
        style={{ ...gBtn(loading ? 'disabled' : 'primary'), width: '100%', textAlign: 'center' }}
      >
        {loading ? 'Starting…' : opp.is_public ? 'START HUNT' : 'REQUEST ACCESS'}
      </button>
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────

const PAGE_SIZE = 24
const PLATFORMS = ['', 'hackerone', 'bugcrowd', 'intigriti', 'vrp', 'government_cvd']
type SortKey = 'score' | 'payout' | 'name'

export default function Opportunities() {
  const navigate = useNavigate()

  const [opps, setOpps] = useState<Opportunity[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [platform, setPlatform] = useState('')
  const [publicOnly, setPublicOnly] = useState(false)
  const [sort, setSort] = useState<SortKey>('score')
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(0)

  // Actions
  const [inviteOpp, setInviteOpp] = useState<Opportunity | null>(null)
  const [startingId, setStartingId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const r = await listOpportunities({
        platform: platform || undefined,
        public_only: publicOnly || undefined,
        search: search || undefined,
        sort_by: sort,
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
      })
      setOpps(r.data.opportunities)
      setTotal(r.data.total)
    } catch {
      setError('Failed to load opportunities — is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [platform, publicOnly, search, sort, page])

  useEffect(() => { load() }, [load])

  // Debounce search; reset page when filter changes
  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(0) }, 350)
    return () => clearTimeout(t)
  }, [searchInput])

  useEffect(() => { setPage(0) }, [platform, publicOnly, sort])

  const handleStart = useCallback((opp: Opportunity) => {
    if (!opp.is_public) { setInviteOpp(opp); return }
    doCreate(opp)
  }, [])

  const doCreate = async (opp: Opportunity) => {
    setStartingId(opp.id)
    setInviteOpp(null)
    try {
      await createWorkflow(opp.id)
      navigate('/workflows')
    } catch (e: any) {
      // 409 = active workflow already exists — navigate directly to it
      if (e?.response?.status === 409) {
        navigate('/workflows')
        return
      }
      const msg = e?.response?.data?.detail
      setError(
        typeof msg === 'string'
          ? msg
          : `Failed to start hunt for ${opp.name}. Requires OPERATOR or ADMIN role.`
      )
    } finally {
      setStartingId(null)
    }
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div style={{ padding: '1.5rem 2rem', maxWidth: 1400 }}>
      {/* Page header */}
      <div style={{ marginBottom: '1.2rem' }}>
        <h1 style={{ color: '#e2e8f0', margin: 0, fontSize: '1.4rem', fontWeight: 700, letterSpacing: '-0.02em' }}>
          Opportunity Hub
        </h1>
        <p style={{ color: '#4a5568', margin: '4px 0 0', fontSize: '0.78rem' }}>
          Public programs require zero additional authorization — the program listing IS the permission.
        </p>
      </div>

      {/* Filter & sort bar */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: '1.2rem', alignItems: 'center' }}>
        {/* Search */}
        <input
          type='text'
          placeholder='Search programs, orgs, domains…'
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          style={{
            background: '#0d1117', border: '1px solid #1e2330', borderRadius: 4,
            color: '#e2e8f0', fontFamily: 'inherit', fontSize: '0.78rem',
            padding: '6px 10px', width: 240, outline: 'none',
          }}
        />

        {/* Platform filter */}
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {PLATFORMS.map(p => (
            <button
              key={p}
              onClick={() => setPlatform(p)}
              style={{
                ...gBtn(platform === p ? 'primary' : 'ghost'),
                padding: '5px 10px', fontSize: '0.7rem',
              }}
            >
              {PLATFORM_LABELS[p] || 'All'}
            </button>
          ))}
        </div>

        {/* Sort */}
        <select
          value={sort}
          onChange={e => setSort(e.target.value as SortKey)}
          style={{
            background: '#0d1117', border: '1px solid #1e2330', borderRadius: 4,
            color: '#8892a4', fontFamily: 'inherit', fontSize: '0.72rem', padding: '5px 8px',
          }}
        >
          <option value='score'>Sort: Score</option>
          <option value='payout'>Sort: Payout</option>
          <option value='name'>Sort: Name</option>
        </select>

        {/* Public-only toggle */}
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
          <input type='checkbox' checked={publicOnly} onChange={e => setPublicOnly(e.target.checked)} />
          <span style={{ color: '#8892a4', fontSize: '0.75rem' }}>Public only</span>
        </label>

        {/* Result count */}
        {!loading && (
          <span style={{ color: '#4a5568', fontSize: '0.72rem', marginLeft: 'auto' }}>
            {total} program{total !== 1 ? 's' : ''}
            {totalPages > 1 && ` · page ${page + 1} / ${totalPages}`}
          </span>
        )}
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

      {/* Grid */}
      {loading ? (
        <div style={{ color: '#4a5568', padding: '4rem', textAlign: 'center', fontSize: '0.85rem' }}>Loading…</div>
      ) : opps.length === 0 ? (
        <div style={{
          border: '1px dashed #1e2330', borderRadius: 8,
          padding: '4rem', textAlign: 'center',
        }}>
          <div style={{ color: '#4a5568', marginBottom: 8 }}>No programs match your filters.</div>
          <button onClick={() => { setPlatform(''); setPublicOnly(false); setSearchInput('') }} style={gBtn('ghost')}>
            Clear filters
          </button>
        </div>
      ) : (
        <>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(290px, 1fr))',
            gap: '0.9rem',
          }}>
            {opps.map(o => (
              <OppCard key={o.id} opp={o} onStart={handleStart} loading={startingId === o.id} />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div style={{ display: 'flex', gap: 6, justifyContent: 'center', marginTop: '1.5rem' }}>
              <button
                onClick={() => setPage(p => Math.max(0, p - 1))}
                disabled={page === 0}
                style={gBtn(page === 0 ? 'disabled' : 'ghost')}
              >
                ← Prev
              </button>
              <span style={{ color: '#4a5568', fontSize: '0.78rem', padding: '6px 8px' }}>
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                style={gBtn(page >= totalPages - 1 ? 'disabled' : 'ghost')}
              >
                Next →
              </button>
            </div>
          )}
        </>
      )}

      {/* Invite-only modal */}
      {inviteOpp && (
        <InviteModal
          opp={inviteOpp}
          loading={startingId === inviteOpp.id}
          onConfirm={() => doCreate(inviteOpp)}
          onCancel={() => setInviteOpp(null)}
        />
      )}
    </div>
  )
}
