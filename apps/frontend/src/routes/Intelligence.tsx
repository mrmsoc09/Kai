import React, { useState } from 'react'
import RSSIntelligenceDashboard from '../components/intelligence/RSSIntelligenceDashboard'
import PlatformIntelligenceDashboard from '../components/intelligence/PlatformIntelligenceDashboard'
import { COLORS } from '@/theme/branding'

const TABS = [
  { id: 'platforms', label: 'Platform Intelligence' },
  { id: 'rss',       label: 'RSS / CVE Feeds'       },
] as const

type Tab = typeof TABS[number]['id']

export default function Intelligence() {
  const [tab, setTab] = useState<Tab>('platforms')

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: `1px solid ${COLORS.border}`,
        background: COLORS.surface,
        padding: '0 20px',
      }}>
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            style={{
              background: 'none',
              border: 'none',
              borderBottom: tab === t.id ? `2px solid ${COLORS.primary.main}` : '2px solid transparent',
              color: tab === t.id ? COLORS.primary.main : COLORS.textSecondary,
              padding: '12px 20px',
              fontSize: 13,
              fontWeight: tab === t.id ? 700 : 400,
              cursor: 'pointer',
              letterSpacing: 0.5,
              transition: 'color 0.15s',
              fontFamily: 'var(--font-mono, monospace)',
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {tab === 'platforms' ? <PlatformIntelligenceDashboard /> : <RSSIntelligenceDashboard />}
      </div>
    </div>
  )
}
