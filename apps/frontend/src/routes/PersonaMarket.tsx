import React from 'react'

const DEFAULT_PERSONA = {
  role: 'Ethical Hacker',
  description: 'Offensive security generalist with expertise in web, network, and OSINT techniques.',
  traits: ['Aggressive recon', 'MITRE ATT&CK aligned', 'Evidence-first', 'HiL-gated execution'],
  maturity: 'mature',
}

export default function PersonaMarket() {
  return (
    <div style={{ padding: '1.5rem', fontFamily: "'JetBrains Mono', monospace" }}>
      <h1 style={{ color: '#355E3B', fontSize: '1.3rem', fontWeight: 700, marginBottom: 4 }}>Persona Market</h1>
      <div style={{ color: '#6F8E7A', fontSize: '0.75rem', marginBottom: '1.5rem' }}>
        Select an AI hacker persona for your research sessions.
      </div>
      <div style={{
        padding: '1.25rem',
        background: '#0f1117',
        border: '2px solid #355E3B',
        borderRadius: 8,
        marginBottom: '1.5rem',
        maxWidth: 480,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
          <span style={{ color: '#355E3B', fontWeight: 700 }}>{DEFAULT_PERSONA.role}</span>
          <span style={{ padding: '2px 8px', background: '#355E3B22', color: '#355E3B', borderRadius: 3, fontSize: '0.7rem' }}>
            ACTIVE · {DEFAULT_PERSONA.maturity}
          </span>
        </div>
        <p style={{ color: '#8FAF9B', fontSize: '0.8rem', margin: '0 0 12px' }}>{DEFAULT_PERSONA.description}</p>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {DEFAULT_PERSONA.traits.map((t) => (
            <span key={t} style={{ padding: '2px 8px', background: '#1a2030', border: '1px solid #355E3B', borderRadius: 3, color: '#60a5fa', fontSize: '0.7rem' }}>{t}</span>
          ))}
        </div>
      </div>
      <div style={{ color: '#355E3B', fontSize: '0.75rem', padding: '1rem', border: '1px dashed #355E3B', borderRadius: 6, maxWidth: 480 }}>
        Additional persona profiles are planned for a future release.
      </div>
    </div>
  )
}
