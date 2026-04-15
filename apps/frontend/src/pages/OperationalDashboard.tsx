/**
 * Operational Dashboard - Real-time Scan Monitoring & Control
 *
 * Main dashboard for monitoring active scans, controlling scan lifecycle,
 * and viewing real-time log streams. Supports multiple simultaneous scans
 * with WebSocket-based real-time updates.
 */
'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { ScanControlPanel } from '@/components/ScanControlPanel';
import { LogStreamViewer } from '@/components/LogStreamViewer';
import { SystemHealthIndicator } from '@/components/SystemHealthIndicator';
import '@/styles/dashboard.css';

interface DashboardState {
  selectedScanId: string | null;
  viewMode: 'split' | 'full' | 'single';
  autoRefresh: boolean;
}

export default function OperationalDashboard() {
  const [state, setState] = useState<DashboardState>({
    selectedScanId: null,
    viewMode: 'split',
    autoRefresh: true,
  });

  const handleSelectScan = useCallback((scanId: string) => {
    setState(prev => ({ ...prev, selectedScanId: scanId }));
  }, []);

  const handleViewModeChange = useCallback((mode: 'split' | 'full' | 'single') => {
    setState(prev => ({ ...prev, viewMode: mode }));
  }, []);

  const handleAutoRefreshToggle = useCallback(() => {
    setState(prev => ({ ...prev, autoRefresh: !prev.autoRefresh }));
  }, []);

  return (
    <div className="operational-dashboard">
      {/* Dashboard Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <h1 className="dashboard-title">KAISON AI - Operational Dashboard</h1>
          <SystemHealthIndicator autoRefresh={state.autoRefresh} />
        </div>
        <div className="header-right">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={state.autoRefresh}
              onChange={handleAutoRefreshToggle}
            />
            <span>Real-time: {state.autoRefresh ? 'ON' : 'OFF'}</span>
          </label>
          <div className="view-mode-selector">
            <button
              className={`view-btn ${state.viewMode === 'split' ? 'active' : ''}`}
              onClick={() => handleViewModeChange('split')}
              title="Split View: Control Panel + Logs"
            >
              Split
            </button>
            <button
              className={`view-btn ${state.viewMode === 'full' ? 'active' : ''}`}
              onClick={() => handleViewModeChange('full')}
              title="Full View: Maximize Log Viewer"
            >
              Logs
            </button>
            <button
              className={`view-btn ${state.viewMode === 'single' ? 'active' : ''}`}
              onClick={() => handleViewModeChange('single')}
              title="Single View: Control Panel Only"
            >
              Control
            </button>
          </div>
        </div>
      </header>

      {/* Main Dashboard Content */}
      <main className="dashboard-content">
        {(state.viewMode === 'split' || state.viewMode === 'single') && (
          <section className="control-section">
            <ScanControlPanel
              selectedScanId={state.selectedScanId}
              onSelectScan={handleSelectScan}
            />
          </section>
        )}

        {(state.viewMode === 'split' || state.viewMode === 'full') && state.selectedScanId && (
          <section className="logs-section">
            <LogStreamViewer
              scanId={state.selectedScanId}
              fullScreen={state.viewMode === 'full'}
            />
          </section>
        )}

        {state.viewMode === 'full' && !state.selectedScanId && (
          <div className="logs-placeholder">
            <p>Select a scan from the control panel to view logs</p>
          </div>
        )}
      </main>

      {/* Footer with Status */}
      <footer className="dashboard-footer">
        <div className="footer-content">
          <span className="status-text">
            {state.selectedScanId ? `Viewing: ${state.selectedScanId}` : 'Ready'}
          </span>
          <span className="timestamp">
            Last update: {new Date().toLocaleTimeString()}
          </span>
        </div>
      </footer>
    </div>
  );
}
