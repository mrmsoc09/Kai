/**
 * DashboardHeader — KAISON AI Branded Header
 *
 * Displays the KAISON AI shield logo, brand name, motto, real-time
 * system status strip, and operational controls across the full
 * 2560px ultrawide header bar. Pins to the top of the viewport.
 */
'use client';

import React, { useState, useEffect, useCallback } from 'react';

/* ── Props ─────────────────────────────────────────────────────────────── */
interface DashboardHeaderProps {
  autoRefresh: boolean;
  onAutoRefreshToggle: () => void;
  viewMode?: 'split' | 'full' | 'single' | 'cockpit';
  onViewModeChange?: (mode: 'split' | 'full' | 'single' | 'cockpit') => void;
  activeScansCount?: number;
}

/* ── Inline SVG Logo (128×128 shield with K1) ──────────────────────────── */
const KaisonShield: React.FC<{ size?: number }> = ({ size = 72 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 128 128"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="KAISON AI Shield Logo"
  >
    {/* Shield fill */}
    <path
      d="M64 6 L112 30 L112 82 Q112 108 64 122 Q16 108 16 82 L16 30 Z"
      fill="#0a0a0a"
    />
    {/* Gold outer border */}
    <path
      d="M64 6 L112 30 L112 82 Q112 108 64 122 Q16 108 16 82 L16 30 Z"
      fill="none"
      stroke="#D4AF37"
      strokeWidth="2.5"
      strokeLinejoin="round"
    />
    {/* Inner accent ring */}
    <path
      d="M64 14 L104 34 L104 80 Q104 100 64 114 Q24 100 24 80 L24 34 Z"
      fill="none"
      stroke="rgba(212,175,55,0.2)"
      strokeWidth="1"
      strokeLinejoin="round"
    />
    {/* Crosshair lines */}
    <line x1="20" y1="64" x2="108" y2="64" stroke="#D4AF37" strokeWidth="0.5" strokeDasharray="4 3" opacity="0.22" />
    <line x1="64" y1="10" x2="64" y2="118" stroke="#D4AF37" strokeWidth="0.5" strokeDasharray="4 3" opacity="0.22" />
    {/* K — vertical + two diagonals */}
    <line x1="36" y1="44" x2="36" y2="84" stroke="#D4AF37" strokeWidth="6" strokeLinecap="round" />
    <line x1="36" y1="64" x2="58" y2="44" stroke="#D4AF37" strokeWidth="6" strokeLinecap="round" />
    <line x1="36" y1="64" x2="58" y2="84" stroke="#D4AF37" strokeWidth="6" strokeLinecap="round" />
    {/* 1 — vertical + flag */}
    <line x1="79" y1="50" x2="79" y2="84" stroke="#D4AF37" strokeWidth="5" strokeLinecap="round" />
    <line x1="73" y1="57" x2="79" y2="50" stroke="#D4AF37" strokeWidth="5" strokeLinecap="round" />
    {/* Corner accent dots */}
    <circle cx="64" cy="6"  r="2.5" fill="#D4AF37" />
    <circle cx="112" cy="30" r="2.5" fill="#D4AF37" />
    <circle cx="16"  cy="30" r="2.5" fill="#D4AF37" />
    {/* Tech corner brackets */}
    <path d="M26 22 L38 22 L38 32" fill="none" stroke="#D4AF37" strokeWidth="1.5" strokeLinecap="round" opacity="0.55" />
    <path d="M90 22 L102 22 L102 32" fill="none" stroke="#D4AF37" strokeWidth="1.5" strokeLinecap="round" opacity="0.55" />
    {/* Bottom accent line */}
    <line x1="44" y1="112" x2="84" y2="112" stroke="#D4AF37" strokeWidth="1" opacity="0.35" />
  </svg>
);

/* ── Component ─────────────────────────────────────────────────────────── */
export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  autoRefresh,
  onAutoRefreshToggle,
  viewMode = 'split',
  onViewModeChange,
  activeScansCount = 0,
}) => {
  const [clock, setClock] = useState<string>('');
  const [systemStatus, setSystemStatus] = useState<'healthy' | 'degraded' | 'unhealthy'>('healthy');

  /* Live clock — updates every second */
  useEffect(() => {
    const tick = () => setClock(new Date().toLocaleTimeString('en-US', { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  /* System health poll — every 30 s */
  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const res = await fetch('/api/v1/system/health', { signal: AbortSignal.timeout(3000) });
        if (res.ok && mounted) {
          const data = await res.json();
          setSystemStatus(data.status ?? 'healthy');
        }
      } catch {
        /* silent — health indicator shows last known state */
      }
    };
    poll();
    const id = setInterval(poll, 30_000);
    return () => { mounted = false; clearInterval(id); };
  }, []);

  /* Derived status color */
  const dotColor =
    systemStatus === 'healthy'   ? '#51cf66' :
    systemStatus === 'degraded'  ? '#ffd43b' :
                                   '#ff6b6b';

  const handleViewMode = useCallback(
    (mode: 'split' | 'full' | 'single' | 'cockpit') => onViewModeChange?.(mode),
    [onViewModeChange]
  );

  return (
    <header className="k1-dashboard-header" role="banner">

      {/* ── LOGO SECTION ────────────────────────────────────────────── */}
      <div className="k1-logo-section">
        <div className="k1-logo-emblem">
          <KaisonShield size={72} />
        </div>
        <div className="k1-brand-text">
          <h1 className="k1-brand-name">KAISON AI</h1>
          <p className="k1-brand-motto">"To plan, To plot, To plunder"</p>
          <p className="k1-brand-subtitle">OPERATIONAL DASHBOARD</p>
        </div>
      </div>

      {/* ── SYSTEM STATUS STRIP ─────────────────────────────────────── */}
      <div className="k1-status-section" role="status" aria-label="System status">

        <div className="k1-status-item">
          <span
            className="k1-status-dot"
            style={{ backgroundColor: dotColor }}
            title={`System: ${systemStatus}`}
          />
          <span className="k1-status-label">
            {systemStatus.toUpperCase()}
          </span>
        </div>

        <div className="k1-status-divider" aria-hidden="true" />

        <div className="k1-status-item">
          <span className={`k1-realtime-badge ${autoRefresh ? 'active' : 'inactive'}`}>
            {autoRefresh ? '⬤ LIVE' : '○ PAUSED'}
          </span>
        </div>

        <div className="k1-status-divider" aria-hidden="true" />

        <div className="k1-status-item">
          <span className="k1-scan-count" aria-label={`${activeScansCount} active scans`}>
            {activeScansCount}
          </span>
          <span className="k1-status-label">
            Active Scan{activeScansCount !== 1 ? 's' : ''}
          </span>
        </div>

        <div className="k1-status-divider k1-status-optional" aria-hidden="true" />

        <div className="k1-status-item k1-status-optional">
          <span className="k1-status-label">{clock}</span>
        </div>

      </div>

      {/* ── CONTROLS ────────────────────────────────────────────────── */}
      <div className="k1-controls-section" role="toolbar" aria-label="Dashboard controls">

        {/* View mode toggle */}
        {onViewModeChange && (
          <div className="k1-view-toggle" role="group" aria-label="View mode">
            <button
              className={`k1-view-btn${viewMode === 'split' ? ' active' : ''}`}
              onClick={() => handleViewMode('split')}
              title="Three-column ultrawide view"
              aria-pressed={viewMode === 'split'}
            >
              ⊞ Ultra
            </button>
            <button
              className={`k1-view-btn${viewMode === 'cockpit' ? ' active' : ''}`}
              onClick={() => handleViewMode('cockpit')}
              title="Tactical Cockpit view"
              aria-pressed={viewMode === 'cockpit'}
            >
              ⌬ Cockpit
            </button>
            <button
              className={`k1-view-btn${viewMode === 'full' ? ' active' : ''}`}
              onClick={() => handleViewMode('full')}
              title="Full-screen logs"
              aria-pressed={viewMode === 'full'}
            >
              ≡ Logs
            </button>
            <button
              className={`k1-view-btn${viewMode === 'single' ? ' active' : ''}`}
              onClick={() => handleViewMode('single')}
              title="Control panel only"
              aria-pressed={viewMode === 'single'}
            >
              ▣ Control
            </button>
          </div>
        )}

        {/* Real-time feed toggle */}
        <button
          className={`k1-btn-secondary${autoRefresh ? ' active' : ''}`}
          onClick={onAutoRefreshToggle}
          aria-pressed={autoRefresh}
          title={autoRefresh ? 'Pause real-time updates' : 'Resume real-time updates'}
        >
          {autoRefresh ? '⏸ Pause Feed' : '▶ Resume Feed'}
        </button>

      </div>
    </header>
  );
};

export default DashboardHeader;
