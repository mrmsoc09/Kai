import React, { useEffect, useState } from 'react'
import { api, getScope, upsertScope } from '../lib/api'
import { toast } from '../store/toasts'

// Scope enforcement decision log entry (from /orchestrator/scope-decisions)
type ScopeDecisionEntry = {
  target: string
  allowed: boolean
  reason: string
  evaluated_at: string
}

type ScopeEntry = { pattern: string; note?: string }
type ScopePolicy = {
  program: string
  in_scope: ScopeEntry[]
  out_of_scope: ScopeEntry[]
  scope_type?: string
}

export default function Scopes() {
  const [program, setProgram] = useState('')
  const [policy, setPolicy] = useState<ScopePolicy | null>(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [newPattern, setNewPattern] = useState('')
  const [newNote, setNewNote] = useState('')
  const [kind, setKind] = useState<'in_scope' | 'out_of_scope'>('in_scope')
  // Scope enforcement audit log — from /orchestrator/scope-decisions
  const [decisions, setDecisions] = useState<ScopeDecisionEntry[]>([])
  const [decisionsTotal, setDecisionsTotal] = useState<number>(0)

  // Load scope enforcement decisions from audit log (/orchestrator/scope-decisions)
  useEffect(() => {
    api.get('/orchestrator/scope-decisions', { params: { limit: 50 } })
      .then(r => {
        setDecisions(r.data?.decisions ?? [])
        setDecisionsTotal(r.data?.total ?? 0)
      })
      .catch(() => {}) // not fatal — page works without decisions
  }, [])

  const load = async () => {
    if (!program.trim()) return
    setLoading(true)
    try {
      const res = await getScope(program)
      setPolicy(res.data)
    } catch (e: any) {
      if (e?.response?.status === 404) {
        setPolicy({ program, in_scope: [], out_of_scope: [] })
        toast.info('No scope policy found. Starting fresh.')
      } else {
        toast.error(`Failed to load scope: ${e.message}`)
      }
    } finally {
      setLoading(false)
    }
  }

  const addEntry = () => {
    if (!newPattern.trim()) { toast.warning('Pattern is required'); return }
    if (!policy) return
    const entry: ScopeEntry = { pattern: newPattern.trim(), note: newNote.trim() || undefined }
    setPolicy({ ...policy, [kind]: [...policy[kind], entry] })
    setNewPattern('')
    setNewNote('')
  }

  const removeEntry = (k: 'in_scope' | 'out_of_scope', idx: number) => {
    if (!policy) return
    setPolicy({ ...policy, [k]: policy[k].filter((_, i) => i !== idx) })
  }

  const save = async () => {
    if (!policy) return
    setSaving(true)
    try {
      await upsertScope(policy.program, { in_scope: policy.in_scope, out_of_scope: policy.out_of_scope })
      toast.success('Scope policy saved.')
    } catch (e: any) {
      toast.error(`Failed to save scope: ${e.message}`)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace" }}>
      <h1 style={{ color: '#355E3B', fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.25rem' }}>
        Scope Management
      </h1>

      {/* Program selector */}
      <div style={{ display: 'flex', gap: 10, marginBottom: '1.5rem' }}>
        <input
          value={program}
          onChange={(e) => setProgram(e.target.value)}
          placeholder='Enter program ID (e.g. google_vrp)…'
          onKeyDown={(e) => e.key === 'Enter' && load()}
          style={input}
        />
        <button onClick={load} disabled={loading} style={btnGreen}>
          {loading ? 'Loading…' : 'Load'}
        </button>
      </div>

      {policy && (
        <>
          {/* Add entry */}
          <div style={{ padding: '1rem', background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 6, marginBottom: '1.25rem' }}>
            <div style={{ color: '#6F8E7A', fontSize: '0.7rem', letterSpacing: '0.1em', marginBottom: 10 }}>ADD ENTRY</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <select value={kind} onChange={(e) => setKind(e.target.value as any)} style={{ ...input, minWidth: 130 }}>
                <option value='in_scope'>In Scope</option>
                <option value='out_of_scope'>Out of Scope</option>
              </select>
              <input value={newPattern} onChange={(e) => setNewPattern(e.target.value)} placeholder='*.example.com or 192.168.0.0/24' style={{ ...input, flex: 2 }} />
              <input value={newNote} onChange={(e) => setNewNote(e.target.value)} placeholder='Note (optional)' style={{ ...input, flex: 1 }} />
              <button onClick={addEntry} style={btnGreen}>Add</button>
            </div>
          </div>

          {/* In scope */}
          <ScopeList
            title='In Scope'
            color='#355E3B'
            entries={policy.in_scope}
            onRemove={(i) => removeEntry('in_scope', i)}
          />

          {/* Out of scope */}
          <ScopeList
            title='Out of Scope'
            color='#D97706'
            entries={policy.out_of_scope}
            onRemove={(i) => removeEntry('out_of_scope', i)}
          />

          <div style={{ marginTop: '1rem', display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={save} disabled={saving} style={btnGreen}>
              {saving ? 'Saving…' : 'Save Scope Policy'}
            </button>
          </div>
        </>
      )}

      {/* Scope Enforcement Audit Log
          Data source: /orchestrator/scope-decisions → output/logs/scope_decisions.jsonl
          Shows recent allow/deny decisions made by the scope guardrail at runtime. */}
      {decisions.length > 0 && (
        <div style={{ marginTop: '2rem' }}>
          <div style={{ color: '#6F8E7A', fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 10 }}>
            SCOPE ENFORCEMENT LOG ({decisions.length} recent · {decisionsTotal} total)
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
            {decisions.map((d, i) => (
              <div
                key={i}
                style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '5px 10px',
                  background: '#0B0C0D',
                  border: `1px solid ${d.allowed ? '#355E3B22' : '#A12B2B22'}`,
                  borderRadius: 4,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                <span style={{
                  flexShrink: 0, fontSize: '0.6rem', fontWeight: 700, padding: '1px 6px', borderRadius: 3,
                  background: d.allowed ? 'rgba(53,94,59,0.15)' : 'rgba(161,43,43,0.15)',
                  color: d.allowed ? '#355E3B' : '#A12B2B',
                  border: `1px solid ${d.allowed ? 'rgba(53,94,59,0.3)' : 'rgba(161,43,43,0.3)'}`,
                }}>
                  {d.allowed ? 'ALLOW' : 'DENY'}
                </span>
                <span style={{ color: '#8FAF9B', fontSize: '0.78rem', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {d.target}
                </span>
                <span style={{ color: '#6F8E7A', fontSize: '0.65rem', flexShrink: 0 }}>
                  {d.reason}
                </span>
                <span style={{ color: '#3A4F43', fontSize: '0.6rem', flexShrink: 0 }}>
                  {new Date(d.evaluated_at).toLocaleTimeString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function ScopeList({ title, color, entries, onRemove }: {
  title: string; color: string; entries: ScopeEntry[]; onRemove: (i: number) => void
}) {
  return (
    <div style={{ marginBottom: '1rem' }}>
      <div style={{ color, fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 8 }}>
        {title} ({entries.length})
      </div>
      {entries.length === 0 ? (
        <div style={{ color: '#355E3B', fontSize: '0.75rem', padding: '0.5rem' }}>None defined</div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {entries.map((e, i) => (
            <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'center', padding: '0.45rem 0.75rem', background: '#0B0C0D', border: `1px solid ${color}22`, borderRadius: 4 }}>
              <span style={{ color, fontFamily: 'monospace', fontSize: '0.82rem', flex: 1 }}>{e.pattern}</span>
              {e.note && <span style={{ color: '#6F8E7A', fontSize: '0.72rem' }}>{e.note}</span>}
              <button onClick={() => onRemove(i)} style={{ background: 'none', border: 'none', color: '#6F8E7A', cursor: 'pointer', fontSize: '1rem', padding: 0, lineHeight: 1 }}>×</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const input: React.CSSProperties = {
  padding: '0.5rem 0.75rem',
  background: '#0f1117',
  border: '1px solid #355E3B',
  borderRadius: 4,
  color: '#8FAF9B',
  fontFamily: 'inherit',
  fontSize: '0.85rem',
  minWidth: 200,
}

const btnGreen: React.CSSProperties = {
  padding: '0.5rem 1rem',
  background: '#355E3B',
  color: '#000',
  border: 'none',
  borderRadius: 4,
  fontFamily: 'inherit',
  fontWeight: 700,
  fontSize: '0.85rem',
  cursor: 'pointer',
}
