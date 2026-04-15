/**
 * VisualizationPage — Global Heat Map + Analytics Dashboard
 *
 * Tab bar selects between:
 *   • "Global Map"  — D3 world map with opportunity markers
 *   • "Analytics"   — Four-chart ROI analytics dashboard
 *
 * Styles: visualizations.css (gold/dark KAISON AI theme)
 */

import React, { useState } from 'react';
import { GlobalHeatMap }      from '../components/GlobalHeatMap';
import { AnalyticsDashboard } from '../components/AnalyticsDashboard';
import '../styles/visualizations.css';

type Tab = 'map' | 'analytics';

const TABS: { id: Tab; label: string; icon: string }[] = [
  { id: 'map',       label: 'GLOBAL MAP',  icon: '◎' },
  { id: 'analytics', label: 'ANALYTICS',   icon: '◈' },
];

const VisualizationPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('map');

  return (
    <div className="k1-viz-page" role="main" aria-label="Visualization">

      {/* ── Tab bar ────────────────────────────────────────────────── */}
      <div className="k1-viz-tab-bar" role="tablist" aria-label="Visualization views">
        {TABS.map(tab => (
          <button
            key={tab.id}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`k1-viz-panel-${tab.id}`}
            id={`k1-viz-tab-${tab.id}`}
            className={`k1-viz-tab${activeTab === tab.id ? ' active' : ''}`}
            onClick={() => setActiveTab(tab.id)}
          >
            <span aria-hidden="true">{tab.icon}</span>{' '}
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Content panels ─────────────────────────────────────────── */}
      <div className="k1-viz-content">
        <div
          id="k1-viz-panel-map"
          role="tabpanel"
          aria-labelledby="k1-viz-tab-map"
          hidden={activeTab !== 'map'}
          style={{ height: '100%' }}
        >
          {activeTab === 'map' && <GlobalHeatMap />}
        </div>

        <div
          id="k1-viz-panel-analytics"
          role="tabpanel"
          aria-labelledby="k1-viz-tab-analytics"
          hidden={activeTab !== 'analytics'}
          style={{ height: '100%' }}
        >
          {activeTab === 'analytics' && <AnalyticsDashboard />}
        </div>
      </div>

    </div>
  );
};

export default VisualizationPage;
