/**
 * KAISON AI — Platform Intelligence Dashboard
 *
 * Real-time status and data panel for the five intelligence platforms:
 *   Wazuh  — SIEM host monitoring
 *   MISP   — Threat intelligence IOC enrichment
 *   Cortex — Observable analysis engine
 *   TheHive — Security case management
 *   Shuffle — SOAR incident response automation
 */

import React, { useState, useEffect, useCallback } from 'react'
import { COLORS } from '@/theme/branding'

// ─── Types ────────────────────────────────────────────────────────────────────

interface PlatformStatus {
  healthy: boolean
  error: string | null
}

interface PlatformHealth {
  platforms: Record<string, PlatformStatus>
  healthy_count: number
  total: number
  all_healthy: boolean
}

interface WazuhAlert {
  id?: string
  rule?: { description?: string; level?: number }
  agent?: { name?: string }
  timestamp?: string
}

interface WazuhData {
  alerts: WazuhAlert[]
  alert_count: number
  anomaly_summary: {
    anomalies_detected?: boolean
    alert_count?: number
    highest_severity?: number
    summary?: string
  }
  error?: string
}

interface MISPEvent {
  Event?: {
    info?: string
    date?: string
    threat_level_id?: string
    attribute_count?: string
    uuid?: string
  }
}

interface MISPEvents {
  events: MISPEvent[]
  count: number
  error?: string
}

interface CortexAnalyzer {
  id?: string
  name?: string
  version?: string
  dataTypes?: string[]
}

interface CortexData {
  analyzers: CortexAnalyzer[]
  count: number
  error?: string
}

interface TheHiveCase {
  _id?: string
  title?: string
  severity?: number
  status?: string
  createdAt?: number
  tags?: string[]
}

interface TheHiveCases {
  cases: TheHiveCase[]
  count: number
  error?: string
}

interface EnrichResult {
  ioc_type: string
  ioc_value: string
  attribute_hits: number
  event_count: number
  threat_level: number | null
  tags: string[]
  known_malicious: boolean
  error?: string
}

// ─── Constants ────────────────────────────────────────────────────────────────

const PLATFORM_META: Record<string, { label: string; color: string; icon: string; desc: string }> = {
  wazuh:   { label: 'Wazuh',    color: '#e8612c', icon: '🛡', desc: 'SIEM Host Monitoring'       },
  misp:    { label: 'MISP',     color: '#4a90e2', icon: '🔍', desc: 'Threat Intelligence IOCs'   },
  cortex:  { label: 'Cortex',   color: '#9b59b6', icon: '⚗',  desc: 'Observable Analysis'        },
  thehive: { label: 'TheHive',  color: '#f39c12', icon: '🐝', desc: 'Case Management'            },
  shuffle: { label: 'Shuffle',  color: '#2ecc71', icon: '🔀', desc: 'SOAR Automation'            },
}

const SEVERITY_COLORS: Record<string, string> = {
  '1': '#e74c3c',
  '2': '#e74c3c',
  '3': '#e67e22',
  '4': '#f39c12',
}

const REFRESH_INTERVAL = 30_000 // 30s

// ─── Styles ───────────────────────────────────────────────────────────────────

const s = {
  root: {
    padding: '20px',
    background: COLORS.background,
    minHeight: '100vh',
    fontFamily: 'var(--font-mono, monospace)',
    color: COLORS.text,
  } as React.CSSProperties,
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    borderBottom: `1px solid ${COLORS.border}`,
    paddingBottom: 12,
  } as React.CSSProperties,
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: COLORS.primary.main,
    letterSpacing: 1,
  } as React.CSSProperties,
  subtitle: {
    fontSize: 12,
    color: COLORS.textSecondary,
    marginTop: 2,
  } as React.CSSProperties,
  refreshBtn: {
    background: 'transparent',
    border: `1px solid ${COLORS.border}`,
    color: COLORS.primary.main,
    padding: '6px 14px',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    letterSpacing: 1,
  } as React.CSSProperties,
  sectionTitle: {
    fontSize: 12,
    fontWeight: 700,
    color: COLORS.textSecondary,
    letterSpacing: 2,
    textTransform: 'uppercase' as const,
    marginBottom: 12,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
    gap: 12,
    marginBottom: 32,
  } as React.CSSProperties,
  statusCard: (healthy: boolean, color: string) => ({
    background: COLORS.surface,
    border: `1px solid ${healthy ? color : '#e74c3c'}`,
    borderRadius: 8,
    padding: '14px 16px',
    display: 'flex',
    flexDirection: 'column' as const,
    gap: 6,
  }),
  platformIcon: (color: string) => ({
    width: 36,
    height: 36,
    borderRadius: 8,
    background: color + '22',
    border: `1px solid ${color}44`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: 18,
    marginBottom: 6,
  }),
  platformLabel: {
    fontSize: 14,
    fontWeight: 700,
  } as React.CSSProperties,
  platformDesc: {
    fontSize: 11,
    color: COLORS.textSecondary,
  } as React.CSSProperties,
  statusBadge: (healthy: boolean) => ({
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    fontSize: 11,
    color: healthy ? '#2ecc71' : '#e74c3c',
    fontWeight: 600,
  }),
  dot: (healthy: boolean) => ({
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: healthy ? '#2ecc71' : '#e74c3c',
    boxShadow: healthy ? '0 0 6px #2ecc71' : 'none',
  }),
  panel: {
    background: COLORS.surface,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 8,
    padding: 16,
    marginBottom: 20,
  } as React.CSSProperties,
  panelHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  } as React.CSSProperties,
  panelTitle: (color: string) => ({
    fontSize: 13,
    fontWeight: 700,
    color,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  }),
  table: {
    width: '100%',
    borderCollapse: 'collapse' as const,
    fontSize: 12,
  },
  th: {
    textAlign: 'left' as const,
    color: COLORS.textSecondary,
    fontWeight: 600,
    padding: '5px 8px',
    borderBottom: `1px solid ${COLORS.border}`,
    fontSize: 11,
    letterSpacing: 1,
  },
  td: {
    padding: '6px 8px',
    borderBottom: `1px solid ${COLORS.border}22`,
    verticalAlign: 'top' as const,
  },
  chip: (color: string) => ({
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: 3,
    fontSize: 10,
    fontWeight: 700,
    background: color + '22',
    color,
    border: `1px solid ${color}55`,
    letterSpacing: 0.5,
  }),
  anomalyBanner: (detected: boolean) => ({
    background: detected ? '#e74c3c22' : '#2ecc7122',
    border: `1px solid ${detected ? '#e74c3c' : '#2ecc71'}55`,
    borderRadius: 6,
    padding: '8px 12px',
    marginBottom: 12,
    fontSize: 12,
    color: detected ? '#e74c3c' : '#2ecc71',
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  }),
  enrichForm: {
    display: 'flex',
    gap: 8,
    marginBottom: 12,
  } as React.CSSProperties,
  input: {
    flex: 1,
    background: COLORS.elevated,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 4,
    padding: '6px 10px',
    color: COLORS.text,
    fontSize: 12,
    outline: 'none',
  } as React.CSSProperties,
  select: {
    background: COLORS.elevated,
    border: `1px solid ${COLORS.border}`,
    borderRadius: 4,
    padding: '6px 10px',
    color: COLORS.text,
    fontSize: 12,
    outline: 'none',
  } as React.CSSProperties,
  btn: (color: string) => ({
    background: color + '22',
    border: `1px solid ${color}55`,
    color,
    padding: '6px 14px',
    borderRadius: 4,
    cursor: 'pointer',
    fontSize: 12,
    fontWeight: 700,
    letterSpacing: 0.5,
  }),
  empty: {
    color: COLORS.textSecondary,
    fontSize: 12,
    padding: '12px 0',
    textAlign: 'center' as const,
  },
  spinner: {
    color: COLORS.textSecondary,
    fontSize: 12,
    padding: 8,
  } as React.CSSProperties,
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 20,
    marginBottom: 20,
  } as React.CSSProperties,
}

// ─── Component ────────────────────────────────────────────────────────────────

const PlatformIntelligenceDashboard: React.FC = () => {
  const [health, setHealth] = useState<PlatformHealth | null>(null)
  const [wazuh, setWazuh] = useState<WazuhData | null>(null)
  const [mispEvents, setMispEvents] = useState<MISPEvents | null>(null)
  const [cortex, setCortex] = useState<CortexData | null>(null)
  const [hive, setHive] = useState<TheHiveCases | null>(null)
  const [loading, setLoading] = useState(true)
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null)

  // MISP IOC enrichment state
  const [enrichValue, setEnrichValue] = useState('')
  const [enrichType, setEnrichType] = useState('domain')
  const [enrichResult, setEnrichResult] = useState<EnrichResult | null>(null)
  const [enrichLoading, setEnrichLoading] = useState(false)

  const fetchAll = useCallback(async () => {
    try {
      const [healthRes, wazuhRes, mispRes, cortexRes, hiveRes] = await Promise.allSettled([
        fetch('/api/v1/intelligence/platforms/health').then(r => r.json()),
        fetch('/api/v1/intelligence/platforms/wazuh/alerts?hours=1').then(r => r.json()),
        fetch('/api/v1/intelligence/platforms/misp/events?limit=10').then(r => r.json()),
        fetch('/api/v1/intelligence/platforms/cortex/analyzers').then(r => r.json()),
        fetch('/api/v1/intelligence/platforms/thehive/cases?limit=15').then(r => r.json()),
      ])

      if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
      if (wazuhRes.status === 'fulfilled')  setWazuh(wazuhRes.value)
      if (mispRes.status === 'fulfilled')   setMispEvents(mispRes.value)
      if (cortexRes.status === 'fulfilled') setCortex(cortexRes.value)
      if (hiveRes.status === 'fulfilled')   setHive(hiveRes.value)

      setLastRefresh(new Date())
    } catch (err) {
      console.error('Platform intelligence fetch error:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAll()
    const id = setInterval(fetchAll, REFRESH_INTERVAL)
    return () => clearInterval(id)
  }, [fetchAll])

  const runEnrichment = async () => {
    if (!enrichValue.trim()) return
    setEnrichLoading(true)
    setEnrichResult(null)
    try {
      const res = await fetch('/api/v1/intelligence/platforms/misp/enrich', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ioc_type: enrichType, value: enrichValue.trim() }),
      })
      const data = await res.json()
      setEnrichResult(data)
    } catch (err) {
      setEnrichResult({ ioc_type: enrichType, ioc_value: enrichValue, attribute_hits: 0, event_count: 0, threat_level: null, tags: [], known_malicious: false, error: String(err) })
    } finally {
      setEnrichLoading(false)
    }
  }

  // ── Render helpers ──────────────────────────────────────────────────────────

  const renderStatusGrid = () => (
    <div>
      <div style={s.sectionTitle}>Platform Status</div>
      <div style={s.grid}>
        {Object.entries(PLATFORM_META).map(([key, meta]) => {
          const status = health?.platforms?.[key]
          const healthy = status?.healthy ?? false
          return (
            <div key={key} style={s.statusCard(healthy, meta.color)}>
              <div style={s.platformIcon(meta.color)}>{meta.icon}</div>
              <div style={s.platformLabel}>{meta.label}</div>
              <div style={s.platformDesc}>{meta.desc}</div>
              <div style={s.statusBadge(healthy)}>
                <span style={s.dot(healthy)} />
                {healthy ? 'Connected' : (status?.error ? 'Error' : 'Offline')}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )

  const renderWazuh = () => {
    const anomaly = wazuh?.anomaly_summary
    const alerts = wazuh?.alerts ?? []
    const detected = Boolean(anomaly?.anomalies_detected)
    return (
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={s.panelTitle(PLATFORM_META.wazuh.color)}>
            🛡 Wazuh — Host Alerts
          </div>
          <span style={{ fontSize: 11, color: COLORS.textSecondary }}>
            {wazuh?.alert_count ?? 0} alert{(wazuh?.alert_count ?? 0) !== 1 ? 's' : ''} (last hour)
          </span>
        </div>

        {anomaly && (
          <div style={s.anomalyBanner(detected)}>
            {detected ? '⚠' : '✔'}&nbsp;
            {anomaly.summary ?? (detected ? 'Host anomalies detected' : 'No anomalies detected')}
            {anomaly.highest_severity ? ` — max severity level ${anomaly.highest_severity}` : ''}
          </div>
        )}

        {alerts.length === 0 ? (
          <div style={s.empty}>No alerts in the last hour</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Level</th>
                <th style={s.th}>Agent</th>
                <th style={s.th}>Rule</th>
                <th style={s.th}>Time</th>
              </tr>
            </thead>
            <tbody>
              {alerts.slice(0, 10).map((a, i) => (
                <tr key={i}>
                  <td style={s.td}>
                    <span style={s.chip(SEVERITY_COLORS[String(a.rule?.level)] ?? COLORS.textSecondary)}>
                      {a.rule?.level ?? '?'}
                    </span>
                  </td>
                  <td style={s.td}>{a.agent?.name ?? '—'}</td>
                  <td style={s.td}>{a.rule?.description ?? '—'}</td>
                  <td style={s.td}>{a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  const renderMISP = () => {
    const events = mispEvents?.events ?? []
    return (
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={s.panelTitle(PLATFORM_META.misp.color)}>
            🔍 MISP — Threat Events
          </div>
          <span style={{ fontSize: 11, color: COLORS.textSecondary }}>
            {mispEvents?.count ?? 0} recent events
          </span>
        </div>

        {/* IOC Enrichment */}
        <div style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 11, color: COLORS.textSecondary, marginBottom: 6 }}>
            IOC ENRICHMENT
          </div>
          <div style={s.enrichForm}>
            <select
              style={s.select}
              value={enrichType}
              onChange={e => setEnrichType(e.target.value)}
            >
              <option value="domain">Domain</option>
              <option value="ip">IP</option>
              <option value="url">URL</option>
              <option value="hash">Hash</option>
            </select>
            <input
              style={s.input}
              placeholder="Enter IOC value..."
              value={enrichValue}
              onChange={e => setEnrichValue(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && runEnrichment()}
            />
            <button
              style={s.btn(PLATFORM_META.misp.color)}
              onClick={runEnrichment}
              disabled={enrichLoading}
            >
              {enrichLoading ? '...' : 'Enrich'}
            </button>
          </div>
          {enrichResult && (
            <div style={{
              background: enrichResult.known_malicious ? '#e74c3c11' : COLORS.elevated,
              border: `1px solid ${enrichResult.known_malicious ? '#e74c3c55' : COLORS.border}`,
              borderRadius: 4, padding: 10, fontSize: 12,
            }}>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' as const, marginBottom: 6 }}>
                <span style={s.chip(enrichResult.known_malicious ? '#e74c3c' : '#2ecc71')}>
                  {enrichResult.known_malicious ? '⚠ KNOWN MALICIOUS' : '✔ CLEAN'}
                </span>
                <span style={s.chip(COLORS.textSecondary)}>{enrichResult.attribute_hits} hits</span>
                <span style={s.chip(COLORS.textSecondary)}>{enrichResult.event_count} events</span>
                {enrichResult.threat_level && (
                  <span style={s.chip(SEVERITY_COLORS[enrichResult.threat_level] ?? COLORS.textSecondary)}>
                    TL:{enrichResult.threat_level}
                  </span>
                )}
              </div>
              {enrichResult.tags.length > 0 && (
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' as const }}>
                  {enrichResult.tags.slice(0, 8).map((tag, i) => (
                    <span key={i} style={s.chip(PLATFORM_META.misp.color)}>{tag}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Recent events */}
        {events.length === 0 ? (
          <div style={s.empty}>No recent events</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Event</th>
                <th style={s.th}>Threat</th>
                <th style={s.th}>Date</th>
              </tr>
            </thead>
            <tbody>
              {events.slice(0, 8).map((ev, i) => {
                const e = ev.Event ?? ev as any
                const tl = String(e.threat_level_id ?? '')
                return (
                  <tr key={i}>
                    <td style={{ ...s.td, maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                      {e.info ?? '—'}
                    </td>
                    <td style={s.td}>
                      {tl && (
                        <span style={s.chip(SEVERITY_COLORS[tl] ?? COLORS.textSecondary)}>
                          {['', 'HIGH', 'MEDIUM', 'LOW', 'UNDEF'][parseInt(tl)] ?? tl}
                        </span>
                      )}
                    </td>
                    <td style={s.td}>{e.date ?? '—'}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  const renderCortex = () => {
    const analyzers = cortex?.analyzers ?? []
    const byType: Record<string, number> = {}
    analyzers.forEach(a => {
      (a.dataTypes ?? []).forEach(dt => { byType[dt] = (byType[dt] ?? 0) + 1 })
    })
    return (
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={s.panelTitle(PLATFORM_META.cortex.color)}>
            ⚗ Cortex — Analyzers
          </div>
          <span style={{ fontSize: 11, color: COLORS.textSecondary }}>
            {cortex?.count ?? 0} available
          </span>
        </div>

        {cortex?.error ? (
          <div style={s.empty}>{cortex.error}</div>
        ) : analyzers.length === 0 ? (
          <div style={s.empty}>No analyzers available</div>
        ) : (
          <>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' as const, marginBottom: 10 }}>
              {Object.entries(byType).map(([dt, count]) => (
                <span key={dt} style={s.chip(PLATFORM_META.cortex.color)}>
                  {dt}: {count}
                </span>
              ))}
            </div>
            <table style={s.table}>
              <thead>
                <tr>
                  <th style={s.th}>Analyzer</th>
                  <th style={s.th}>Version</th>
                  <th style={s.th}>Types</th>
                </tr>
              </thead>
              <tbody>
                {analyzers.slice(0, 8).map((a, i) => (
                  <tr key={i}>
                    <td style={s.td}>{a.name ?? a.id ?? '—'}</td>
                    <td style={s.td}>{a.version ?? '—'}</td>
                    <td style={s.td}>
                      <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' as const }}>
                        {(a.dataTypes ?? []).map((dt, j) => (
                          <span key={j} style={s.chip(PLATFORM_META.cortex.color)}>{dt}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    )
  }

  const renderTheHive = () => {
    const cases = hive?.cases ?? []
    const sevLabel = (s: number) => ['', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'][s] ?? String(s)
    const sevColor = (s: number) => ['', '#3498db', '#f39c12', '#e67e22', '#e74c3c'][s] ?? COLORS.textSecondary
    return (
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={s.panelTitle(PLATFORM_META.thehive.color)}>
            🐝 TheHive — Cases
          </div>
          <span style={{ fontSize: 11, color: COLORS.textSecondary }}>
            {hive?.count ?? 0} open
          </span>
        </div>

        {cases.length === 0 ? (
          <div style={s.empty}>No cases found</div>
        ) : (
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Title</th>
                <th style={s.th}>Severity</th>
                <th style={s.th}>Status</th>
                <th style={s.th}>Created</th>
              </tr>
            </thead>
            <tbody>
              {cases.slice(0, 10).map((c, i) => (
                <tr key={i}>
                  <td style={{ ...s.td, maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' as const }}>
                    {c.title ?? '—'}
                  </td>
                  <td style={s.td}>
                    <span style={s.chip(sevColor(c.severity ?? 0))}>
                      {sevLabel(c.severity ?? 0)}
                    </span>
                  </td>
                  <td style={s.td}>
                    <span style={s.chip(c.status === 'Open' ? '#2ecc71' : COLORS.textSecondary)}>
                      {c.status ?? '—'}
                    </span>
                  </td>
                  <td style={s.td}>
                    {c.createdAt ? new Date(c.createdAt).toLocaleDateString() : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    )
  }

  const renderShuffle = () => {
    const isHealthy = health?.platforms?.shuffle?.healthy ?? false
    const workflows = [
      { name: 'Critical Finding Escalation', trigger: 'critical_finding',    color: '#e74c3c' },
      { name: 'Mission Complete Debrief',    trigger: 'mission_complete',    color: '#2ecc71' },
      { name: 'Approval Gate Notification',  trigger: 'approval_required',  color: '#f39c12' },
      { name: 'Host Anomaly Response',       trigger: 'host_anomaly',        color: '#e67e22' },
    ]
    return (
      <div style={s.panel}>
        <div style={s.panelHeader}>
          <div style={s.panelTitle(PLATFORM_META.shuffle.color)}>
            🔀 Shuffle — SOAR Workflows
          </div>
          <span style={s.statusBadge(isHealthy)}>
            <span style={s.dot(isHealthy)} />
            {isHealthy ? 'Ready' : 'Offline'}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {workflows.map((wf, i) => (
            <div key={i} style={{
              background: COLORS.elevated,
              border: `1px solid ${wf.color}33`,
              borderLeft: `3px solid ${wf.color}`,
              borderRadius: 4,
              padding: '8px 12px',
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: wf.color, marginBottom: 2 }}>
                {wf.name}
              </div>
              <div style={{ fontSize: 10, color: COLORS.textSecondary }}>
                trigger: <code>{wf.trigger}</code>
              </div>
              <div style={{ marginTop: 4, display: 'flex', gap: 4 }}>
                <span style={s.chip(isHealthy ? wf.color : COLORS.textSecondary)}>
                  {isHealthy ? 'Armed' : 'Standby'}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    )
  }

  // ── Main render ─────────────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ ...s.root, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={s.spinner}>Loading platform intelligence...</div>
      </div>
    )
  }

  const healthyCount = health?.healthy_count ?? 0
  const totalCount   = health?.total ?? 5

  return (
    <div style={s.root}>
      <div style={s.header}>
        <div>
          <div style={s.title}>PLATFORM INTELLIGENCE</div>
          <div style={s.subtitle}>
            {healthyCount}/{totalCount} platforms connected
            {lastRefresh && ` · Last refresh ${lastRefresh.toLocaleTimeString()}`}
          </div>
        </div>
        <button style={s.refreshBtn} onClick={fetchAll}>↺ REFRESH</button>
      </div>

      {renderStatusGrid()}

      <div style={s.twoCol}>
        {renderWazuh()}
        {renderMISP()}
      </div>

      <div style={s.twoCol}>
        {renderCortex()}
        {renderTheHive()}
      </div>

      {renderShuffle()}
    </div>
  )
}

export default PlatformIntelligenceDashboard
