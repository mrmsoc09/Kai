/**
 * MissionOverviewPanel — Center Column: Scan Detail + Platform Metrics
 *
 * Displays the selected scan's full detail (status, phase, progress,
 * findings breakdown) and a real-time platform health summary at the
 * bottom. Connects to /api/v1/scans/{id} and /api/v1/system/health.
 */
'use client';

import React, { useState, useEffect, useCallback } from 'react';

/* ── Types ─────────────────────────────────────────────────────────────── */
interface ScanDetail {
  id: string;
  target_url: string;
  status: string;
  current_phase: string;
  phase_number: number;
  total_phases: number;
  findings_count: number;
  duration_seconds: number;
  progress_pct: number;
  rate_limit_hits?: number;
  findings_by_type?: Record<string, number>;
  completed_playbooks?: string[];
}

interface PlatformHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  active_scans: number;
  cpu_usage: number;
  memory_usage: number;
  uptime_seconds: number;
}

interface MissionOverviewPanelProps {
  selectedScanId: string | null;
  /** Lifted from ScanControlPanel via parent — used for aggregate counts */
  totalActiveScans?: number;
}

/* ── Helpers ────────────────────────────────────────────────────────────── */
const fmtDuration = (secs: number): string => {
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  if (m < 60) return `${m}m ${s}s`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
};

const statusClass = (status: string): string =>
  status?.toLowerCase().replace(/[^a-z]/g, '') || 'unknown';

/* ── Component ─────────────────────────────────────────────────────────── */
export const MissionOverviewPanel: React.FC<MissionOverviewPanelProps> = ({
  selectedScanId,
  totalActiveScans = 0,
}) => {
  const [scan, setScan] = useState<ScanDetail | null>(null);
  const [health, setHealth] = useState<PlatformHealth | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* Fetch selected scan detail */
  const fetchScan = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/scans/${id}`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setScan(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load scan');
    } finally {
      setLoading(false);
    }
  }, []);

  /* Re-fetch on scan selection; poll every 5 s while running */
  useEffect(() => {
    if (!selectedScanId) { setScan(null); return; }
    fetchScan(selectedScanId);
    const id = setInterval(() => fetchScan(selectedScanId), 5000);
    return () => clearInterval(id);
  }, [selectedScanId, fetchScan]);

  /* System health poll every 10 s */
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const res = await fetch('/api/v1/system/health', {
          signal: AbortSignal.timeout(3000),
        });
        if (res.ok && mounted) setHealth(await res.json());
      } catch { /* silent */ }
    };
    poll();
    const id = setInterval(poll, 10_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  /* Progress helper */
  const progress = Math.min(Math.max(scan?.progress_pct ?? 0, 0), 100);

  return (
    <div className="k1-mission-overview" role="region" aria-label="Mission overview">

      {/* ── PANEL TITLE ─────────────────────────────────────────────── */}
      <h2 className="k1-panel-title">
        <span className="k1-title-icon" aria-hidden="true">◎</span>
        MISSION OVERVIEW
      </h2>

      {/* ── SELECTED SCAN DETAIL ────────────────────────────────────── */}
      {loading && !scan && (
        <div className="k1-no-selection">
          <div className="k1-no-selection-icon" aria-hidden="true">◌</div>
          <p>Loading scan data…</p>
        </div>
      )}

      {error && (
        <div className="k1-no-selection">
          <div className="k1-no-selection-icon" style={{ color: '#ff6b6b' }} aria-hidden="true">✕</div>
          <p style={{ color: '#ff7a7a' }}>{error}</p>
        </div>
      )}

      {!selectedScanId && !loading && (
        <div className="k1-no-selection">
          <div className="k1-no-selection-icon" aria-hidden="true">◎</div>
          <p>Select a scan from the left panel<br />to view details</p>
        </div>
      )}

      {scan && (
        <div className="k1-scan-detail">
          {/* Status + target */}
          <div className="k1-scan-detail-header">
            <span className={`k1-scan-status-badge ${statusClass(scan.status)}`}>
              {scan.status}
            </span>
            <span className="k1-scan-target k1-truncate" title={scan.target_url}>
              {scan.target_url}
            </span>
          </div>

          {/* Phase + progress bar */}
          <div className="k1-scan-progress">
            <div className="k1-progress-label">
              <span>
                Phase {scan.phase_number ?? '—'}/{scan.total_phases ?? '—'}
                {scan.current_phase ? ` · ${scan.current_phase}` : ''}
              </span>
              <span>{Math.round(progress)}%</span>
            </div>
            <div className="k1-progress-bar" role="progressbar" aria-valuenow={progress} aria-valuemin={0} aria-valuemax={100}>
              <div className="k1-progress-fill" style={{ width: `${progress}%` }} />
            </div>
          </div>

          {/* Key stats */}
          <div className="k1-scan-stats-grid">
            <div className="k1-stat-card">
              <span className="k1-stat-value">{scan.findings_count ?? 0}</span>
              <span className="k1-stat-label">Findings</span>
            </div>
            <div className="k1-stat-card">
              <span className="k1-stat-value">{fmtDuration(scan.duration_seconds ?? 0)}</span>
              <span className="k1-stat-label">Duration</span>
            </div>
            <div className="k1-stat-card">
              <span className="k1-stat-value">{scan.rate_limit_hits ?? 0}</span>
              <span className="k1-stat-label">Rate Limits</span>
            </div>
          </div>

          {/* Findings by type */}
          {scan.findings_by_type && Object.keys(scan.findings_by_type).length > 0 && (
            <div className="k1-metrics-section" style={{ marginTop: 12 }}>
              <p className="k1-section-title">FINDINGS BY TYPE</p>
              <div className="k1-metrics-grid">
                {Object.entries(scan.findings_by_type).slice(0, 6).map(([type, count]) => (
                  <div key={type} className="k1-metric-item">
                    <span className="k1-metric-label">{type}</span>
                    <span className="k1-metric-value k1-value-gold">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Completed playbooks */}
          {scan.completed_playbooks && scan.completed_playbooks.length > 0 && (
            <div className="k1-metrics-section" style={{ marginTop: 8 }}>
              <p className="k1-section-title">COMPLETED PLAYBOOKS</p>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                {scan.completed_playbooks.slice(0, 5).map((pb) => (
                  <div key={pb} className="k1-status-bar-item">
                    <span className="k1-status-dot-sm active" />
                    <span>{pb}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── PLATFORM METRICS ────────────────────────────────────────── */}
      <div className="k1-metrics-section">
        <p className="k1-section-title">PLATFORM METRICS</p>
        <div className="k1-metrics-grid">
          <div className="k1-metric-item">
            <span className="k1-metric-label">Active Scans</span>
            <span className="k1-metric-value k1-value-gold">{totalActiveScans}</span>
          </div>
          <div className="k1-metric-item">
            <span className="k1-metric-label">CPU</span>
            <span
              className={`k1-metric-value ${
                (health?.cpu_usage ?? 0) > 80 ? 'k1-value-danger' :
                (health?.cpu_usage ?? 0) > 60 ? 'k1-value-warning' : ''
              }`}
            >
              {health ? `${health.cpu_usage.toFixed(0)}%` : '—'}
            </span>
          </div>
          <div className="k1-metric-item">
            <span className="k1-metric-label">Memory</span>
            <span
              className={`k1-metric-value ${
                (health?.memory_usage ?? 0) > 85 ? 'k1-value-danger' :
                (health?.memory_usage ?? 0) > 70 ? 'k1-value-warning' : ''
              }`}
            >
              {health ? `${health.memory_usage.toFixed(0)}%` : '—'}
            </span>
          </div>
          <div className="k1-metric-item">
            <span className="k1-metric-label">Uptime</span>
            <span className="k1-metric-value">
              {health ? fmtDuration(health.uptime_seconds) : '—'}
            </span>
          </div>
        </div>
      </div>

      {/* ── GOVERNANCE STATUS BAR ───────────────────────────────────── */}
      <div className="k1-mission-status-bar" role="complementary" aria-label="Governance status">
        <div className="k1-status-bar-item">
          <span className="k1-status-dot-sm active" aria-hidden="true" />
          <span>Scope Guard: ENABLED</span>
        </div>
        <div className="k1-status-bar-item">
          <span className="k1-status-dot-sm active" aria-hidden="true" />
          <span>FP Detection: ACTIVE</span>
        </div>
        <div className="k1-status-bar-item">
          <span className="k1-status-dot-sm active" aria-hidden="true" />
          <span>
            System:{' '}
            <span style={{ color: health?.status === 'healthy' ? '#51cf66' : health?.status === 'degraded' ? '#ffd43b' : '#ff6b6b' }}>
              {health?.status?.toUpperCase() ?? 'UNKNOWN'}
            </span>
          </span>
        </div>
      </div>

    </div>
  );
};

export default MissionOverviewPanel;
