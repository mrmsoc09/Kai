/**
 * OperationalDashboard — KAISON AI Command Center
 *
 * Full-viewport operational interface optimized for 2560×1080
 * ultrawide (21:9 LG 29WP60G-B).  Three-column layout:
 *   Left   → Active scans & scan control (ScanControlPanel)
 *   Center → Mission overview & selected scan detail (MissionOverviewPanel)
 *   Right  → Real-time log stream (LogStreamViewer)
 *
 * Renders outside the main Layout shell (no sidebar/topbar) so it
 * owns the full viewport — route: /operational
 */
'use client';

import React, { useState, useCallback } from 'react';

import { DashboardHeader }       from '@/components/DashboardHeader';
import { DashboardLayout }       from '@/components/DashboardLayout';
import { MissionOverviewPanel }  from '@/components/MissionOverviewPanel';
import { ScanControlPanel }      from '@/components/ScanControlPanel';
import { LogStreamViewer }       from '@/components/LogStreamViewer';

/* Import new branding/layout styles first, then existing dashboard styles */
import '@/styles/branding.css';
import '@/styles/typography.css';
import '@/styles/responsive.css';
import '@/styles/dashboard.css';  /* keeps existing ScanControlPanel / LogStreamViewer styles */

/* ── State ──────────────────────────────────────────────────────────────── */
interface DashboardState {
  selectedScanId: string | null;
  viewMode: 'split' | 'full' | 'single';
  autoRefresh: boolean;
  activeScansCount: number;
}

/* ── Component ──────────────────────────────────────────────────────────── */
export default function OperationalDashboard() {
  const [state, setState] = useState<DashboardState>({
    selectedScanId:  null,
    viewMode:        'split',
    autoRefresh:     true,
    activeScansCount: 0,
  });

  const handleSelectScan = useCallback((scanId: string) => {
    setState(prev => ({ ...prev, selectedScanId: scanId }));
  }, []);

  const handleAutoRefreshToggle = useCallback(() => {
    setState(prev => ({ ...prev, autoRefresh: !prev.autoRefresh }));
  }, []);

  const handleViewModeChange = useCallback((mode: 'split' | 'full' | 'single') => {
    setState(prev => ({ ...prev, viewMode: mode }));
  }, []);

  /* Right panel: only rendered when a scan is selected or in full-log mode */
  const showLogs = state.selectedScanId !== null;

  return (
    <div className="k1-operational-shell">

      {/* ── BRANDED HEADER ──────────────────────────────────────────── */}
      <DashboardHeader
        autoRefresh={state.autoRefresh}
        onAutoRefreshToggle={handleAutoRefreshToggle}
        viewMode={state.viewMode}
        onViewModeChange={handleViewModeChange}
        activeScansCount={state.activeScansCount}
      />

      {/* ── ULTRAWIDE THREE-COLUMN CONTENT ──────────────────────────── */}
      {state.viewMode !== 'full' && (
        <DashboardLayout
          leftPanel={
            <ScanControlPanel
              selectedScanId={state.selectedScanId}
              onSelectScan={handleSelectScan}
            />
          }
          centerPanel={
            <MissionOverviewPanel
              selectedScanId={state.selectedScanId}
              totalActiveScans={state.activeScansCount}
            />
          }
          rightPanel={
            showLogs ? (
              <LogStreamViewer
                scanId={state.selectedScanId}
                fullScreen={false}
              />
            ) : (
              <div className="k1-no-selection">
                <div className="k1-no-selection-icon" aria-hidden="true">≡</div>
                <p>Select a scan to stream logs</p>
              </div>
            )
          }
        />
      )}

      {/* ── FULL LOG VIEW (viewMode === 'full') ─────────────────────── */}
      {state.viewMode === 'full' && (
        <div
          style={{
            flex: 1,
            padding: '14px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          {state.selectedScanId ? (
            <LogStreamViewer
              scanId={state.selectedScanId}
              fullScreen={true}
            />
          ) : (
            <div className="k1-no-selection" style={{ flex: 1 }}>
              <div className="k1-no-selection-icon" aria-hidden="true">≡</div>
              <p>Select a scan from Control mode to view its logs</p>
            </div>
          )}
        </div>
      )}

      {/* ── FOOTER ──────────────────────────────────────────────────── */}
      <footer className="k1-dashboard-footer" role="contentinfo">
        <span className="k1-footer-item">
          KAISON AI&nbsp;<span className="k1-accent">◆</span>&nbsp;Operational Command
        </span>
        <div className="k1-footer-divider" aria-hidden="true" />
        <span className="k1-footer-item">
          {state.selectedScanId
            ? <>Monitoring: <span className="k1-accent">{state.selectedScanId.slice(0, 8)}…</span></>
            : 'No active target'}
        </span>
        <div className="k1-footer-spacer" />
        <span className="k1-footer-item k1-footer-optional">
          {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
        </span>
      </footer>

    </div>
  );
}
