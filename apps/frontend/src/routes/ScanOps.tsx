/**
 * SCAN OPS — Unified tabbed view: Arsenal | Run History | HiL Queue | Live Logs
 */
import React, { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { listFindings, approveHIL } from '../lib/api'

const C = {
  bg: '#0B0C0D', card: '#111316', border: '#4E7A57', borderDim: '#2E4A38',
  green: '#355E3B', greenGlow: 'rgba(53,94,59,0.22)',
  orange: '#D97706', red: '#A12B2B', purple: '#5A2E8A',
  text: '#8FAF9B', textSub: '#5F7665', textMute: '#6F8E7A', textDead: '#3A4F43',
}
const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"

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
            <span style={{ background: C.greenGlow, color: C.green, border: '1px solid rgba(95,143,107,0.3)', borderRadius: 10, padding: '0 5px', fontSize: '0.58rem' }}>{t.badge}</span>
          )}
        </button>
      ))}
    </div>
  )
}

// ─── ARSENAL ──────────────────────────────────────────────────────────────────

const TOOL_ICONS: Record<string, string> = {
  recon: '◎', scan: '▷', exploit: '◈', report: '▦',
  web: '⬡', network: '◉', osint: '✦', fuzzing: '≋',
}

function Arsenal() {
  const [tools, setTools] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [localTools, setLocalTools] = useState<any[]>(() => {
    try { return JSON.parse(localStorage.getItem('k1_local_tools') || '[]') } catch { return [] }
  })
  const [showAdd, setShowAdd] = useState(false)
  const [newTool, setNewTool] = useState({ name: '', category: '', description: '', tags: '' })

  useEffect(() => {
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || ''
    fetch('/api/v1/tools', { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.json())
      .then(d => setTools(Array.isArray(d) ? d : d.tools ?? []))
      .catch(() => setTools([]))
      .finally(() => setLoading(false))
  }, [])

  const mergedTools = [...localTools, ...tools]

  const cats = mergedTools.reduce((acc: Record<string, any[]>, t) => {
    const cat = (t.category || 'other').toLowerCase()
    acc[cat] = acc[cat] || []
    acc[cat].push(t)
    return acc
  }, {})

  const filtered = search
    ? mergedTools.filter(t => (t.name || t.id || '').toLowerCase().includes(search.toLowerCase()) || (t.description || '').toLowerCase().includes(search.toLowerCase()))
    : null

  const addLocalTool = () => {
    if (!newTool.name.trim()) return
    const created = {
      id: `local-${Date.now()}`,
      name: newTool.name.trim(),
      category: newTool.category.trim() || 'custom',
      description: newTool.description.trim(),
      tags: newTool.tags.split(',').map(t => t.trim()).filter(Boolean),
      local: true,
    }
    const next = [created, ...localTools]
    setLocalTools(next)
    localStorage.setItem('k1_local_tools', JSON.stringify(next))
    setNewTool({ name: '', category: '', description: '', tags: '' })
    setShowAdd(false)
  }

  const renderTools = (list: any[]) => (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 8 }}>
      {list.map((t, i) => {
        const key = `${t.id}-${i}`
        const expanded = expandedId === key
        const icon = TOOL_ICONS[t.category?.toLowerCase()] || '▷'
        return (
          <div
            key={key}
            style={{
              background: C.bg, border: `1px solid ${C.border}`, borderRadius: 6,
              padding: '10px 14px', transition: 'border-color 0.12s',
              cursor: 'pointer',
            }}
            onClick={() => setExpandedId(expanded ? null : key)}
            onMouseEnter={e => e.currentTarget.style.borderColor = C.purple}
            onMouseLeave={e => e.currentTarget.style.borderColor = C.border}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: expanded ? 8 : 0 }}>
              <span style={{ color: C.green, fontSize: '0.85rem', width: 18, textAlign: 'center' }}>{icon}</span>
              <div style={{ flex: 1 }}>
                <div style={{ color: C.text, fontWeight: 600, fontSize: '0.78rem', fontFamily: MONO }}>
                  {t.name || t.id}
                </div>
                {!expanded && t.description && (
                  <div style={{ color: C.textMute, fontSize: '0.62rem', marginTop: 2, lineHeight: 1.3 }}>
                    {t.description.slice(0, 60)}{t.description.length > 60 ? '…' : ''}
                  </div>
                )}
              </div>
              <span style={{ color: C.textMute, fontSize: '0.7rem' }}>{expanded ? '▼' : '▶'}</span>
            </div>
            {expanded && (
              <div>
                {t.description && (
                  <div style={{ color: C.textSub, fontSize: '0.72rem', lineHeight: 1.55, marginBottom: 8 }}>
                    {t.description}
                  </div>
                )}
                {t.input_schema?.properties && (
                  <div style={{ marginBottom: 8 }}>
                    <div style={{ color: C.textMute, fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.12em', marginBottom: 6 }}>PARAMETERS</div>
                    {Object.entries(t.input_schema.properties).map(([k, v]: [string, any]) => (
                      <div key={k} style={{ display: 'flex', gap: 8, padding: '4px 0', borderBottom: `1px solid ${C.borderDim}` }}>
                        <span style={{ color: C.green, fontFamily: MONO, fontSize: '0.65rem', minWidth: 100 }}>{k}</span>
                        <span style={{ color: C.textMute, fontSize: '0.62rem' }}>{v.type || '—'}</span>
                        {v.description && <span style={{ color: C.textMute, fontSize: '0.62rem', flex: 1 }}>{v.description}</span>}
                      </div>
                    ))}
                  </div>
                )}
                {t.tags?.length > 0 && (
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {t.tags.map((tag: string) => (
                      <span key={tag} style={{ background: C.card, border: `1px solid ${C.border}`, color: C.textMute, fontSize: '0.55rem', padding: '1px 5px', borderRadius: 3 }}>{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )

  if (loading) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>▓▒░ LOADING ARSENAL…</div>

  return (
    <div style={{ padding: '1.25rem 1.5rem' }}>
      <div style={{ display: 'flex', gap: 10, marginBottom: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search tools…"
          style={{ flex: 1, maxWidth: 320, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '7px 12px', fontFamily: MONO, fontSize: '0.75rem', outline: 'none' }}
        />
        <button
          onClick={() => setShowAdd(v => !v)}
          style={{ padding: '7px 10px', background: C.green, color: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}
        >
          {showAdd ? 'Close' : 'Add Tool'}
        </button>
        <span style={{ color: C.textMute, fontSize: '0.65rem', fontFamily: MONO }}>{mergedTools.length} tools registered</span>
      </div>

      {showAdd && (
        <div style={{ marginBottom: '1rem', padding: '12px', background: C.card, border: `1px solid ${C.border}`, borderRadius: 6 }}>
          <div style={{ display: 'grid', gap: 8, gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))' }}>
            <input
              placeholder="Tool name"
              value={newTool.name}
              onChange={(e) => setNewTool({ ...newTool, name: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
            <input
              placeholder="Category"
              value={newTool.category}
              onChange={(e) => setNewTool({ ...newTool, category: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
            <input
              placeholder="Tags (comma separated)"
              value={newTool.tags}
              onChange={(e) => setNewTool({ ...newTool, tags: e.target.value })}
              style={{ background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
            />
          </div>
          <textarea
            placeholder="Description"
            value={newTool.description}
            onChange={(e) => setNewTool({ ...newTool, description: e.target.value })}
            style={{ marginTop: 8, width: '100%', minHeight: 70, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '6px 10px', fontFamily: MONO, fontSize: '0.7rem' }}
          />
          <div style={{ marginTop: 8, display: 'flex', gap: 8 }}>
            <button onClick={addLocalTool} style={{ padding: '6px 10px', background: C.green, color: '#0B0C0D', border: `1px solid ${C.border}`, borderRadius: 4, fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}>Save Tool</button>
            <button onClick={() => setShowAdd(false)} style={{ padding: '6px 10px', background: 'transparent', color: C.text, border: `1px solid ${C.border}`, borderRadius: 4, fontFamily: MONO, fontSize: '0.65rem', fontWeight: 700, cursor: 'pointer' }}>Cancel</button>
          </div>
        </div>
      )}

      {filtered ? (
        renderTools(filtered)
      ) : (
        Object.entries(cats).map(([cat, items]) => (
          <div key={cat} style={{ marginBottom: '1.5rem' }}>
            <div style={{ color: C.textMute, fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.18em', marginBottom: 8, padding: '4px 0', borderBottom: `1px solid ${C.border}` }}>
              {cat.toUpperCase()} · {items.length}
            </div>
            {renderTools(items)}
          </div>
        ))
      )}
    </div>
  )
}

// ─── RUN HISTORY ──────────────────────────────────────────────────────────────

function RunHistory() {
  const [runs, setRuns] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || ''
    fetch('/api/v1/runs?limit=50', { headers: { Authorization: `Bearer ${tok}` } })
      .then(r => r.json())
      .then(d => {
        const next = Array.isArray(d?.runs) ? d.runs : Array.isArray(d) ? d : []
        setRuns(next)
      })
      .catch(() => setRuns([]))
      .finally(() => setLoading(false))
  }, [])

  const statusColor: Record<string, string> = {
    success: C.green, completed: C.green, failed: C.red, error: C.red,
    running: C.orange, pending: C.textMute, cancelled: C.textMute,
  }

  if (loading) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>▓▒░ LOADING RUN HISTORY…</div>
  if (!Array.isArray(runs) || runs.length === 0) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>NO RUNS FOUND</div>

  return (
    <div style={{ padding: '1.25rem 1.5rem' }}>
      <div style={{ color: C.textMute, fontSize: '0.65rem', fontFamily: MONO, marginBottom: '1rem' }}>
        {runs.length} runs found
      </div>
      {runs.map((run, i) => {
        const expanded = expandedId === run.id
        const sc = statusColor[run.status?.toLowerCase()] || C.textMute
        return (
          <div
            key={run.id || i}
            style={{
              background: C.card, border: `1px solid ${C.border}`, borderRadius: 6,
              marginBottom: 6, cursor: 'pointer', transition: 'border-color 0.1s',
            }}
            onClick={() => setExpandedId(expanded ? null : run.id)}
            onMouseEnter={e => e.currentTarget.style.borderColor = C.purple}
            onMouseLeave={e => e.currentTarget.style.borderColor = C.border}
          >
            <div style={{ padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: sc, boxShadow: run.status === 'running' ? `0 0 8px ${sc}` : 'none', flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ color: C.text, fontSize: '0.78rem', fontWeight: 600, fontFamily: MONO }}>
                  {run.tool_id || run.name || `Run ${run.id?.slice(0, 8)}`}
                </div>
                <div style={{ color: C.textMute, fontSize: '0.62rem', marginTop: 2 }}>
                  {run.program_id && `${run.program_id} · `}
                  {new Date(run.created_at || run.started_at || Date.now()).toLocaleString()}
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ color: sc, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.08em' }}>
                  {(run.status || '—').toUpperCase()}
                </div>
                {run.duration_ms && (
                  <div style={{ color: C.textMute, fontSize: '0.58rem', marginTop: 2 }}>
                    {(run.duration_ms / 1000).toFixed(1)}s
                  </div>
                )}
              </div>
              <span style={{ color: C.textMute, fontSize: '0.7rem' }}>{expanded ? '▼' : '▶'}</span>
            </div>

            {expanded && (
              <div style={{ padding: '0 14px 12px', borderTop: `1px solid ${C.border}` }}>
                {run.output && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ color: C.textMute, fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.14em', marginBottom: 6 }}>OUTPUT</div>
                    <pre style={{
                      color: C.textSub, fontSize: '0.68rem', fontFamily: MONO, lineHeight: 1.5,
                      background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4,
                      padding: '8px 10px', margin: 0, overflowX: 'auto', maxHeight: 200, overflowY: 'auto',
                      whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                    }}>
                      {typeof run.output === 'string' ? run.output : JSON.stringify(run.output, null, 2)}
                    </pre>
                  </div>
                )}
                {run.error && (
                  <div style={{ marginTop: 10, padding: '8px 10px', background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 4, color: C.red, fontFamily: MONO, fontSize: '0.68rem' }}>
                    {run.error}
                  </div>
                )}
                {run.params && (
                  <div style={{ marginTop: 10 }}>
                    <div style={{ color: C.textMute, fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.14em', marginBottom: 6 }}>PARAMETERS</div>
                    <pre style={{ color: C.textMute, fontSize: '0.65rem', fontFamily: MONO, margin: 0, whiteSpace: 'pre-wrap' }}>
                      {JSON.stringify(run.params, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── HIL QUEUE ────────────────────────────────────────────────────────────────

const SEV_COLORS: Record<string, string> = {
  CRITICAL: '#A12B2B', HIGH: '#D97706', MEDIUM: '#E0A43A', LOW: '#355E3B', INFO: '#5A2E8A',
}

function HiLQueue() {
  const [findings, setFindings] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [actingId, setActingId] = useState<string | null>(null)
  const navigate = useNavigate()

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await listFindings({ status: 'in_review', page_size: 50 })
      const items = r.data?.items ?? r.data ?? []
      // Also fetch hil_approved
      const r2 = await listFindings({ status: 'new', page_size: 50 })
      const items2 = r2.data?.items ?? r2.data ?? []
      setFindings([...items, ...items2].filter(f => ['new', 'in_review', 'hil_approved'].includes(f.status)))
    } catch { setFindings([]) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleApprove = async (fid: string) => {
    setActingId(fid)
    try { await approveHIL(fid); await load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Approval failed') }
    finally { setActingId(null) }
  }

  if (loading) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>▓▒░ LOADING HiL QUEUE…</div>
  if (findings.length === 0) return (
    <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>
      <div style={{ marginBottom: 8 }}>NO FINDINGS AWAITING REVIEW</div>
      <div style={{ color: C.textDead, fontSize: '0.65rem' }}>All clear — no human-in-the-loop actions pending</div>
    </div>
  )

  return (
    <div style={{ padding: '1.25rem 1.5rem' }}>
      <div style={{ color: C.orange, fontSize: '0.65rem', fontFamily: MONO, fontWeight: 700, letterSpacing: '0.12em', marginBottom: '1rem' }}>
        {findings.length} FINDING{findings.length !== 1 ? 'S' : ''} REQUIRE REVIEW
      </div>
      {findings.map(f => {
        const expanded = expandedId === f.id
        const sc = SEV_COLORS[f.severity?.toUpperCase()] || C.textMute
        const busy = actingId === f.id
        return (
          <div key={f.id} style={{ background: C.card, border: `1px solid ${C.border}`, borderRadius: 6, marginBottom: 8 }}>
            <div style={{ padding: '12px 14px', display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div style={{ flexShrink: 0, marginTop: 2 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: sc, boxShadow: `0 0 8px ${sc}` }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: C.text, fontWeight: 700, fontSize: '0.82rem', marginBottom: 4 }}>
                  {f.title}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <span style={{ color: sc, fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.08em' }}>
                    {f.severity?.toUpperCase()}
                  </span>
                  <span style={{ color: C.textMute, fontSize: '0.6rem' }}>{f.program}</span>
                  <span style={{ color: C.textMute, fontSize: '0.6rem' }}>{f.asset}</span>
                  <span style={{ color: C.textMute, fontSize: '0.6rem', marginLeft: 'auto' }}>
                    {new Date(f.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', gap: 6, flexShrink: 0 }}>
                <button
                  onClick={(e) => { e.stopPropagation(); setExpandedId(expanded ? null : f.id) }}
                  style={{ padding: '4px 8px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 3, color: C.textMute, fontFamily: MONO, fontSize: '0.6rem', cursor: 'pointer' }}
                >
                  {expanded ? 'COLLAPSE' : 'EXPAND'}
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); navigate(`/findings/${f.id}`) }}
                  style={{ padding: '4px 8px', background: 'transparent', border: `1px solid ${C.border}`, borderRadius: 3, color: C.textSub, fontFamily: MONO, fontSize: '0.6rem', cursor: 'pointer' }}
                >
                  DETAIL
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); handleApprove(f.id) }}
                  disabled={busy}
                  style={{ padding: '4px 10px', background: busy ? C.borderDim : C.green, border: 'none', borderRadius: 3, color: busy ? C.textMute : '#0B0C0D', fontFamily: MONO, fontSize: '0.6rem', fontWeight: 700, cursor: busy ? 'not-allowed' : 'pointer' }}
                >
                  {busy ? '…' : 'APPROVE'}
                </button>
              </div>
            </div>
            {expanded && (
              <div style={{ padding: '0 14px 14px', borderTop: `1px solid ${C.border}` }}>
                <div style={{ color: C.textSub, fontSize: '0.75rem', lineHeight: 1.65, marginTop: 10, marginBottom: 10 }}>
                  {f.description}
                </div>
                {f.reproducibility_score !== undefined && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                    <span style={{ color: C.textMute, fontSize: '0.62rem' }}>Reproducibility:</span>
                    <div style={{ flex: 1, maxWidth: 120, height: 4, background: C.borderDim, borderRadius: 2 }}>
                      <div style={{ width: `${(f.reproducibility_score ?? 0) * 100}%`, height: '100%', background: C.green, borderRadius: 2 }} />
                    </div>
                    <span style={{ color: C.green, fontSize: '0.62rem', fontFamily: MONO }}>
                      {Math.round((f.reproducibility_score ?? 0) * 100)}%
                    </span>
                  </div>
                )}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ─── LIVE LOGS ────────────────────────────────────────────────────────────────

function LiveLogs() {
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [error, setError] = useState<string>('')
  const bottomRef = useRef<HTMLDivElement>(null)

  const load = useCallback(() => {
    setError('')
    const tok = localStorage.getItem('k1_token') || localStorage.getItem('K1_DEV_TOKEN') || ''
    fetch('/api/v1/logs?limit=200', { headers: { Authorization: `Bearer ${tok}` } })
      .then(async r => {
        if (!r.ok) {
          throw new Error(`HTTP ${r.status}`)
        }
        const ct = r.headers.get('content-type') || ''
        if (!ct.includes('application/json')) {
          throw new Error('Non-JSON response')
        }
        return r.json()
      })
      .then(d => {
        const next = Array.isArray(d?.logs)
          ? d.logs
          : Array.isArray(d?.items)
            ? d.items
            : Array.isArray(d)
              ? d
              : []
        setLogs(next)
        setLoading(false)
      })
      .catch((e) => {
        setLogs([])
        setError(String(e?.message || e || 'Log stream unavailable'))
        setLoading(false)
      })
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 5000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const filtered = filter
    ? logs.filter(l => JSON.stringify(l).toLowerCase().includes(filter.toLowerCase()))
    : logs

  const levelColor: Record<string, string> = {
    ERROR: C.red, WARN: C.orange, WARNING: C.orange,
    INFO: C.purple, DEBUG: C.textMute, SUCCESS: C.green,
  }

  if (loading) return <div style={{ padding: '3rem', textAlign: 'center', color: C.textMute, fontFamily: MONO, fontSize: '0.75rem' }}>▓▒░ LOADING LOGS…</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ padding: '8px 1.5rem', borderBottom: `1px solid ${C.border}`, display: 'flex', gap: 10, alignItems: 'center' }}>
        <input
          value={filter}
          onChange={e => setFilter(e.target.value)}
          placeholder="Filter logs…"
          style={{ flex: 1, maxWidth: 280, background: C.bg, border: `1px solid ${C.border}`, borderRadius: 4, color: C.text, padding: '5px 10px', fontFamily: MONO, fontSize: '0.72rem', outline: 'none' }}
        />
        <span style={{ color: C.textMute, fontSize: '0.62rem', fontFamily: MONO }}>{Array.isArray(filtered) ? filtered.length : 0} entries</span>
        <div style={{ width: 7, height: 7, borderRadius: '50%', background: C.green, boxShadow: `0 0 6px ${C.green}`, marginLeft: 'auto' }} />
        <span style={{ color: C.textMute, fontSize: '0.58rem', fontFamily: MONO }}>LIVE</span>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '8px 1.5rem', fontFamily: MONO, fontSize: '0.68rem', lineHeight: 1.6 }}>
        {error && (
          <div style={{ color: C.orange, fontSize: '0.7rem', marginBottom: 8 }}>
            Log stream unavailable: {error}
          </div>
        )}
        {(Array.isArray(filtered) ? filtered : []).map((log, i) => {
          const level = (log.level || log.severity || 'INFO').toUpperCase()
          const lc = levelColor[level] || C.textMute
          const ts = log.ts || log.timestamp || log.created_at || ''
          const msg = log.text || log.message || log.msg || JSON.stringify(log)
          return (
            <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 2, padding: '2px 0', borderBottom: `1px solid ${C.borderDim}` }}>
              <span style={{ color: C.textMute, minWidth: 70, flexShrink: 0 }}>
                {ts ? new Date(ts).toLocaleTimeString() : '—'}
              </span>
              <span style={{ color: lc, minWidth: 45, flexShrink: 0, fontWeight: 700 }}>{level}</span>
              <span style={{ color: log.source ? C.textSub : C.textMute, minWidth: 80, flexShrink: 0 }}>{log.source || ''}</span>
              <span style={{ color: C.textSub, flex: 1, wordBreak: 'break-word' }}>{msg}</span>
            </div>
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

// ─── Main ScanOps ─────────────────────────────────────────────────────────────

export default function ScanOps() {
  const [tab, setTab] = useState<'arsenal' | 'runs' | 'hil' | 'logs'>('arsenal')
  const [hilCount, setHilCount] = useState(0)

  useEffect(() => {
    listFindings({ status: 'in_review', page_size: 1 })
      .then(r => setHilCount(r.data?.total ?? 0))
      .catch(() => {})
  }, [])

  const tabs = [
    { id: 'arsenal', label: 'ARSENAL' },
    { id: 'runs',    label: 'RUN HISTORY' },
    { id: 'hil',     label: 'HiL QUEUE', badge: hilCount },
    { id: 'logs',    label: 'LIVE LOGS' },
  ]

  return (
    <div style={{ background: C.bg, minHeight: '100vh', fontFamily: MONO, display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '1rem 1.5rem 0', background: C.card, borderBottom: `1px solid ${C.border}` }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 2 }}>
          <span style={{ color: C.green, fontSize: '1.2rem' }}>▷</span>
          <h1 style={{ color: C.text, margin: 0, fontSize: '1.1rem', fontWeight: 700, letterSpacing: '0.05em' }}>SCAN OPS</h1>
          <span style={{ color: C.textMute, fontSize: '0.65rem', letterSpacing: '0.1em' }}>Arsenal · Runs · HiL Queue · Logs</span>
        </div>
        <TabBar tabs={tabs} active={tab} onChange={(id) => setTab(id as any)} />
      </div>
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {tab === 'arsenal' && <Arsenal />}
        {tab === 'runs'    && <RunHistory />}
        {tab === 'hil'     && <HiLQueue />}
        {tab === 'logs'    && <LiveLogs />}
      </div>
    </div>
  )
}
