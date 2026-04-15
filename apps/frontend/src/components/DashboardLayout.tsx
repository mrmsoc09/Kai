/**
 * DashboardLayout — Ultrawide Three-Column Grid
 *
 * Optimized for 2560×1080 (21:9 LG 29WP60G-B) with responsive
 * fallbacks down to mobile.  Each panel is an independent scroll
 * zone; responsive.css handles column collapsing at breakpoints.
 *
 * Usage:
 *   <DashboardLayout
 *     leftPanel  = {<ScanControlPanel … />}
 *     centerPanel= {<MissionOverviewPanel … />}
 *     rightPanel = {<LogStreamViewer … />}
 *   />
 */

import React from 'react';

interface DashboardLayoutProps {
  /** Active scans list — occupies the left third */
  leftPanel: React.ReactNode;
  /** Selected scan details / platform metrics — center third */
  centerPanel: React.ReactNode;
  /** Real-time log stream — right third */
  rightPanel: React.ReactNode;
  /** Extra class name on the grid container */
  className?: string;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  leftPanel,
  centerPanel,
  rightPanel,
  className = '',
}) => {
  return (
    <div
      className={`k1-ultrawide-layout${className ? ` ${className}` : ''}`}
      role="main"
      aria-label="Operational dashboard workspace"
    >
      {/* ── LEFT PANEL ── */}
      <div className="k1-panel-left" aria-label="Active scans">
        <div className="k1-panel">
          {leftPanel}
        </div>
      </div>

      {/* ── CENTER PANEL ── */}
      <div className="k1-panel-center" aria-label="Scan details and mission overview">
        <div className="k1-panel">
          {centerPanel}
        </div>
      </div>

      {/* ── RIGHT PANEL ── */}
      <div className="k1-panel-right" aria-label="Real-time log stream">
        <div className="k1-panel">
          {rightPanel}
        </div>
      </div>
    </div>
  );
};

export default DashboardLayout;
