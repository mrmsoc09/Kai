import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getFinding, requestHIL, submitFinding } from '../lib/api'
import { toast } from '../store/toasts'
import EvidencePanel, { EvidenceItem } from '../components/EvidencePanel'
import FindingForm from '../components/FindingForm'

type FindingData = {
  id: string
  program: string
  asset: string
  title: string
  description: string
  severity: string
  status: string
  created_at: string
  reproducibility_score?: number
  evidence?: EvidenceItem[]
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444', high: '#D97706', medium: '#D97706',
  low: '#22c55e', info: '#60a5fa',
}

const STATUS_FLOW: Record<string, string> = {
  new: 'in_review',
  in_review: 'hil_approved',
  hil_approved: 'submitted',
}

export default function FindingDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  // Special case: /findings/new renders the creation form
  if (id === 'new') return <FindingForm />

  const [finding, setFinding] = useState<FindingData | null>(null)
  const [loading, setLoading] = useState(true)
  const [evidence, setEvidence] = useState<EvidenceItem[]>([])
  const [acting, setActing] = useState(false)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    getFinding(id)
      .then((res) => {
        const f = res.data
        setFinding(f)
        setEvidence(f.evidence ?? [])
      })
      .catch((e) => toast.error(`Failed to load finding: ${e.message}`))
      .finally(() => setLoading(false))
  }, [id])

  const handleRequestHIL = async () => {
    if (!id) return
    setActing(true)
    try {
      await requestHIL(id)
      toast.success('HiL review requested.')
      setFinding((f) => f ? { ...f, status: 'in_review' } : f)
    } catch (e: any) {
      toast.error(`Failed to request HiL: ${e.message}`)
    } finally {
      setActing(false)
    }
  }

  const handleSubmit = async () => {
    if (!id) return
    setActing(true)
    try {
      // Compute a placeholder report hash from the finding ID
      const encoder = new TextEncoder()
      const buf = await crypto.subtle.digest('SHA-256', encoder.encode(id).buffer)
      const hashHex = Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, '0')).join('')
      await submitFinding(id, hashHex)
      toast.success('Finding submitted to program.')
      setFinding((f) => f ? { ...f, status: 'submitted' } : f)
    } catch (e: any) {
      toast.error(`Failed to submit: ${e.message}`)
    } finally {
      setActing(false)
    }
  }

  if (loading) return <div style={{ padding: '2rem', color: '#6F8E7A', fontFamily: 'monospace' }}>Loading finding…</div>
  if (!finding) return <div style={{ padding: '2rem', color: '#D97706', fontFamily: 'monospace' }}>Finding not found.</div>

  const sevColor = SEVERITY_COLORS[finding.severity] || '#6b7280'

  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace", maxWidth: 900 }}>
      {/* Breadcrumb */}
      <div style={{ color: '#6F8E7A', fontSize: '0.75rem', marginBottom: '1rem' }}>
        <Link to='/findings' style={{ color: '#6F8E7A', textDecoration: 'none' }}>Findings</Link>
        {' → '}
        <span style={{ color: '#8FAF9B' }}>{finding.id.slice(0, 8)}…</span>
      </div>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem' }}>
        <div>
          <h1 style={{ color: '#8FAF9B', fontSize: '1.2rem', fontWeight: 700, margin: '0 0 6px' }}>
            {finding.title}
          </h1>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Badge color={sevColor}>{finding.severity.toUpperCase()}</Badge>
            <Badge color='#60a5fa'>{finding.status.replace(/_/g, ' ').toUpperCase()}</Badge>
            <span style={{ color: '#6F8E7A', fontSize: '0.75rem', alignSelf: 'center' }}>{finding.program}</span>
          </div>
        </div>

        {/* Status action buttons */}
        <div style={{ display: 'flex', gap: 8 }}>
          {finding.status === 'new' && (
            <ActionBtn onClick={handleRequestHIL} disabled={acting} color='#a78bfa'>
              Request HiL Review
            </ActionBtn>
          )}
          {finding.status === 'hil_approved' && (
            <ActionBtn onClick={handleSubmit} disabled={acting} color='#355E3B'>
              Submit to Program
            </ActionBtn>
          )}
        </div>
      </div>

      {/* Meta grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: '1.5rem' }}>
        <MetaCard label='Asset' value={finding.asset} />
        <MetaCard label='Program' value={finding.program} />
        <MetaCard label='Created' value={finding.created_at ? new Date(finding.created_at).toLocaleDateString() : '—'} />
        {finding.reproducibility_score !== undefined && (
          <MetaCard label='Reproducibility' value={`${(finding.reproducibility_score * 100).toFixed(0)}%`} />
        )}
      </div>

      {/* Description */}
      <section style={{ marginBottom: '2rem' }}>
        <div style={{ color: '#6F8E7A', fontSize: '0.7rem', letterSpacing: '0.1em', marginBottom: 8 }}>DESCRIPTION</div>
        <div style={{
          padding: '1rem',
          background: '#0B0C0D',
          border: '1px solid #355E3B',
          borderRadius: 6,
          color: '#8FAF9B',
          fontSize: '0.85rem',
          lineHeight: 1.7,
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {finding.description}
        </div>
      </section>

      {/* Evidence */}
      <section style={{ padding: '1rem', background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 6 }}>
        <EvidencePanel
          findingId={finding.id}
          existingEvidence={evidence}
          onAdded={(item) => setEvidence((prev) => [...prev, item])}
        />
      </section>
    </div>
  )
}

function Badge({ children, color }: { children: React.ReactNode; color: string }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 3,
      background: `${color}22`,
      color,
      fontWeight: 700,
      fontSize: '0.7rem',
      letterSpacing: '0.04em',
    }}>{children}</span>
  )
}

function MetaCard({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ padding: '0.6rem 0.75rem', background: '#0B0C0D', border: '1px solid #355E3B', borderRadius: 4 }}>
      <div style={{ color: '#6F8E7A', fontSize: '0.65rem', letterSpacing: '0.08em', marginBottom: 4 }}>{label.toUpperCase()}</div>
      <div style={{ color: '#8FAF9B', fontSize: '0.82rem', wordBreak: 'break-all' }}>{value}</div>
    </div>
  )
}

function ActionBtn({ children, onClick, disabled, color }: { children: React.ReactNode; onClick: () => void; disabled: boolean; color: string }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '0.5rem 1rem',
        background: disabled ? '#1a2030' : color,
        color: disabled ? '#6F8E7A' : color === '#355E3B' ? '#000' : '#c7d2e0',
        border: 'none',
        borderRadius: 4,
        fontFamily: 'inherit',
        fontWeight: 700,
        fontSize: '0.8rem',
        cursor: disabled ? 'not-allowed' : 'pointer',
        letterSpacing: '0.04em',
      }}
    >
      {disabled ? '…' : children}
    </button>
  )
}
