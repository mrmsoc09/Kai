/**
 * ScanPoolDashboard — real-time view of the rotating 75-125 opportunity scan pool.
 *
 * Displays:
 *   • Cycle progress bar (% of entries scanned in current cycle)
 *   • Active scans grid (up to 25, default 5-7)
 *   • Queued programs list with queue positions
 *   • Concurrency controls (min/max sliders)
 *   • Per-entry pause / manual-advance controls
 */
import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

const API_BASE = '/api/v1/scan-pool'

const C = {
  bg: '#0b0f14',
  card: '#0f141b',
  border: '#1e2a38',
  green: '#355E3B',
  greenBright: '#22c55e',
  orange: '#f97316',
  red: '#ef4444',
  text: '#c7d2e0',
  textMute: '#8a95a7',
  textDead: '#4b5563',
  mono: "'JetBrains Mono', 'Fira Code', monospace",
}

// ─── Types ──────────────────────────────────────────────────────────────────

interface Pool {
  id: string
  name: string
  status: 'active' | 'paused' | 'stopped'
  min_concurrent: number
  max_concurrent: number
  current_cycle: number
  cycle_started_at: string | null
  last_cycle_completed_at: string | null
  target_cycle_days: number | null
}

interface PoolEntry {
  id: string
  pool_id: string
  program_name: string
  platform: string | null
  program_handle: string | null
  queue_position: number
  status: 'waiting' | 'active' | 'paused' | 'error'
  total_scans_completed: number
  current_cycle_scanned: boolean
  last_activated_at: string | null
  last_completed_at: string | null
  last_scan_status: string | null
}

interface PoolStatus {
  pool: Pool
  total_entries: number
  active_count: number
  waiting_count: number
  paused_count: number
  error_count: number
  cycle_scanned_count: number
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function cyclePercent(status: PoolStatus): number {
  if (!status.total_entries) return 0
  return Math.round((status.cycle_scanned_count / status.total_entries) * 100)
}

// ─── Status dot ─────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: 'active' | 'paused' | 'stopped' | 'waiting' | 'error' }) {
  const color =
    status === 'active' ? C.greenBright :
    status === 'waiting' ? C.textMute :
    status === 'paused' ? C.orange :
    status === 'error' ? C.red :
    C.textDead
  const pulse = status === 'active'
  return (
    <span style={{
      display: 'inline-block',
      width: 8, height: 8,
      borderRadius: '50%',
      backgroundColor: color,
      boxShadow: pulse ? `0 0 6px ${color}` : 'none',
      flexShrink: 0,
    }} />
  )
}

// ─── Cycle progress bar ──────────────────────────────────────────────────────

function CycleBar({ pct, cycle }: { pct: number; cycle: number }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: C.textMute, marginBottom: 4 }}>
        <span>CYCLE {cycle} PROGRESS</span>
        <span style={{ color: pct >= 80 ? C.greenBright : C.text }}>{pct}%</span>
      </div>
      <div style={{ height: 6, background: '#1e2a38', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: pct >= 80 ? C.greenBright : pct >= 40 ? '#60a5fa' : C.orange,
          transition: 'width 0.6s ease',
          borderRadius: 3,
        }} />
      </div>
    </div>
  )
}

// ─── Entry card ─────────────────────────────────────────────────────────────

function EntryCard({
  entry,
  onPause,
  onResume,
}: {
  entry: PoolEntry
  onPause: (id: string) => void
  onResume: (id: string) => void
}) {
  const borderColor =
    entry.status === 'active' ? C.greenBright :
    entry.status === 'error' ? C.red :
    entry.status === 'paused' ? C.orange :
    C.border

  return (
    <div style={{
      padding: '0.6rem 0.75rem',
      background: C.card,
      border: `1px solid ${borderColor}`,
      borderRadius: 4,
      fontFamily: C.mono,
      fontSize: '0.72rem',
      display: 'flex',
      flexDirection: 'column',
      gap: 4,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <StatusDot status={entry.status} />
        <span style={{ color: C.text, fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {entry.program_name}
        </span>
        <span style={{ color: C.textDead, fontSize: '0.6rem' }}>#{entry.queue_position}</span>
      </div>
      <div style={{ display: 'flex', gap: 8, color: C.textMute, fontSize: '0.65rem' }}>
        {entry.platform && <span>{entry.platform}</span>}
        <span>scans: {entry.total_scans_completed}</span>
        {entry.last_scan_status && (
          <span style={{ color: entry.last_scan_status === 'completed' ? C.greenBright : C.red }}>
            last: {entry.last_scan_status}
          </span>
        )}
      </div>
      {entry.last_activated_at && (
        <div style={{ color: C.textDead, fontSize: '0.6rem' }}>activated {fmtDate(entry.last_activated_at)}</div>
      )}
      <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
        {entry.status === 'active' || entry.status === 'waiting' ? (
          <button onClick={() => onPause(entry.id)} style={btnStyle(C.orange)}>PAUSE</button>
        ) : entry.status === 'paused' ? (
          <button onClick={() => onResume(entry.id)} style={btnStyle(C.greenBright)}>RESUME</button>
        ) : null}
      </div>
    </div>
  )
}

function btnStyle(color: string): React.CSSProperties {
  return {
    background: 'none', border: `1px solid ${color}`, borderRadius: 3,
    color, fontSize: '0.6rem', cursor: 'pointer', padding: '1px 8px',
    fontFamily: C.mono,
  }
}

// ─── Concurrency controls ───────────────────────────────────────────────────

function ConcurrencyPanel({ pool, onSave }: { pool: Pool; onSave: (min: number, max: number) => void }) {
  const [minC, setMinC] = useState(pool.min_concurrent)
  const [maxC, setMaxC] = useState(pool.max_concurrent)
  const dirty = minC !== pool.min_concurrent || maxC !== pool.max_concurrent

  return (
    <div style={{ padding: '0.75rem', background: C.card, border: `1px solid ${C.border}`, borderRadius: 4, fontFamily: C.mono, fontSize: '0.72rem' }}>
      <div style={{ color: C.textMute, marginBottom: 8, fontSize: '0.65rem', letterSpacing: '0.08em' }}>CONCURRENCY</div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ color: C.textMute, minWidth: 28 }}>min</span>
        <input type="range" min={1} max={maxC} value={minC} onChange={e => setMinC(Number(e.target.value))} style={{ flex: 1 }} />
        <span style={{ color: C.text, minWidth: 16 }}>{minC}</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ color: C.textMute, minWidth: 28 }}>max</span>
        <input type="range" min={minC} max={25} value={maxC} onChange={e => setMaxC(Number(e.target.value))} style={{ flex: 1 }} />
        <span style={{ color: C.text, minWidth: 16 }}>{maxC}</span>
      </label>
      <button
        disabled={!dirty}
        onClick={() => onSave(minC, maxC)}
        style={{ ...btnStyle(dirty ? C.greenBright : C.textDead), opacity: dirty ? 1 : 0.4 }}
      >
        SAVE
      </button>
    </div>
  )
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function ScanPoolDashboard() {
  const [pools, setPools] = useState<Pool[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [status, setStatus] = useState<PoolStatus | null>(null)
  const [entries, setEntries] = useState<PoolEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  // Load pool list on mount
  useEffect(() => {
    api.get(`${API_BASE}/pools`)
      .then(r => {
        const list: Pool[] = r.data.pools ?? []
        setPools(list)
        if (list.length > 0) setSelectedPoolId(list[0].id)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Poll selected pool status + entries every 5s
  const refreshPool = useCallback(() => {
    if (!selectedPoolId) return
    api.get(`${API_BASE}/${selectedPoolId}/status`)
      .then(r => setStatus(r.data))
      .catch(() => {})
    api.get(`${API_BASE}/${selectedPoolId}/entries`)
      .then(r => setEntries(r.data.entries ?? []))
      .catch(() => {})
  }, [selectedPoolId])

  useEffect(() => {
    refreshPool()
    const iv = setInterval(refreshPool, 5_000)
    return () => clearInterval(iv)
  }, [refreshPool])

  const flash = (msg: string) => {
    setActionMsg(msg)
    setTimeout(() => setActionMsg(null), 3000)
  }

  const setPoolLifecycle = async (action: 'pause' | 'resume' | 'stop') => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/${action}`, {})
      flash(`Pool ${action}d.`)
      refreshPool()
    } catch (e: any) { flash(`Error: ${e.message}`) }
  }

  const pauseEntry = async (entryId: string) => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/entries/${entryId}/pause`, {})
      flash('Entry paused.')
      refreshPool()
    } catch (e: any) { flash(`Error: ${e.message}`) }
  }

  const resumeEntry = async (entryId: string) => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/entries/${entryId}/resume`, {})
      flash('Entry resumed.')
      refreshPool()
    } catch (e: any) { flash(`Error: ${e.message}`) }
  }

  const saveConcurrency = async (min: number, max: number) => {
    if (!selectedPoolId) return
    try {
      await api.put(`${API_BASE}/${selectedPoolId}/concurrency`, { min_concurrent: min, max_concurrent: max })
      flash('Concurrency updated.')
      refreshPool()
    } catch (e: any) { flash(`Error: ${e.message}`) }
  }

  const manualAdvance = async () => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/advance`, {})
      flash('Queue advanced.')
      refreshPool()
    } catch (e: any) { flash(`Error: ${e.message}`) }
  }

  if (loading) return (
    <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: C.mono, fontSize: '0.75rem' }}>
      ▓▒░ LOADING SCAN POOL…
    </div>
  )

  if (error) return (
    <div style={{ padding: '2rem', color: C.red, fontFamily: C.mono, fontSize: '0.75rem' }}>
      Error loading pools: {error}
    </div>
  )

  if (pools.length === 0) return (
    <div style={{ padding: '2rem', color: C.textMute, fontFamily: C.mono, fontSize: '0.75rem', textAlign: 'center' }}>
      <div style={{ fontSize: '2rem', marginBottom: 8 }}>◯</div>
      No scan pools configured yet.
      <div style={{ marginTop: 8, fontSize: '0.65rem' }}>
        Create a pool via the API: <code>POST /api/v1/scan-pool/pools</code>
      </div>
    </div>
  )

  const pool = pools.find(p => p.id === selectedPoolId)
  const pct = status ? cyclePercent(status) : 0
  const activeEntries = entries.filter(e => e.status === 'active')
  const waitingEntries = entries.filter(e => e.status === 'waiting')
  const pausedEntries = entries.filter(e => e.status === 'paused')
  const errorEntries = entries.filter(e => e.status === 'error')

  return (
    <div style={{ background: C.bg, minHeight: '100vh', fontFamily: C.mono, color: C.text }}>
      {/* Header */}
      <div style={{ padding: '1rem 1.5rem', background: C.card, borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ color: C.green, fontSize: '1.2rem' }}>⟳</span>
          <h1 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, letterSpacing: '0.05em' }}>SCAN POOL OPERATIONS</h1>
          {pool && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.65rem' }}>
              <StatusDot status={pool.status} />
              <span style={{ color: C.textMute }}>{pool.status.toUpperCase()}</span>
            </span>
          )}
        </div>
        {actionMsg && <span style={{ fontSize: '0.7rem', color: C.greenBright }}>{actionMsg}</span>}
        <div style={{ display: 'flex', gap: 8 }}>
          {pool?.status === 'active' && (
            <button onClick={() => setPoolLifecycle('pause')} style={btnStyle(C.orange)}>PAUSE POOL</button>
          )}
          {(pool?.status === 'paused' || pool?.status === 'stopped') && (
            <button onClick={() => setPoolLifecycle('resume')} style={btnStyle(C.greenBright)}>RESUME POOL</button>
          )}
          {pool?.status === 'active' && (
            <button onClick={manualAdvance} style={btnStyle('#60a5fa')}>▶ ADVANCE</button>
          )}
        </div>
      </div>

      {/* Pool selector (if multiple pools) */}
      {pools.length > 1 && (
        <div style={{ padding: '0.5rem 1.5rem', borderBottom: `1px solid ${C.border}`, display: 'flex', gap: 8 }}>
          {pools.map(p => (
            <button key={p.id} onClick={() => setSelectedPoolId(p.id)} style={{
              ...btnStyle(p.id === selectedPoolId ? C.greenBright : C.textMute),
              fontWeight: p.id === selectedPoolId ? 700 : 400,
            }}>{p.name}</button>
          ))}
        </div>
      )}

      <div style={{ padding: '1rem 1.5rem', display: 'grid', gridTemplateColumns: '1fr 280px', gap: '1rem' }}>
        {/* Left: Cycle + Active + Queue */}
        <div>
          {/* Cycle progress */}
          {status && pool && (
            <>
              <CycleBar pct={pct} cycle={pool.current_cycle} />
              <div style={{ display: 'flex', gap: 16, marginBottom: '1rem', fontSize: '0.65rem', color: C.textMute }}>
                <span>Total: <strong style={{ color: C.text }}>{status.total_entries}</strong></span>
                <span>Active: <strong style={{ color: C.greenBright }}>{status.active_count}</strong></span>
                <span>Waiting: <strong style={{ color: C.text }}>{status.waiting_count}</strong></span>
                {status.paused_count > 0 && <span>Paused: <strong style={{ color: C.orange }}>{status.paused_count}</strong></span>}
                {status.error_count > 0 && <span>Errors: <strong style={{ color: C.red }}>{status.error_count}</strong></span>}
                {pool.cycle_started_at && (
                  <span>Cycle started: <strong style={{ color: C.text }}>{fmtDate(pool.cycle_started_at)}</strong></span>
                )}
              </div>
            </>
          )}

          {/* Active scans */}
          {activeEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                ACTIVE SCANS ({activeEntries.length}/{pool?.max_concurrent ?? '?'} max)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {activeEntries.map(e => (
                  <EntryCard key={e.id} entry={e} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {/* Error entries */}
          {errorEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.red, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                ERRORS ({errorEntries.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {errorEntries.map(e => (
                  <EntryCard key={e.id} entry={e} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {/* Paused entries */}
          {pausedEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.orange, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                PAUSED ({pausedEntries.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {pausedEntries.map(e => (
                  <EntryCard key={e.id} entry={e} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {/* Waiting queue */}
          {waitingEntries.length > 0 && (
            <section>
              <div style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                QUEUE ({waitingEntries.length} waiting)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {waitingEntries.map(e => (
                  <div key={e.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '0.4rem 0.6rem', background: C.card,
                    border: `1px solid ${C.border}`, borderRadius: 3, fontSize: '0.68rem',
                  }}>
                    <span style={{ color: C.textDead, minWidth: 28 }}>#{e.queue_position}</span>
                    <span style={{ color: C.text, flex: 1 }}>{e.program_name}</span>
                    {e.platform && <span style={{ color: C.textMute, fontSize: '0.6rem' }}>{e.platform}</span>}
                    <span style={{ color: C.textDead, fontSize: '0.6rem' }}>×{e.total_scans_completed}</span>
                    <button onClick={() => pauseEntry(e.id)} style={btnStyle(C.textDead)}>pause</button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right: Controls */}
        {pool && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <ConcurrencyPanel pool={pool} onSave={saveConcurrency} />

            <div style={{ padding: '0.75rem', background: C.card, border: `1px solid ${C.border}`, borderRadius: 4, fontSize: '0.68rem' }}>
              <div style={{ color: C.textMute, marginBottom: 8, fontSize: '0.65rem', letterSpacing: '0.08em' }}>CYCLE INFO</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, color: C.textMute }}>
                <div>Cycle <strong style={{ color: C.text }}>#{pool.current_cycle}</strong></div>
                {pool.target_cycle_days && (
                  <div>Target <strong style={{ color: C.text }}>{pool.target_cycle_days}d</strong></div>
                )}
                {pool.last_cycle_completed_at && (
                  <div>Last complete <strong style={{ color: C.text }}>{fmtDate(pool.last_cycle_completed_at)}</strong></div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
