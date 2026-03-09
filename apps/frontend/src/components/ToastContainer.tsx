import React from 'react'
import { useToasts } from '../store/toasts'

const KIND_COLORS: Record<string, string> = {
  success: '#355E3B',
  error: '#D97706',
  warning: '#D97706',
  info: '#60a5fa',
}

export default function ToastContainer() {
  const { toasts, dismiss } = useToasts()
  if (!toasts.length) return null

  return (
    <div style={{
      position: 'fixed',
      bottom: 24,
      right: 24,
      zIndex: 9999,
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
      maxWidth: 360,
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      {toasts.map((t) => (
        <div
          key={t.id}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            padding: '0.75rem 1rem',
            background: '#0f1117',
            border: `1px solid ${KIND_COLORS[t.kind] || '#355E3B'}`,
            borderRadius: 6,
            boxShadow: `0 0 16px ${KIND_COLORS[t.kind]}22`,
            animation: 'fadeIn 0.2s ease',
          }}
        >
          <span style={{ color: KIND_COLORS[t.kind], fontSize: '0.8rem', minWidth: 60, fontWeight: 700 }}>
            {t.kind.toUpperCase()}
          </span>
          <span style={{ color: '#8FAF9B', fontSize: '0.8rem', flex: 1, lineHeight: 1.5 }}>
            {t.message}
          </span>
          <button
            onClick={() => dismiss(t.id)}
            style={{ background: 'none', border: 'none', color: '#6F8E7A', cursor: 'pointer', fontSize: '1rem', lineHeight: 1, padding: 0 }}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}
