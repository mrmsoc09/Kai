import React, { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'
import { useStore } from '../store/system'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const login = useStore((s) => s.login)
  const navigate = useNavigate()
  const location = useLocation()
  const from = (location.state as any)?.from?.pathname || '/dashboard'

  const inputStyle: React.CSSProperties = {
    width: '100%',
    boxSizing: 'border-box',
    padding: '0.6rem 0.75rem',
    background: '#0B0C0D',
    border: `1px solid ${error ? '#D97706' : '#355E3B'}`,
    borderRadius: 4,
    color: '#8FAF9B',
    fontSize: '0.875rem',
    fontFamily: 'inherit',
    outline: 'none',
    marginBottom: 12,
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) { setError('Username is required.'); return }
    if (!password) { setError('Password is required.'); return }
    setError('')
    setLoading(true)
    try {
      // OAuth2 password grant — must be submitted as form-urlencoded
      const params = new URLSearchParams()
      params.append('username', username.trim())
      params.append('password', password)

      const res = await axios.post(`${API_BASE}/auth/token`, params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        withCredentials: true,
      })

      const { access_token, user_id, tenant_id, role } = res.data
      login(access_token, {
        id: user_id ?? username,
        roles: role ? [role] : [],
        tenant_id: tenant_id ?? undefined,
      })
      navigate(from, { replace: true })
    } catch (err: any) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Invalid credentials.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0B0C0D',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    }}>
      <div style={{
        width: 400,
        padding: '2.5rem',
        background: '#0f1117',
        border: '1px solid #355E3B',
        borderRadius: 8,
        boxShadow: '0 0 40px rgba(95,143,107,0.06)',
      }}>
        {/* Logo */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{
            fontSize: '2rem',
            fontWeight: 700,
            letterSpacing: '0.1em',
            background: 'linear-gradient(135deg, #355E3B 0%, #2D4E33 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>K1</div>
          <div style={{ color: '#6F8E7A', fontSize: '0.75rem', marginTop: 4, letterSpacing: '0.2em' }}>
            SECURITY RESEARCH PLATFORM
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <label style={{ display: 'block', color: '#8FAF9B', fontSize: '0.75rem', marginBottom: 6, letterSpacing: '0.1em' }}>
            USERNAME
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="username"
            autoFocus
            autoComplete="username"
            style={inputStyle}
          />

          <label style={{ display: 'block', color: '#8FAF9B', fontSize: '0.75rem', marginBottom: 6, letterSpacing: '0.1em' }}>
            PASSWORD
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            style={{ ...inputStyle, marginBottom: error ? 6 : 16 }}
          />

          {error && (
            <div style={{ color: '#D97706', fontSize: '0.75rem', marginBottom: 12 }}>{error}</div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '0.65rem',
              background: loading ? '#1a2e1a' : '#355E3B',
              color: loading ? '#6F8E7A' : '#000',
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
            {loading ? 'AUTHENTICATING…' : 'SIGN IN'}
          </button>
        </form>
      </div>
    </div>
  )
}
