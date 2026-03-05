import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from '../lib/api'
import { useStore } from '../store/system'

export default function Login() {
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useStore((s) => s.login)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token.trim()) { setError('Token is required.'); return }
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/auth/login', { token: token.trim() })
      const { access_token } = res.data
      const meRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${access_token}` },
      })
      login(access_token, { id: meRes.data.id, roles: meRes.data.roles ?? [] })
      navigate(from, { replace: true })
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Invalid token. Check your K1_DEV_TOKEN.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0a0c10',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    }}>
      <div style={{
        width: 400,
        padding: '2.5rem',
        background: '#0f1117',
        border: '1px solid #1e2330',
        borderRadius: 8,
        boxShadow: '0 0 40px rgba(0,255,65,0.06)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            fontSize: '2rem',
            fontWeight: 700,
            letterSpacing: '0.1em',
            background: 'linear-gradient(135deg, #00FF41 0%, #00cc33 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>K1</div>
          <div style={{ color: '#4a5568', fontSize: '0.75rem', marginTop: 4, letterSpacing: '0.2em' }}>
            SECURITY RESEARCH PLATFORM
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', color: '#8892a4', fontSize: '0.75rem', marginBottom: 6, letterSpacing: '0.1em' }}>
            ACCESS TOKEN
          </label>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Enter your K1_DEV_TOKEN…"
            autoFocus
            autoComplete="current-password"
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '0.6rem 0.75rem',
              background: '#070809',
              border: `1px solid ${error ? '#f97316' : '#1e2330'}`,
              borderRadius: 4,
              color: '#e2e8f0',
              fontSize: '0.875rem',
              fontFamily: 'inherit',
              outline: 'none',
              marginBottom: error ? 6 : 16,
            }}
          />
          {error && (
            <div style={{ color: '#f97316', fontSize: '0.75rem', marginBottom: 12 }}>{error}</div>
          )}
          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.65rem',
              background: loading ? '#1a2e1a' : '#00FF41',
              color: loading ? '#4a5568' : '#000',
              border: 'none',
              borderRadius: 4,
              fontFamily: 'inherit',
              fontWeight: 700,
              fontSize: '0.875rem',
              letterSpacing: '0.08em',
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background 0.15s',
            }}
          >
            {loading ? 'AUTHENTICATING…' : 'AUTHENTICATE'}
          </button>
        </form>

        <div style={{ marginTop: '1.5rem', padding: '0.75rem', background: '#070809', borderRadius: 4, border: '1px solid #1a2030' }}>
          <div style={{ color: '#4a5568', fontSize: '0.7rem', lineHeight: 1.6 }}>
            Set <span style={{ color: '#00FF41' }}>K1_DEV_TOKEN</span> in your environment and enter it above.
            The token is exchanged for a signed JWT — it is not stored in the browser.
          </div>
        </div>
      </div>
    </div>
  )
}
