import React, { useEffect, useState } from 'react'

type ValidationTool = { id: string; name: string; description: string }

export default function Validation(){
  const [tools, setTools] = useState<ValidationTool[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchTools = async () => {
      try {
        const res = await fetch('/api/v1/approvals/tools')
        const data = await res.json()
        if (data.tools) setTools(data.tools)
      } catch (e:any) {
        setError(e?.message || 'Failed to load validation tools')
      } finally {
        setLoading(false)
      }
    }
    fetchTools()
  }, [])

  return (
    <div style={{ padding: 24 }}>
      <h1 style={{ marginBottom: 8 }}>Validation & Intrusive Tools</h1>
      <p style={{ color: '#667', marginBottom: 16 }}>
        Tier-2 tools require approval. Use the console or API to approve a run before execution.
      </p>
      {loading && <p>Loading…</p>}
      {error && <p style={{ color: 'crimson' }}>{error}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 16 }}>
        {tools.map((t) => (
          <div key={t.id} style={{ border: '1px solid #e3e3e3', borderRadius: 8, padding: 16, background: '#fafafa' }}>
            <h3 style={{ margin: 0 }}>{t.name}</h3>
            <p style={{ margin: '8px 0', color: '#555' }}>{t.description}</p>
            <code style={{ fontSize: 12, color: '#333', background: '#eef', padding: '2px 4px', borderRadius: 4 }}>{t.id}</code>
          </div>
        ))}
        {!loading && !error && tools.length === 0 && <p>No intrusive tools registered or API unavailable.</p>}
      </div>
    </div>
  )
}
