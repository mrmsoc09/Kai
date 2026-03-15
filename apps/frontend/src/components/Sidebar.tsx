import React, { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useStore } from '../store/system'
import { authLogout, getLLMConfig } from '../lib/api'

// ─── 8-page nav structure ─────────────────────────────────────────────────────

const NAV = [
  { to: '/dashboard', icon: '◉', label: 'COMMAND CTR',  sub: 'Mission Control' },
  { to: '/hunt',      icon: '◈', label: 'HUNT OPS',     sub: 'Programs & Workflows' },
  { to: '/findings',  icon: '⬡', label: 'FINDINGS',     sub: 'Vulnerability Hub' },
  { to: '/intel',     icon: '◎', label: 'INTELLIGENCE', sub: 'Recon & Threat Intel' },
  { to: '/ai',        icon: '✦', label: 'AI ENGINE',    sub: 'Kaison Composer & LLM' },
  { to: '/scans',     icon: '▷', label: 'SCAN OPS',     sub: 'Tools & Execution' },
  { to: '/reports',   icon: '▦', label: 'ANALYTICS',    sub: 'Reports & Payouts' },
  { to: '/settings',  icon: '⚙', label: 'SETTINGS',     sub: 'Platform Config' },
]

export default function Sidebar() {
  const logout = useStore((s) => s.logout)
  const user = useStore((s) => s.auth.user)
  const navigate = useNavigate()
  const [llmModel, setLlmModel] = useState('')
  const [llmReady, setLlmReady] = useState(false)
  const [logo, setLogo] = useState<string>(() => localStorage.getItem('k1_logo_dataurl') || '')

  const P = {
    bg: '#0B0C0D',
    panel: '#111316',
    border: '#4E7A57',
    text: '#8FAF9B',
    muted: '#6F8E7A',
    accent: '#5A2E8A',
    green: '#355E3B',
    orange: '#D97706',
    ink: '#0B0C0D',
  }

  const llmConfig = useStore((s) => s.llmConfig)

  useEffect(() => {
    getLLMConfig()
      .then(r => {
        const cfg = r.data
        const ready = cfg.has_api_key || cfg.provider === 'ollama'
        setLlmModel(cfg.model || cfg.provider || '')
        setLlmReady(ready)
      })
      .catch(() => {
        const cfg = llmConfig
        if (cfg) {
          setLlmModel(cfg.model || cfg.provider || '')
          setLlmReady(!!cfg.has_api_key || !!cfg.api_key || cfg.provider === 'ollama')
        }
      })
  }, [llmConfig])

  useEffect(() => {
    const refresh = () => setLogo(localStorage.getItem('k1_logo_dataurl') || '')
    window.addEventListener('k1-branding', refresh)
    return () => window.removeEventListener('k1-branding', refresh)
  }, [])

  const handleLogout = async () => {
    try { await authLogout() } catch { /* ignore */ }
    logout()
    navigate('/login', { replace: true })
  }

  const linkBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 10,
    padding: '9px 12px', margin: '1px 6px', borderRadius: 5,
    textDecoration: 'none', color: P.text,
    fontFamily: "'JetBrains Mono','Fira Code','Courier New',monospace",
    fontSize: '0.65rem', fontWeight: 700, letterSpacing: '0.08em',
    transition: 'all 0.12s ease', borderLeft: '2px solid transparent',
  }

  return (
    <aside style={{
      width: 192, minWidth: 192, height: '100vh',
      background: P.panel, borderRight: `2px solid ${P.border}`,
      display: 'flex', flexDirection: 'column',
      position: 'fixed', left: 0, top: 0, zIndex: 100,
      fontFamily: "'JetBrains Mono','Fira Code','Courier New',monospace",
    }}>
      {/* Logo */}
      <div style={{ padding: '16px 14px 12px', borderBottom: `2px solid ${P.border}` }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
          {logo ? (
            <img
              src={logo}
              alt="K1 Logo"
              style={{
                width: 30, height: 30, border: `2px solid ${P.border}`, borderRadius: 4,
                objectFit: 'contain', background: P.bg, flexShrink: 0,
              }}
            />
          ) : (
            <div style={{
              width: 30, height: 30, border: `2px solid ${P.green}`, borderRadius: 4,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '0.6rem', fontWeight: 900, color: P.ink, letterSpacing: '-0.02em',
              boxShadow: '0 0 10px rgba(53,94,59,0.25)', flexShrink: 0,
              background: P.green,
            }}>KAI</div>
          )}
          <div>
            <div style={{ color: P.text, fontWeight: 800, fontSize: '0.9rem', letterSpacing: '0.2em' }}>KAI</div>
            <div style={{ color: P.muted, fontSize: '0.49rem', letterSpacing: '0.16em', marginTop: 1 }}>AUTONOMOUS HUNT</div>
          </div>
        </div>
      </div>

      {/* Nav links */}
      <nav style={{ flex: 1, overflowY: 'auto', padding: '8px 0' }}>
        <div style={{ padding: '5px 14px 3px', color: P.muted, fontSize: '0.5rem', fontWeight: 700, letterSpacing: '0.24em' }}>
          NAVIGATION
        </div>
        {NAV.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              ...linkBase,
              color: P.text,
              background: isActive ? 'rgba(53,94,59,0.12)' : 'transparent',
              borderLeft: `2px solid ${isActive ? P.green : 'transparent'}`,
            })}
          >
            <span style={{ fontSize: '0.9rem', width: 18, textAlign: 'center', flexShrink: 0 }}>
              {item.icon}
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ fontSize: '0.62rem', fontWeight: 700, letterSpacing: '0.1em', lineHeight: 1 }}>
                {item.label}
              </span>
              <span style={{ fontSize: '0.51rem', fontWeight: 400, opacity: 0.5, letterSpacing: '0.03em', lineHeight: 1 }}>
                {item.sub}
              </span>
            </span>
          </NavLink>
        ))}
      </nav>

      {/* Bottom */}
      <div style={{ borderTop: `2px solid ${P.border}`, padding: '8px 8px 10px' }}>
        {user && (
          <div style={{ padding: '3px 7px 6px', color: P.text, fontSize: '0.57rem', letterSpacing: '0.06em' }}>
            <div>{user.id}</div>
            <div style={{ color: P.muted, fontSize: '0.51rem', marginTop: 1 }}>
              {user.roles?.[0] ?? 'user'}
            </div>
          </div>
        )}

        {/* AI engine status pill */}
        <div
          onClick={() => !llmReady && navigate('/ai')}
          style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '5px 8px', marginBottom: 5, borderRadius: 4,
            background: P.bg, border: `2px solid ${P.border}`,
            cursor: llmReady ? 'default' : 'pointer',
          }}
        >
          <div style={{
            width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
            background: llmReady ? P.green : P.border,
            boxShadow: llmReady ? '0 0 6px rgba(53,94,59,0.6)' : 'none',
          }} />
          <span style={{
            fontSize: '0.52rem', letterSpacing: '0.07em', flex: 1,
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            color: P.text,
          }}>
            {llmReady ? `AI: ${llmModel}` : 'AI ENGINE: UNCONFIGURED'}
          </span>
          {!llmReady && (
            <span style={{ color: P.orange, fontSize: '0.49rem', flexShrink: 0, letterSpacing: '0.08em' }}>
              SETUP
            </span>
          )}
        </div>

        <button
          onClick={handleLogout}
          style={{
            width: '100%', padding: '6px', background: 'transparent',
            border: `2px solid ${P.border}`, borderRadius: 4, color: P.text,
            fontFamily: 'inherit', fontSize: '0.57rem', cursor: 'pointer',
            letterSpacing: '0.14em', transition: 'all 0.12s',
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = P.accent; e.currentTarget.style.color = P.text }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = P.border; e.currentTarget.style.color = P.text }}
        >
          SIGN OUT
        </button>
      </div>
    </aside>
  )
}
