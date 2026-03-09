import React, { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { listFindings } from '../lib/api'
import { toast } from '../store/toasts'

type Finding = {
  id: string
  program: string
  asset: string
  title: string
  severity: string
  status: string
  created_at: string
  reproducibility_score?: number
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#D97706',
  medium: '#D97706',
  low: '#22c55e',
  info: '#60a5fa',
}

const STATUS_COLORS: Record<string, string> = {
  new: '#60a5fa',
  in_review: '#D97706',
  hil_approved: '#a78bfa',
  submitted: '#355E3B',
  resolved: '#22c55e',
  rejected: '#ef4444',
  duplicate: '#6b7280',
}

const PAGE_SIZE = 25

export default function Findings() {
  const [findings, setFindings] = useState<Finding[]>([])
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [filterSeverity, setFilterSeverity] = useState('')
  const [filterStatus, setFilterStatus] = useState('')
  const [filterProgram, setFilterProgram] = useState('')
  const [sortBy, setSortBy] = useState<'created_at' | 'severity'>('created_at')

  const load = useCallback(async (pg: number) => {
    setLoading(true)
    try {
      const res = await listFindings({
        page: pg,
        page_size: PAGE_SIZE,
        severity: filterSeverity || undefined,
        status: filterStatus || undefined,
        program: filterProgram || undefined,
      })
      const data: Finding[] = res.data?.items ?? res.data ?? []
      setFindings(data)
      setHasMore(data.length === PAGE_SIZE)
    } catch (e: any) {
      toast.error(`Failed to load findings: ${e.message}`)
    } finally {
      setLoading(false)
    }
  }, [filterSeverity, filterStatus, filterProgram])

  useEffect(() => {
    setPage(1)
    load(1)
  }, [load])

  const handlePageChange = (next: number) => {
    setPage(next)
    load(next)
  }

  const sorted = [...findings].sort((a, b) => {
    if (sortBy === 'severity') {
      const order: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3, info: 4 }
      return (order[a.severity] ?? 5) - (order[b.severity] ?? 5)
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  })

  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace" }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
        <div>
          <h1 style={{ color: '#355E3B', fontSize: '1.4rem', fontWeight: 700, margin: 0 }}>Findings</h1>
          <div style={{ color: '#6F8E7A', fontSize: '0.75rem', marginTop: 4 }}>
            Vulnerability findings across all programs
          </div>
        </div>
        <Link
          to='/findings/new'
          style={{
            padding: '0.5rem 1rem',
            background: '#355E3B',
            color: '#000',
            fontWeight: 700,
            fontSize: '0.8rem',
            borderRadius: 4,
            textDecoration: 'none',
            letterSpacing: '0.05em',
          }}
        >
          + NEW FINDING
        </Link>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: '1rem', flexWrap: 'wrap' }}>
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          style={selectStyle}
        >
          <option value=''>All Severities</option>
          <option value='critical'>Critical</option>
          <option value='high'>High</option>
          <option value='medium'>Medium</option>
          <option value='low'>Low</option>
          <option value='info'>Info</option>
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          style={selectStyle}
        >
          <option value=''>All Statuses</option>
          <option value='new'>New</option>
          <option value='in_review'>In Review</option>
          <option value='hil_approved'>HiL Approved</option>
          <option value='submitted'>Submitted</option>
          <option value='resolved'>Resolved</option>
          <option value='rejected'>Rejected</option>
          <option value='duplicate'>Duplicate</option>
        </select>
        <input
          value={filterProgram}
          onChange={(e) => setFilterProgram(e.target.value)}
          placeholder='Filter by program…'
          style={{ ...selectStyle, minWidth: 180 }}
        />
        <select
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as any)}
          style={selectStyle}
        >
          <option value='created_at'>Sort: Newest</option>
          <option value='severity'>Sort: Severity</option>
        </select>
      </div>

      {/* Table */}
      {loading ? (
        <div style={{ color: '#6F8E7A', padding: '3rem', textAlign: 'center' }}>Loading findings…</div>
      ) : sorted.length === 0 ? (
        <div style={{ color: '#6F8E7A', padding: '3rem', textAlign: 'center', border: '1px dashed #355E3B', borderRadius: 6 }}>
          <div style={{ fontSize: '2rem', marginBottom: 8 }}>🔍</div>
          No findings match your filters.
          <br />
          <Link to='/findings/new' style={{ color: '#355E3B', marginTop: 12, display: 'inline-block' }}>
            Create your first finding →
          </Link>
        </div>
      ) : (
        <>
          <div style={{ border: '1px solid #355E3B', borderRadius: 6, overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
              <thead>
                <tr style={{ background: '#0f1117', borderBottom: '1px solid #355E3B' }}>
                  {['Severity', 'Title', 'Program', 'Asset', 'Status', 'Created'].map((h) => (
                    <th key={h} style={{ padding: '0.6rem 0.75rem', textAlign: 'left', color: '#6F8E7A', fontWeight: 600, letterSpacing: '0.05em' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((f, i) => (
                  <tr
                    key={f.id}
                    style={{ borderBottom: '1px solid #1a2030', background: i % 2 === 0 ? '#0B0C0D' : '#0B0C0D' }}
                  >
                    <td style={{ padding: '0.6rem 0.75rem' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 3,
                        background: `${SEVERITY_COLORS[f.severity] || '#6b7280'}22`,
                        color: SEVERITY_COLORS[f.severity] || '#6b7280',
                        fontWeight: 700,
                        fontSize: '0.7rem',
                        letterSpacing: '0.05em',
                      }}>
                        {f.severity?.toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', maxWidth: 300 }}>
                      <Link
                        to={`/findings/${f.id}`}
                        style={{ color: '#8FAF9B', textDecoration: 'none', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {f.title}
                      </Link>
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', color: '#8FAF9B', fontSize: '0.75rem' }}>{f.program}</td>
                    <td style={{ padding: '0.6rem 0.75rem', color: '#8FAF9B', fontSize: '0.75rem', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{f.asset}</td>
                    <td style={{ padding: '0.6rem 0.75rem' }}>
                      <span style={{
                        display: 'inline-block',
                        padding: '2px 8px',
                        borderRadius: 3,
                        background: `${STATUS_COLORS[f.status] || '#6b7280'}22`,
                        color: STATUS_COLORS[f.status] || '#6b7280',
                        fontSize: '0.7rem',
                        letterSpacing: '0.04em',
                      }}>
                        {f.status?.replace(/_/g, ' ').toUpperCase()}
                      </span>
                    </td>
                    <td style={{ padding: '0.6rem 0.75rem', color: '#6F8E7A', fontSize: '0.72rem' }}>
                      {f.created_at ? new Date(f.created_at).toLocaleDateString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 12 }}>
            <button
              disabled={page === 1}
              onClick={() => handlePageChange(page - 1)}
              style={pagerBtn(page === 1)}
            >
              ← Prev
            </button>
            <span style={{ color: '#6F8E7A', fontSize: '0.8rem', alignSelf: 'center' }}>Page {page}</span>
            <button
              disabled={!hasMore}
              onClick={() => handlePageChange(page + 1)}
              style={pagerBtn(!hasMore)}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  )
}

const selectStyle: React.CSSProperties = {
  padding: '0.4rem 0.6rem',
  background: '#0f1117',
  border: '1px solid #355E3B',
  borderRadius: 4,
  color: '#8FAF9B',
  fontFamily: 'inherit',
  fontSize: '0.8rem',
}

const pagerBtn = (disabled: boolean): React.CSSProperties => ({
  padding: '0.35rem 0.75rem',
  background: disabled ? '#0B0C0D' : '#0f1117',
  border: '1px solid #355E3B',
  borderRadius: 4,
  color: disabled ? '#355E3B' : '#8FAF9B',
  fontFamily: 'inherit',
  fontSize: '0.8rem',
  cursor: disabled ? 'not-allowed' : 'pointer',
})
