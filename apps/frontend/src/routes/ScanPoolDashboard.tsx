import React, { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'

const API_BASE = '/api/v1/scan-pool'

const C = {
  bg: '#0b0f14',
  card: '#0f141b',
  border: '#1e2a38',
  green: '#355E3B',
  greenBright: '#22c55e',
  blue: '#60a5fa',
  orange: '#f97316',
  red: '#ef4444',
  text: '#c7d2e0',
  textMute: '#8a95a7',
  textDead: '#4b5563',
  mono: "'JetBrains Mono', 'Fira Code', monospace",
}

type PoolSummary = {
  id: string
  name: string
  description: string | null
  user_id: string | null
  status: 'active' | 'paused' | 'stopped'
  min_concurrent: number
  max_concurrent: number
  current_cycle: number
  cycle_started_at: string | null
  last_cycle_completed_at: string | null
  target_cycle_days: number | null
  created_at: string | null
  updated_at: string | null
}

type PoolEntry = {
  id: string
  queue_position: number
  program_name: string
  platform: string | null
  program_handle: string | null
  status: 'waiting' | 'active' | 'paused' | 'error'
  total_scans_completed: number
  current_cycle_scanned: boolean
  last_activated_at: string | null
  last_completed_at: string | null
  last_scan_status: string | null
  last_celery_task_id: string | null
}

type PoolStatus = {
  pool_id: string
  name: string
  status: 'active' | 'paused' | 'stopped'
  min_concurrent: number
  max_concurrent: number
  current_cycle: number
  cycle_started_at: string | null
  last_cycle_completed_at: string | null
  target_cycle_days: number | null
  total_entries: number
  status_counts: Record<string, number>
  entries: PoolEntry[]
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function btnStyle(color: string): React.CSSProperties {
  return {
    background: 'none',
    border: `1px solid ${color}`,
    borderRadius: 4,
    color,
    fontSize: '0.65rem',
    cursor: 'pointer',
    padding: '3px 8px',
    fontFamily: C.mono,
  }
}

function StatusDot({ status }: { status: 'active' | 'paused' | 'stopped' | 'waiting' | 'error' }) {
  const color =
    status === 'active'
      ? C.greenBright
      : status === 'waiting'
        ? C.textMute
        : status === 'paused'
          ? C.orange
          : status === 'error'
            ? C.red
            : C.textDead
  return (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        boxShadow: status === 'active' ? `0 0 6px ${color}` : 'none',
        flexShrink: 0,
      }}
    />
  )
}

function CycleBar({ pct, cycle }: { pct: number; cycle: number }) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: C.textMute, marginBottom: 4 }}>
        <span>CYCLE {cycle} PROGRESS</span>
        <span style={{ color: pct >= 80 ? C.greenBright : C.text }}>{pct}%</span>
      </div>
      <div style={{ height: 6, background: C.border, borderRadius: 3, overflow: 'hidden' }}>
        <div
          style={{
            height: '100%',
            width: `${pct}%`,
            background: pct >= 80 ? C.greenBright : pct >= 40 ? C.blue : C.orange,
            transition: 'width 0.6s ease',
          }}
        />
      </div>
    </div>
  )
}

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
    entry.status === 'active'
      ? C.greenBright
      : entry.status === 'paused'
        ? C.orange
        : entry.status === 'error'
          ? C.red
          : C.border

  return (
    <div
      style={{
        padding: '0.7rem 0.8rem',
        background: C.card,
        border: `1px solid ${borderColor}`,
        borderRadius: 6,
        fontFamily: C.mono,
        fontSize: '0.72rem',
        display: 'flex',
        flexDirection: 'column',
        gap: 5,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <StatusDot status={entry.status} />
        <span style={{ color: C.text, fontWeight: 700, flex: 1 }}>{entry.program_name}</span>
        <span style={{ color: C.textDead, fontSize: '0.62rem' }}>#{entry.queue_position}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, color: C.textMute, fontSize: '0.64rem' }}>
        {entry.platform && <span>{entry.platform}</span>}
        <span>scans: {entry.total_scans_completed}</span>
        {entry.last_scan_status && (
          <span style={{ color: entry.last_scan_status === 'completed' ? C.greenBright : C.red }}>
            last: {entry.last_scan_status}
          </span>
        )}
      </div>
      <div style={{ color: C.textDead, fontSize: '0.6rem' }}>
        activated {fmtDate(entry.last_activated_at)} • completed {fmtDate(entry.last_completed_at)}
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 2 }}>
        {(entry.status === 'active' || entry.status === 'waiting') && (
          <button onClick={() => onPause(entry.id)} style={btnStyle(C.orange)}>PAUSE</button>
        )}
        {entry.status === 'paused' && (
          <button onClick={() => onResume(entry.id)} style={btnStyle(C.greenBright)}>RESUME</button>
        )}
      </div>
    </div>
  )
}

function ConcurrencyPanel({
  minConcurrent,
  maxConcurrent,
  onSave,
}: {
  minConcurrent: number
  maxConcurrent: number
  onSave: (min: number, max: number) => void
}) {
  const [minC, setMinC] = useState(minConcurrent)
  const [maxC, setMaxC] = useState(maxConcurrent)

  useEffect(() => {
    setMinC(minConcurrent)
    setMaxC(maxConcurrent)
  }, [maxConcurrent, minConcurrent])

  const dirty = minC !== minConcurrent || maxC !== maxConcurrent

  return (
    <div style={{ padding: '0.85rem', background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, fontFamily: C.mono, fontSize: '0.72rem' }}>
      <div style={{ color: C.textMute, marginBottom: 8, fontSize: '0.65rem', letterSpacing: '0.08em' }}>CONCURRENCY</div>
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
        <span style={{ color: C.textMute, minWidth: 28 }}>min</span>
        <input type='range' min={1} max={maxC} value={minC} onChange={e => setMinC(Number(e.target.value))} style={{ flex: 1 }} />
        <span style={{ color: C.text, minWidth: 16 }}>{minC}</span>
      </label>
      <label style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ color: C.textMute, minWidth: 28 }}>max</span>
        <input type='range' min={minC} max={25} value={maxC} onChange={e => setMaxC(Number(e.target.value))} style={{ flex: 1 }} />
        <span style={{ color: C.text, minWidth: 16 }}>{maxC}</span>
      </label>
      <button disabled={!dirty} onClick={() => onSave(minC, maxC)} style={{ ...btnStyle(dirty ? C.greenBright : C.textDead), opacity: dirty ? 1 : 0.45 }}>
        SAVE
      </button>
    </div>
  )
}

export default function ScanPoolDashboard() {
  const [pools, setPools] = useState<PoolSummary[]>([])
  const [selectedPoolId, setSelectedPoolId] = useState<string | null>(null)
  const [status, setStatus] = useState<PoolStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const flash = useCallback((message: string) => {
    setActionMsg(message)
    window.setTimeout(() => setActionMsg(null), 3000)
  }, [])

  const loadPools = useCallback(async () => {
    try {
      const response = await api.get(API_BASE)
      const list: PoolSummary[] = Array.isArray(response.data) ? response.data : []
      setPools(list)
      setSelectedPoolId(current => current ?? list[0]?.id ?? null)
      setError(null)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err?.message || 'Failed to load scan pools.')
    } finally {
      setLoading(false)
    }
  }, [])

  const refreshPool = useCallback(async () => {
    if (!selectedPoolId) return
    try {
      const response = await api.get(`${API_BASE}/${selectedPoolId}`)
      setStatus(response.data)
      setError(null)
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err?.message || 'Failed to load pool status.')
    }
  }, [selectedPoolId])

  useEffect(() => {
    void loadPools()
  }, [loadPools])

  useEffect(() => {
    if (!selectedPoolId) return
    void refreshPool()
    const timer = window.setInterval(() => {
      void refreshPool()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [refreshPool, selectedPoolId])

  const setPoolLifecycle = async (action: 'pause' | 'resume' | 'stop') => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/${action}`, {})
      flash(`Pool ${action}d.`)
      await loadPools()
      await refreshPool()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      flash(`Error: ${typeof detail === 'string' ? detail : err?.message || 'request failed'}`)
    }
  }

  const pauseEntry = async (entryId: string) => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/entries/${entryId}/pause`, {})
      flash('Entry paused.')
      await refreshPool()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      flash(`Error: ${typeof detail === 'string' ? detail : err?.message || 'request failed'}`)
    }
  }

  const resumeEntry = async (entryId: string) => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/entries/${entryId}/resume`, {})
      flash('Entry resumed.')
      await refreshPool()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      flash(`Error: ${typeof detail === 'string' ? detail : err?.message || 'request failed'}`)
    }
  }

  const saveConcurrency = async (min: number, max: number) => {
    if (!selectedPoolId) return
    try {
      await api.put(`${API_BASE}/${selectedPoolId}/settings`, {
        min_concurrent: min,
        max_concurrent: max,
      })
      flash('Concurrency updated.')
      await loadPools()
      await refreshPool()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      flash(`Error: ${typeof detail === 'string' ? detail : err?.message || 'request failed'}`)
    }
  }

  const manualAdvance = async () => {
    if (!selectedPoolId) return
    try {
      await api.post(`${API_BASE}/${selectedPoolId}/advance`, {})
      flash('Queue advanced.')
      await refreshPool()
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      flash(`Error: ${typeof detail === 'string' ? detail : err?.message || 'request failed'}`)
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: C.mono, fontSize: '0.75rem' }}>
        ▓▒░ LOADING SCAN POOL…
      </div>
    )
  }

  if (error && pools.length === 0) {
    return (
      <div style={{ padding: '2rem', color: C.red, fontFamily: C.mono, fontSize: '0.75rem' }}>
        Error loading pools: {error}
      </div>
    )
  }

  if (pools.length === 0) {
    return (
      <div style={{ padding: '2rem', color: C.textMute, fontFamily: C.mono, fontSize: '0.75rem', textAlign: 'center' }}>
        <div style={{ fontSize: '2rem', marginBottom: 8 }}>◯</div>
        No scan pools configured yet.
        <div style={{ marginTop: 8, fontSize: '0.65rem' }}>
          Create a pool via the API: <code>POST /api/v1/scan-pool</code>
        </div>
      </div>
    )
  }

  const selectedPool = status ?? pools.find(pool => pool.id === selectedPoolId) ?? null
  const entries = status?.entries ?? []
  const totalEntries = status?.total_entries ?? entries.length
  const activeEntries = entries.filter(entry => entry.status === 'active')
  const waitingEntries = entries.filter(entry => entry.status === 'waiting')
  const pausedEntries = entries.filter(entry => entry.status === 'paused')
  const errorEntries = entries.filter(entry => entry.status === 'error')
  const cycleScannedCount = entries.filter(entry => entry.current_cycle_scanned).length
  const cyclePct = totalEntries > 0 ? Math.round((cycleScannedCount / totalEntries) * 100) : 0
  const activeCount = status?.status_counts?.active ?? activeEntries.length
  const waitingCount = status?.status_counts?.waiting ?? waitingEntries.length
  const pausedCount = status?.status_counts?.paused ?? pausedEntries.length
  const errorCount = status?.status_counts?.error ?? errorEntries.length

  return (
    <div style={{ background: C.bg, minHeight: '100vh', fontFamily: C.mono, color: C.text }}>
      <div style={{ padding: '1rem 1.5rem', background: C.card, borderBottom: `1px solid ${C.border}`, display: 'flex', alignItems: 'center', gap: 12, justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
          <span style={{ color: C.green, fontSize: '1.2rem' }}>⟳</span>
          <h1 style={{ margin: 0, fontSize: '1rem', fontWeight: 700, letterSpacing: '0.05em' }}>SCAN POOL OPERATIONS</h1>
          {selectedPool && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.65rem' }}>
              <StatusDot status={selectedPool.status} />
              <span style={{ color: C.textMute }}>{selectedPool.status.toUpperCase()}</span>
            </span>
          )}
        </div>
        {actionMsg && <span style={{ fontSize: '0.7rem', color: C.greenBright }}>{actionMsg}</span>}
        <div style={{ display: 'flex', gap: 8 }}>
          {selectedPool?.status === 'active' && (
            <button onClick={() => void setPoolLifecycle('pause')} style={btnStyle(C.orange)}>PAUSE POOL</button>
          )}
          {(selectedPool?.status === 'paused' || selectedPool?.status === 'stopped') && (
            <button onClick={() => void setPoolLifecycle('resume')} style={btnStyle(C.greenBright)}>RESUME POOL</button>
          )}
          {selectedPool?.status === 'active' && (
            <button onClick={() => void manualAdvance()} style={btnStyle(C.blue)}>ADVANCE</button>
          )}
          {selectedPool?.status !== 'stopped' && (
            <button onClick={() => void setPoolLifecycle('stop')} style={btnStyle(C.red)}>STOP</button>
          )}
        </div>
      </div>

      {pools.length > 1 && (
        <div style={{ padding: '0.5rem 1.5rem', borderBottom: `1px solid ${C.border}`, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {pools.map(pool => (
            <button
              key={pool.id}
              onClick={() => setSelectedPoolId(pool.id)}
              style={{
                ...btnStyle(pool.id === selectedPoolId ? C.greenBright : C.textMute),
                fontWeight: pool.id === selectedPoolId ? 700 : 400,
              }}
            >
              {pool.name}
            </button>
          ))}
        </div>
      )}

      <div style={{ padding: '1rem 1.5rem', display: 'grid', gridTemplateColumns: '1fr 280px', gap: '1rem' }}>
        <div>
          {selectedPool && (
            <>
              <CycleBar pct={cyclePct} cycle={selectedPool.current_cycle} />
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: '1rem', fontSize: '0.65rem', color: C.textMute }}>
                <span>Total: <strong style={{ color: C.text }}>{totalEntries}</strong></span>
                <span>Active: <strong style={{ color: C.greenBright }}>{activeCount}</strong></span>
                <span>Waiting: <strong style={{ color: C.text }}>{waitingCount}</strong></span>
                {pausedCount > 0 && <span>Paused: <strong style={{ color: C.orange }}>{pausedCount}</strong></span>}
                {errorCount > 0 && <span>Errors: <strong style={{ color: C.red }}>{errorCount}</strong></span>}
                {selectedPool.cycle_started_at && (
                  <span>Cycle started: <strong style={{ color: C.text }}>{fmtDate(selectedPool.cycle_started_at)}</strong></span>
                )}
              </div>
            </>
          )}

          {activeEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                ACTIVE SCANS ({activeEntries.length}/{selectedPool?.max_concurrent ?? '?'} max)
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {activeEntries.map(entry => (
                  <EntryCard key={entry.id} entry={entry} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {pausedEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.orange, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                PAUSED ({pausedEntries.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {pausedEntries.map(entry => (
                  <EntryCard key={entry.id} entry={entry} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {errorEntries.length > 0 && (
            <section style={{ marginBottom: '1.25rem' }}>
              <div style={{ color: C.red, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                ERRORS ({errorEntries.length})
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 8 }}>
                {errorEntries.map(entry => (
                  <EntryCard key={entry.id} entry={entry} onPause={pauseEntry} onResume={resumeEntry} />
                ))}
              </div>
            </section>
          )}

          {waitingEntries.length > 0 && (
            <section>
              <div style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 6 }}>
                QUEUE ({waitingEntries.length} waiting)
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {waitingEntries.map(entry => (
                  <div
                    key={entry.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 10,
                      padding: '0.45rem 0.65rem',
                      background: C.card,
                      border: `1px solid ${C.border}`,
                      borderRadius: 4,
                      fontSize: '0.68rem',
                    }}
                  >
                    <span style={{ color: C.textDead, minWidth: 28 }}>#{entry.queue_position}</span>
                    <span style={{ color: C.text, flex: 1 }}>{entry.program_name}</span>
                    {entry.platform && <span style={{ color: C.textMute, fontSize: '0.6rem' }}>{entry.platform}</span>}
                    <span style={{ color: C.textDead, fontSize: '0.6rem' }}>×{entry.total_scans_completed}</span>
                    <button onClick={() => void pauseEntry(entry.id)} style={btnStyle(C.textDead)}>pause</button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {selectedPool && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <ConcurrencyPanel minConcurrent={selectedPool.min_concurrent} maxConcurrent={selectedPool.max_concurrent} onSave={saveConcurrency} />

            <div style={{ padding: '0.85rem', background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: '0.68rem' }}>
              <div style={{ color: C.textMute, marginBottom: 8, fontSize: '0.65rem', letterSpacing: '0.08em' }}>CYCLE INFO</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4, color: C.textMute }}>
                <div>Cycle <strong style={{ color: C.text }}>#{selectedPool.current_cycle}</strong></div>
                {selectedPool.target_cycle_days && (
                  <div>Target <strong style={{ color: C.text }}>{selectedPool.target_cycle_days}d</strong></div>
                )}
                {selectedPool.last_cycle_completed_at && (
                  <div>Last complete <strong style={{ color: C.text }}>{fmtDate(selectedPool.last_cycle_completed_at)}</strong></div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
