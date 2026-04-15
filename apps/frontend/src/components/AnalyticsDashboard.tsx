/**
 * AnalyticsDashboard — Four-chart analytics view
 *
 * Renders:
 *   • Top programs bar chart (payout by program)
 *   • Vulnerability distribution pie chart
 *   • Monthly trends line chart (findings + payout)
 *   • Playbook ROI rankings table
 *
 * All charts use Recharts (already installed) and adopt the
 * KAISON AI gold/dark color scheme from branding.css.
 * Data refreshes every 60 s and on WebSocket scan-completed events.
 */

import React, { useState, useEffect, useCallback } from 'react';
import {
  BarChart,    Bar,
  LineChart,   Line,
  PieChart,    Pie,    Cell,
  XAxis,       YAxis,
  CartesianGrid,
  Tooltip,     Legend,
  ResponsiveContainer,
  TooltipProps,
} from 'recharts';
import { useWebSocket } from '@/hooks/useWebSocket';

/* ── Palette ────────────────────────────────────────────────────────────── */
const PALETTE = ['#D4AF37', '#ff6b6b', '#51cf66', '#4dabf7', '#ffd43b', '#cc5de8', '#f97316', '#20c997'];

/* ── Types ─────────────────────────────────────────────────────────────── */
interface ProgramMetric {
  name: string;
  payout: number;
  findings: number;
}

interface VulnType {
  type: string;
  count: number;
  payout: number;
}

interface PlaybookRank {
  playbook_id: string;
  name: string;
  findings: number;
  acceptance_rate: number;
  roi: number;
}

interface MonthlyPoint {
  month: string;
  findings: number;
  payout: number;
  acceptance_rate: number;
}

interface AnalyticsData {
  top_programs:               ProgramMetric[];
  vulnerability_distribution: VulnType[];
  playbook_performance:       PlaybookRank[];
  monthly_trends:             MonthlyPoint[];
}

/* ── Shared tooltip style ───────────────────────────────────────────────── */
const CustomTooltip: React.FC<TooltipProps<number, string>> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#111',
      border: '1px solid rgba(212,175,55,0.4)',
      borderRadius: 4,
      padding: '8px 12px',
      fontFamily: 'IBM Plex Mono, monospace',
      fontSize: 11,
    }}>
      {label && <div style={{ color: '#D4AF37', fontWeight: 700, marginBottom: 4 }}>{label}</div>}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color ?? '#e0e0e0', lineHeight: 1.7 }}>
          {p.name}: <span style={{ fontWeight: 700 }}>
            {typeof p.value === 'number' && p.name?.toLowerCase().includes('payout')
              ? `$${p.value.toLocaleString()}`
              : p.value}
          </span>
        </div>
      ))}
    </div>
  );
};

/* ── Section card wrapper ───────────────────────────────────────────────── */
const ChartCard: React.FC<{ title: string; children: React.ReactNode; wide?: boolean }> = ({
  title, children, wide,
}) => (
  <div className={`k1-chart-card${wide ? ' k1-chart-card-wide' : ''}`}>
    <h3 className="k1-chart-title">
      <span aria-hidden="true">◈</span> {title}
    </h3>
    {children}
  </div>
);

/* ── Main Component ─────────────────────────────────────────────────────── */
export const AnalyticsDashboard: React.FC = () => {
  const [data, setData]       = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const loadAnalytics = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/analytics/dashboard-metrics', {
        signal: AbortSignal.timeout(6000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setData(await res.json());
      setLastRefresh(new Date());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load analytics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
    const id = setInterval(loadAnalytics, 60_000);
    return () => clearInterval(id);
  }, [loadAnalytics]);

  /* Refresh on WebSocket events */
  useWebSocket('/ws/scans', useCallback((msg: string) => {
    try {
      const ev = JSON.parse(msg);
      if (ev.type === 'scan_completed') loadAnalytics();
    } catch { /* ignore */ }
  }, [loadAnalytics]));

  /* ── States ─────────────────────────────────────────────────────────── */
  if (loading) {
    return (
      <div className="k1-analytics-loading">
        <span className="k1-loading-icon" aria-hidden="true">◌</span>
        Loading analytics…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="k1-analytics-error">
        <span aria-hidden="true">✕</span>
        {error ?? 'No data available'}
      </div>
    );
  }

  /* ── Sorted playbooks ────────────────────────────────────────────────── */
  const topPlaybooks = [...(data.playbook_performance ?? [])]
    .sort((a, b) => b.roi - a.roi)
    .slice(0, 8);

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="k1-analytics-dashboard" role="region" aria-label="Analytics dashboard">

      {/* Refresh timestamp */}
      <div className="k1-analytics-header">
        <span className="k1-panel-title" style={{ flex: 1 }}>
          <span className="k1-title-icon" aria-hidden="true">◈</span>
          ANALYTICS &amp; ROI METRICS
        </span>
        {lastRefresh && (
          <span className="k1-analytics-refresh">
            Updated: {lastRefresh.toLocaleTimeString()}
          </span>
        )}
        <button
          className="k1-btn-default"
          onClick={loadAnalytics}
          style={{ padding: '4px 10px', fontSize: 10 }}
          aria-label="Refresh analytics data"
        >
          ↺ Refresh
        </button>
      </div>

      <div className="k1-charts-grid">

        {/* ── Top Programs bar chart ───────────────────────────────────── */}
        <ChartCard title="Top Programs by Payout">
          {data.top_programs?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.top_programs} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.1)" vertical={false} />
                <XAxis
                  dataKey="name"
                  tick={{ fill: '#6a6a6a', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(212,175,55,0.2)' }}
                />
                <YAxis
                  tick={{ fill: '#6a6a6a', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="payout" fill="#D4AF37" radius={[3, 3, 0, 0]} name="Payout ($)" />
                <Bar dataKey="findings" fill="#4dabf7" radius={[3, 3, 0, 0]} name="Findings" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="k1-chart-empty">No program data</div>
          )}
        </ChartCard>

        {/* ── Vulnerability distribution pie chart ─────────────────────── */}
        <ChartCard title="Vulnerability Distribution">
          {data.vulnerability_distribution?.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={data.vulnerability_distribution}
                  dataKey="count"
                  nameKey="type"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  innerRadius={35}
                  paddingAngle={2}
                  label={({ type, percent }) =>
                    percent > 0.06 ? `${type} ${(percent * 100).toFixed(0)}%` : ''
                  }
                  labelLine={{ stroke: 'rgba(212,175,55,0.3)', strokeWidth: 0.8 }}
                >
                  {data.vulnerability_distribution.map((_, i) => (
                    <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }) => {
                    if (!active || !payload?.length) return null;
                    const p = payload[0].payload as VulnType;
                    return (
                      <div style={{ background: '#111', border: '1px solid rgba(212,175,55,0.4)', borderRadius: 4, padding: '8px 12px', fontFamily: 'IBM Plex Mono, monospace', fontSize: 11 }}>
                        <div style={{ color: '#D4AF37', fontWeight: 700 }}>{p.type}</div>
                        <div style={{ color: '#e0e0e0' }}>Count: {p.count}</div>
                        <div style={{ color: '#51cf66' }}>Payout: ${p.payout?.toLocaleString()}</div>
                      </div>
                    );
                  }}
                />
                <Legend
                  iconSize={8}
                  iconType="circle"
                  formatter={(value) => (
                    <span style={{ color: '#888', fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' }}>{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="k1-chart-empty">No vulnerability data</div>
          )}
        </ChartCard>

        {/* ── Monthly trends line chart ────────────────────────────────── */}
        <ChartCard title="Monthly Trends — Findings &amp; Payout" wide>
          {data.monthly_trends?.length ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={data.monthly_trends} margin={{ top: 4, right: 20, bottom: 4, left: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(212,175,55,0.08)" vertical={false} />
                <XAxis
                  dataKey="month"
                  tick={{ fill: '#6a6a6a', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                  tickLine={false}
                  axisLine={{ stroke: 'rgba(212,175,55,0.2)' }}
                />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: '#6a6a6a', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: '#6a6a6a', fontSize: 9, fontFamily: 'IBM Plex Mono' }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={v => `$${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  formatter={value => (
                    <span style={{ color: '#888', fontSize: 10, fontFamily: 'IBM Plex Mono, monospace' }}>{value}</span>
                  )}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="findings"
                  stroke="#ff6b6b"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#ff6b6b' }}
                  activeDot={{ r: 4 }}
                  name="Findings"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="payout"
                  stroke="#51cf66"
                  strokeWidth={2}
                  dot={{ r: 2, fill: '#51cf66' }}
                  activeDot={{ r: 4 }}
                  name="Payout ($)"
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="acceptance_rate"
                  stroke="#D4AF37"
                  strokeWidth={1.5}
                  strokeDasharray="4 3"
                  dot={false}
                  name="Acceptance Rate"
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="k1-chart-empty">No trend data</div>
          )}
        </ChartCard>

        {/* ── Playbook ROI table ───────────────────────────────────────── */}
        <ChartCard title="Top Playbooks by ROI" wide>
          {topPlaybooks.length ? (
            <div style={{ overflowX: 'auto' }}>
              <table className="k1-playbook-table" aria-label="Playbook rankings by ROI">
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Playbook</th>
                    <th>Findings</th>
                    <th>Acceptance</th>
                    <th>ROI</th>
                  </tr>
                </thead>
                <tbody>
                  {topPlaybooks.map((pb, idx) => (
                    <tr key={pb.playbook_id}>
                      <td>
                        <span className={`k1-rank-badge rank-${idx + 1}`}>
                          #{idx + 1}
                        </span>
                      </td>
                      <td className="k1-playbook-name">{pb.name}</td>
                      <td className="k1-num-cell">{pb.findings}</td>
                      <td>
                        <span
                          className="k1-acceptance-badge"
                          style={{
                            color: pb.acceptance_rate >= 0.8 ? '#51cf66'
                                 : pb.acceptance_rate >= 0.5 ? '#ffd43b'
                                 : '#ff6b6b',
                          }}
                        >
                          {(pb.acceptance_rate * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td className="k1-roi-cell">
                        ${pb.roi.toLocaleString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="k1-chart-empty">No playbook data</div>
          )}
        </ChartCard>

      </div>
    </div>
  );
};

export default AnalyticsDashboard;
