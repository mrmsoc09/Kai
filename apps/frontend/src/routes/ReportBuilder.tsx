import React, { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { toast } from '../store/toasts'

export default function ReportBuilder() {
  const [formats, setFormats] = useState<any[]>([])
  const [fmt, setFmt] = useState('')
  const [findingId, setFindingId] = useState('')
  const [mitigation, setMitigation] = useState('')
  const [content, setContent] = useState('')
  const [rendering, setRendering] = useState(false)
  const [finalizing, setFinalizing] = useState(false)

  useEffect(() => {
    api.get('/reports/formats')
      .then((r) => {
        const fmts = r.data?.formats ?? r.data ?? []
        setFormats(fmts)
        if (fmts.length > 0) setFmt(fmts[0].id)
      })
      .catch(() => { /* formats unavailable */ })
  }, [])

  const render = async () => {
    if (!fmt) { toast.warning('Select a report format'); return }
    setRendering(true)
    setContent('')
    try {
      const payload = {
        format_id: fmt,
        ...(findingId ? { finding_id: findingId } : {}),
        finding: { title: 'Finding', severity: 'medium', impact: '', summary: '', scope: '', references: [] },
        evidence: { repro: '', artifacts: {} },
        mitigation: { plan: mitigation, timeline: 'TBD' },
      }
      const r = await api.post('/reports/render', payload)
      setContent(r.data?.content ?? JSON.stringify(r.data, null, 2))
    } catch (e: any) {
      toast.error(`Render failed: ${e.message}`)
    } finally {
      setRendering(false)
    }
  }

  const finalize = async () => {
    if (!findingId.trim()) { toast.warning('Enter a finding ID to finalize'); return }
    setFinalizing(true)
    try {
      const payload = { finding_id: findingId, mitigation: { plan: mitigation, timeline: 'TBD' }, duplicate_check: { status: 'clear' } }
      await api.post('/reports/finalize', payload)
      toast.success('Report finalized. Ready for HiL review.')
    } catch (e: any) {
      toast.error(`Finalize blocked: ${e.message}`)
    } finally {
      setFinalizing(false)
    }
  }

  const copyContent = () => {
    if (!content) return
    navigator.clipboard.writeText(content).then(() => toast.success('Copied to clipboard'))
  }

  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace" }}>
      <h1 style={{ color: '#a78bfa', fontSize: '1.3rem', fontWeight: 700, marginBottom: '1.25rem' }}>Report Builder</h1>
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.25rem' }}>
        {/* Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div>
            <label style={lbl}>FORMAT</label>
            <select value={fmt} onChange={(e) => setFmt(e.target.value)} style={inp}>
              {formats.length === 0 && <option value=''>Loading…</option>}
              {formats.map((f: any) => <option key={f.id} value={f.id}>{f.name ?? f.id}</option>)}
            </select>
          </div>
          <div>
            <label style={lbl}>FINDING ID (optional)</label>
            <input value={findingId} onChange={(e) => setFindingId(e.target.value)} placeholder='UUID of finding…' style={inp} />
          </div>
          <div>
            <label style={lbl}>MITIGATION PLAN</label>
            <textarea
              value={mitigation}
              onChange={(e) => setMitigation(e.target.value)}
              rows={5}
              placeholder='Describe the fix, patch, or workaround…'
              style={{ ...inp, resize: 'vertical' }}
            />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <button onClick={render} disabled={rendering} style={btnCyan}>
              {rendering ? 'Rendering…' : 'Render Draft'}
            </button>
            <button onClick={finalize} disabled={finalizing} style={btnOrange}>
              {finalizing ? 'Finalizing…' : 'Finalize for HiL'}
            </button>
          </div>
          <p style={{ color: '#6F8E7A', fontSize: '0.7rem' }}>
            Finalize submits the report for HiL review. A finding ID is required.
          </p>
        </div>

        {/* Preview */}
        <div style={{ background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 6, padding: '1rem', position: 'relative', minHeight: '60vh', overflow: 'auto' }}>
          {content && (
            <button onClick={copyContent} style={{ position: 'absolute', top: 10, right: 10, padding: '3px 8px', background: '#355E3B', border: 'none', borderRadius: 3, color: '#8FAF9B', cursor: 'pointer', fontSize: '0.75rem' }}>
              Copy
            </button>
          )}
          <pre style={{ color: '#8FAF9B', fontSize: '0.78rem', whiteSpace: 'pre-wrap', margin: 0 }}>
            {content || <span style={{ color: '#355E3B' }}>Report preview will appear here…</span>}
          </pre>
        </div>
      </div>
    </div>
  )
}

const lbl: React.CSSProperties = { display: 'block', color: '#6F8E7A', fontSize: '0.7rem', letterSpacing: '0.1em', marginBottom: 6 }
const inp: React.CSSProperties = { width: '100%', boxSizing: 'border-box', padding: '0.5rem 0.65rem', background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 4, color: '#8FAF9B', fontFamily: 'inherit', fontSize: '0.85rem' }
const btnCyan: React.CSSProperties = { padding: '0.55rem', background: '#0891b2', color: '#c7d2e0', border: 'none', borderRadius: 4, fontFamily: 'inherit', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }
const btnOrange: React.CSSProperties = { padding: '0.55rem', background: '#D97706', color: '#c7d2e0', border: 'none', borderRadius: 4, fontFamily: 'inherit', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }
