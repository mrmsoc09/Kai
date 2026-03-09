/**
 * ThreatHeatmap — Severity × Program findings matrix with glow effects.
 * Fetches real finding data and renders a glowing threat intelligence grid.
 */
import React, { useEffect, useRef, useState } from 'react'
import { listFindings } from '../../lib/api'

interface CellData {
  count: number
  pct: number  // 0-1 normalized within its severity column
}

interface HeatmapData {
  programs: string[]
  severities: string[]
  matrix: Record<string, Record<string, CellData>>  // matrix[program][severity]
  totals: Record<string, number>  // per severity
}

// Severity visual config
const SEV_CONFIG = {
  CRITICAL: { color: '#A12B2B', glow: 'rgba(161,43,43,0.55)',   label: 'CRIT', order: 0 },
  HIGH:     { color: '#D97706', glow: 'rgba(217,119,6,0.5)',  label: 'HIGH', order: 1 },
  MEDIUM:   { color: '#E0A43A', glow: 'rgba(224,164,58,0.45)', label: 'MED',  order: 2 },
  LOW:      { color: '#355E3B', glow: 'rgba(53,94,59,0.4)',    label: 'LOW',  order: 3 },
  INFO:     { color: '#5A2E8A', glow: 'rgba(90,46,138,0.35)',  label: 'INFO', order: 4 },
}

const SEVERITIES = Object.keys(SEV_CONFIG)
const MONO = "'JetBrains Mono','Fira Code','Courier New',monospace"

function buildHeatmap(findings: any[]): HeatmapData {
  const matrix: Record<string, Record<string, number>> = {}
  const progSet = new Set<string>()
  const sevTotals: Record<string, number> = {}

  for (const f of findings) {
    const prog = f.program || 'unknown'
    const sev = (f.severity || 'INFO').toUpperCase()
    if (!SEVERITIES.includes(sev)) continue
    progSet.add(prog)
    if (!matrix[prog]) matrix[prog] = {}
    matrix[prog][sev] = (matrix[prog][sev] || 0) + 1
    sevTotals[sev] = (sevTotals[sev] || 0) + 1
  }

  // Find max per severity column for normalization
  const sevMax: Record<string, number> = {}
  for (const sev of SEVERITIES) {
    sevMax[sev] = 0
    for (const prog of progSet) {
      const count = matrix[prog]?.[sev] || 0
      if (count > sevMax[sev]) sevMax[sev] = count
    }
  }

  const programs = [...progSet].sort()
  const normalized: Record<string, Record<string, CellData>> = {}
  for (const prog of programs) {
    normalized[prog] = {}
    for (const sev of SEVERITIES) {
      const count = matrix[prog]?.[sev] || 0
      normalized[prog][sev] = {
        count,
        pct: sevMax[sev] > 0 ? count / sevMax[sev] : 0,
      }
    }
  }

  return { programs, severities: SEVERITIES, matrix: normalized, totals: sevTotals }
}

interface TooltipState {
  x: number; y: number; program: string; severity: string; count: number
}

export default function ThreatHeatmap({ height = 320 }: { height?: number }) {
  const [data, setData] = useState<HeatmapData | null>(null)
  const [loading, setLoading] = useState(true)
  const [tooltip, setTooltip] = useState<TooltipState | null>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    listFindings({ page_size: 500 })
      .then(r => {
        const findings = r.data?.items ?? r.data ?? []
        setData(buildHeatmap(findings))
      })
      .catch(() => {
        // Demo data if API unavailable
        const demo: any[] = [
          ...Array.from({ length: 4 }, (_, i) => ({ program: 'shopify', severity: 'CRITICAL' })),
          ...Array.from({ length: 12 }, (_, i) => ({ program: 'shopify', severity: 'HIGH' })),
          ...Array.from({ length: 8 }, (_, i) => ({ program: 'shopify', severity: 'MEDIUM' })),
          ...Array.from({ length: 3 }, () => ({ program: 'paypal', severity: 'CRITICAL' })),
          ...Array.from({ length: 7 }, () => ({ program: 'paypal', severity: 'HIGH' })),
          ...Array.from({ length: 15 }, () => ({ program: 'paypal', severity: 'MEDIUM' })),
          ...Array.from({ length: 6 }, () => ({ program: 'paypal', severity: 'LOW' })),
          ...Array.from({ length: 2 }, () => ({ program: 'uber', severity: 'CRITICAL' })),
          ...Array.from({ length: 5 }, () => ({ program: 'uber', severity: 'HIGH' })),
          ...Array.from({ length: 3 }, () => ({ program: 'uber', severity: 'MEDIUM' })),
          ...Array.from({ length: 8 }, () => ({ program: 'uber', severity: 'LOW' })),
          ...Array.from({ length: 4 }, () => ({ program: 'uber', severity: 'INFO' })),
          ...Array.from({ length: 9 }, () => ({ program: 'adobe', severity: 'MEDIUM' })),
          ...Array.from({ length: 14 }, () => ({ program: 'adobe', severity: 'LOW' })),
          ...Array.from({ length: 11 }, () => ({ program: 'adobe', severity: 'INFO' })),
          ...Array.from({ length: 1 }, () => ({ program: 'tesla', severity: 'CRITICAL' })),
          ...Array.from({ length: 4 }, () => ({ program: 'tesla', severity: 'HIGH' })),
          ...Array.from({ length: 7 }, () => ({ program: 'tesla', severity: 'MEDIUM' })),
        ]
        setData(buildHeatmap(demo))
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div style={{
        height, background: '#111316', border: '1px solid #355E3B', borderRadius: 6,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#6F8E7A', fontFamily: MONO, fontSize: '0.7rem', letterSpacing: '0.1em',
      }}>
        ▓▒░ LOADING THREAT MAP…
      </div>
    )
  }

  if (!data || data.programs.length === 0) {
    return (
      <div style={{
        height, background: '#111316', border: '1px solid #355E3B', borderRadius: 6,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: '#6F8E7A', fontFamily: MONO, fontSize: '0.7rem',
      }}>
        NO FINDINGS TO DISPLAY
      </div>
    )
  }

  const cellH = Math.max(28, Math.min(44, Math.floor((height - 80) / data.programs.length)))
  const cellW = 64

  return (
    <div
      ref={containerRef}
      style={{
        background: '#111316', border: '1px solid #355E3B', borderRadius: 6,
        padding: '14px 16px', overflow: 'hidden', position: 'relative',
        fontFamily: MONO,
      }}
      onMouseLeave={() => setTooltip(null)}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ color: '#8FAF9B', fontSize: '0.6rem', fontWeight: 700, letterSpacing: '0.16em' }}>
          THREAT DENSITY MATRIX
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {SEVERITIES.map(sev => (
            <div key={sev} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <div style={{ width: 8, height: 8, background: SEV_CONFIG[sev as keyof typeof SEV_CONFIG].color, borderRadius: 2 }} />
              <span style={{ color: '#6F8E7A', fontSize: '0.55rem' }}>
                {SEV_CONFIG[sev as keyof typeof SEV_CONFIG].label}
                {data.totals[sev] ? ` (${data.totals[sev]})` : ''}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div style={{ overflowX: 'auto', overflowY: 'hidden' }}>
        <div style={{ minWidth: 200 }}>
          {/* Column headers */}
          <div style={{ display: 'flex', marginBottom: 4, paddingLeft: 110 }}>
            {SEVERITIES.map(sev => {
              const cfg = SEV_CONFIG[sev as keyof typeof SEV_CONFIG]
              return (
                <div key={sev} style={{
                  width: cellW, textAlign: 'center', color: cfg.color,
                  fontSize: '0.58rem', fontWeight: 700, letterSpacing: '0.08em',
                }}>
                  {cfg.label}
                </div>
              )
            })}
          </div>

          {/* Grid rows */}
          {data.programs.map(prog => (
            <div key={prog} style={{ display: 'flex', alignItems: 'center', marginBottom: 3 }}>
              {/* Program label */}
              <div style={{
                width: 104, paddingRight: 8, color: '#8FAF9B', fontSize: '0.65rem',
                fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                textAlign: 'right', lineHeight: 1,
              }}>
                {prog}
              </div>

              {/* Cells */}
              {SEVERITIES.map(sev => {
                const cell = data.matrix[prog]?.[sev] ?? { count: 0, pct: 0 }
                const cfg = SEV_CONFIG[sev as keyof typeof SEV_CONFIG]
                const isHot = cell.pct > 0.6
                const alpha = cell.count === 0 ? 0 : Math.max(0.08, cell.pct * 0.85)
                const glowStrength = cell.pct * 12

                return (
                  <div
                    key={sev}
                    onMouseEnter={(e) => {
                      if (cell.count > 0) {
                        const rect = e.currentTarget.getBoundingClientRect()
                        const containerRect = containerRef.current?.getBoundingClientRect() || rect
                        setTooltip({
                          x: rect.left - containerRect.left + rect.width / 2,
                          y: rect.top - containerRect.top - 4,
                          program: prog, severity: sev, count: cell.count,
                        })
                      }
                    }}
                    style={{
                      width: cellW, height: cellH, display: 'flex', alignItems: 'center',
                      justifyContent: 'center', marginRight: 2, borderRadius: 3,
                      background: cell.count === 0
                        ? '#0B0C0D'
                        : `rgba(${hexToRgb(cfg.color)},${alpha})`,
                      border: `1px solid ${cell.count === 0 ? '#24352A' : `rgba(${hexToRgb(cfg.color)},${alpha * 1.5})`}`,
                      boxShadow: isHot ? `0 0 ${glowStrength}px ${cfg.glow}` : 'none',
                      cursor: cell.count > 0 ? 'pointer' : 'default',
                      transition: 'all 0.15s ease',
                      position: 'relative',
                    }}
                  >
                    {cell.count > 0 && (
                      <span style={{
                        color: cell.pct > 0.5 ? '#c7d2e0' : cfg.color,
                        fontSize: '0.68rem', fontWeight: 700,
                        textShadow: isHot ? `0 0 8px ${cfg.glow}` : 'none',
                      }}>
                        {cell.count}
                      </span>
                    )}
                    {/* Hot cell pulse bar at bottom */}
                    {isHot && (
                      <div style={{
                        position: 'absolute', bottom: 0, left: 0, right: 0, height: 2,
                        background: cfg.color, opacity: 0.7, borderRadius: '0 0 3px 3px',
                      }} />
                    )}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Tooltip */}
      {tooltip && (
        <div style={{
          position: 'absolute',
          left: tooltip.x, top: tooltip.y,
          transform: 'translate(-50%, -100%)',
          background: '#111316', border: `1px solid ${SEV_CONFIG[tooltip.severity as keyof typeof SEV_CONFIG].color}40`,
          borderRadius: 5, padding: '6px 10px', pointerEvents: 'none', zIndex: 50,
          boxShadow: `0 0 14px ${SEV_CONFIG[tooltip.severity as keyof typeof SEV_CONFIG].glow}`,
          whiteSpace: 'nowrap',
        }}>
          <div style={{ color: SEV_CONFIG[tooltip.severity as keyof typeof SEV_CONFIG].color, fontSize: '0.65rem', fontWeight: 700 }}>
            {tooltip.count} {tooltip.severity}
          </div>
          <div style={{ color: '#8FAF9B', fontSize: '0.6rem', marginTop: 2 }}>{tooltip.program}</div>
        </div>
      )}
    </div>
  )
}

function hexToRgb(hex: string): string {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return `${r},${g},${b}`
}
