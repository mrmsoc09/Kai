/**
 * Kaison K1 Dashboard
 * Main entry point for unified OSINT/Vulnerability scanning platform
 * Integrates tools, programs, and Kai security guardrails
 */

import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { COLORS, UI, COMPONENT_STYLES, BRANDING, ICONS } from '@/theme/branding';
import { BudgetStatusIndicator } from './budget/BudgetStatusIndicator';
import { BudgetDashboard } from './budget/BudgetDashboard';
import { useAgentStream, AgentEvent } from '../hooks/useAgentStream';

interface ToolSummary {
  id: string;
  name: string;
  category: string;
  last_used?: string;
  use_count: number;
}

interface ProgramSummary {
  id: string;
  name: string;
  platform: string;
  max_payout: number;
  active: boolean;
}

interface AuthorizationStatus {
  total: number;
  active: number;
  expired: number;
}

interface SystemStats {
  tools_deployed: number;
  programs_available: number;
  recent_scans: number;
  authorizations_active: number;
}

const Dashboard: React.FC = () => {
  const navigate = useNavigate();
  const { events: agentEvents, connected: wsConnected } = useAgentStream('');

  // State management
  const [systemStats, setSystemStats] = useState<SystemStats>({
    tools_deployed: 0,
    programs_available: 0,
    recent_scans: 0,
    authorizations_active: 0,
  });

  const [tools, setTools] = useState<ToolSummary[]>([]);
  const [programs, setPrograms] = useState<ProgramSummary[]>([]);
  const [authStatus, setAuthStatus] = useState<AuthorizationStatus>({
    total: 0,
    active: 0,
    expired: 0,
  });

  const [pendingApprovals, setPendingApprovals] = useState(0);
  const [platformHealthy, setPlatformHealthy] = useState(true);
  const [activeMissions, setActiveMissions] = useState(0);

  const [activeTab, setActiveTab] = useState<'overview' | 'tools' | 'programs' | 'security'>('overview');
  const [loading, setLoading] = useState(true);

  // Fetch system data on mount
  useEffect(() => {
    fetchDashboardData();
    const interval = setInterval(fetchDashboardData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchDashboardData = async () => {
    try {
      // Fetch tools
      const toolsRes = await fetch('/api/v1/tools', { credentials: 'include' });
      const toolsData = await toolsRes.json();

      // Fetch programs
      const programsRes = await fetch('/api/v1/programs', { credentials: 'include' });
      const programsData = await programsRes.json();

      // Fetch Kai authorizations
      const authRes = await fetch('/api/v1/kai/authorizations', { credentials: 'include' });
      const authData = await authRes.json();

      // Update state
      if (toolsData.success) {
        setTools(toolsData.data.tools || []);
      }

      if (programsData.success) {
        setPrograms(programsData.data.programs || []);
      }

      if (authData.success) {
        const auths = authData.data.authorizations || [];
        setAuthStatus({
          total: auths.length,
          active: auths.filter((a: any) => new Date(a.expires_at) > new Date()).length,
          expired: auths.filter((a: any) => new Date(a.expires_at) <= new Date()).length,
        });
      }

      // Update system stats
      setSystemStats({
        tools_deployed: toolsData.data?.count || 0,
        programs_available: programsData.data?.total || 0,
        recent_scans: 0,
        authorizations_active: authStatus.active,
      });

      // Set platform and approval counts (mock for now, would come from API)
      setPlatformHealthy(true);
      setPendingApprovals(0);
      setActiveMissions(0);

      setLoading(false);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
      setLoading(false);
    }
  };

  // Render loading state
  if (loading) {
    return (
      <div className="dashboard-loading">
        <div className="spinner">{ICONS.loading}</div>
        <p>Loading Kaison K1...</p>
      </div>
    );
  }

  return (
    <div className="dashboard" style={{ '--primary-color': COLORS.primary.main } as React.CSSProperties}>
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-brand">
          <h1>{BRANDING.name}</h1>
          <p className="tagline">{BRANDING.tagline}</p>
        </div>
        <div className="header-status">
          <div style={{ marginRight: '1rem' }}>
            <BudgetStatusIndicator />
          </div>
          <div className="status-indicator">
            <span className="indicator-dot"></span>
            System Healthy
          </div>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="dashboard-nav">
        <button
          className={`nav-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          {ICONS.info} Overview
        </button>
        <button
          className={`nav-tab ${activeTab === 'tools' ? 'active' : ''}`}
          onClick={() => setActiveTab('tools')}
        >
          {ICONS.tool} Tools ({systemStats.tools_deployed})
        </button>
        <button
          className={`nav-tab ${activeTab === 'programs' ? 'active' : ''}`}
          onClick={() => setActiveTab('programs')}
        >
          {ICONS.network} Programs ({systemStats.programs_available})
        </button>
        <button
          className={`nav-tab ${activeTab === 'security' ? 'active' : ''}`}
          onClick={() => setActiveTab('security')}
        >
          {ICONS.shield} Security
        </button>
      </nav>

      {/* Main Content */}
      <main className="dashboard-main">
        {activeTab === 'overview' && <OverviewSection stats={systemStats} authStatus={authStatus} />}
        {activeTab === 'tools' && <ToolsSection tools={tools} />}
        {activeTab === 'programs' && <ProgramsSection programs={programs} />}
        {activeTab === 'security' && <SecuritySection authStatus={authStatus} />}
      </main>
    </div>
  );
};

/**
 * Overview Section - High-level system status
 */
const OverviewSection: React.FC<{ stats: SystemStats; authStatus: AuthorizationStatus }> = ({
  stats,
  authStatus,
}) => {
  const navigate = useNavigate();

  return (
    <div className="overview-section">
      <h2>System Overview</h2>

      {/* Mission Readiness Summary */}
      <div className="mission-readiness" style={{
        background: '#1a1a1a',
        border: '1px solid #333',
        borderRadius: 8,
        padding: '16px',
        marginBottom: '24px'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '16px'
        }}>
          <h3 style={{ margin: 0, color: '#fff', fontSize: '1rem' }}>Mission Readiness</h3>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 8px',
            borderRadius: '4px',
            background: '#4caf50',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 'bold'
          }}>
            ● READY TO HUNT
          </span>
        </div>

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
          gap: '12px',
          marginBottom: '16px'
        }}>
          <div style={{ padding: '8px', background: '#0a0a0a', borderRadius: '4px' }}>
            <div style={{ color: '#888', fontSize: '0.7rem', marginBottom: '4px' }}>Platform Status</div>
            <div style={{ color: '#4caf50', fontWeight: 'bold' }}>Healthy</div>
          </div>
          <div style={{ padding: '8px', background: '#0a0a0a', borderRadius: '4px' }}>
            <div style={{ color: '#888', fontSize: '0.7rem', marginBottom: '4px' }}>Active Missions</div>
            <div style={{ color: '#2196f3', fontWeight: 'bold' }}>0</div>
          </div>
          <div style={{ padding: '8px', background: '#0a0a0a', borderRadius: '4px' }}>
            <div style={{ color: '#888', fontSize: '0.7rem', marginBottom: '4px' }}>Pending Approvals</div>
            <div style={{ color: '#ff9800', fontWeight: 'bold' }}>0</div>
          </div>
          <div style={{ padding: '8px', background: '#0a0a0a', borderRadius: '4px' }}>
            <div style={{ color: '#888', fontSize: '0.7rem', marginBottom: '4px' }}>API Budget</div>
            <div style={{ color: '#4caf50', fontWeight: 'bold' }}>75%</div>
          </div>
        </div>

        {/* Quick Actions */}
        <div style={{
          display: 'flex',
          gap: '8px',
          flexWrap: 'wrap'
        }}>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/hunt')}
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            {ICONS.shield} Start New Mission
          </button>
          <button
            className="btn btn-primary"
            onClick={() => navigate('/operations/approvals')}
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            {ICONS.tool} View Approvals (0)
          </button>
          <button
            className="btn btn-secondary"
            onClick={() => navigate('/console')}
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            {ICONS.info} Command Console
          </button>
          <button
            className="btn btn-outline"
            onClick={() => navigate('/master-findings')}
            style={{ fontSize: '0.8rem', padding: '6px 12px' }}
          >
            {ICONS.database} Master Findings
          </button>
        </div>
      </div>

    {/* Quick Stats Grid */}
    <div className="stats-grid">
      <div className="stat-card">
        <div className="stat-icon" style={{ color: COLORS.primary.main }}>
          {ICONS.tool}
        </div>
        <div className="stat-content">
          <h3>{stats.tools_deployed}</h3>
          <p>Tools Deployed</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon" style={{ color: COLORS.secondary.main }}>
          {ICONS.network}
        </div>
        <div className="stat-content">
          <h3>{stats.programs_available}</h3>
          <p>Programs Available</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon" style={{ color: COLORS.status.success }}>
          {ICONS.shield}
        </div>
        <div className="stat-content">
          <h3>{authStatus.active}</h3>
          <p>Active Authorizations</p>
        </div>
      </div>

      <div className="stat-card">
        <div className="stat-icon" style={{ color: COLORS.status.info }}>
          {ICONS.database}
        </div>
        <div className="stat-content">
          <h3>{stats.recent_scans}</h3>
          <p>Recent Scans</p>
        </div>
      </div>
    </div>

    {/* Quick Actions */}
    <div className="quick-actions">
      <h3>Quick Actions</h3>
      <button className="btn btn-primary">
        {ICONS.shield} Create Authorization
      </button>
      <button className="btn btn-primary">
        {ICONS.tool} Run Tool
      </button>
      <button className="btn btn-secondary">
        {ICONS.network} Scrape Programs
      </button>
      <button className="btn btn-outline">
        {ICONS.gear} Settings
      </button>
    </div>

    {/* System Information */}
    <div className="system-info">
      <h3>System Information</h3>
      <table>
        <tbody>
          <tr>
            <td>Platform</td>
            <td>Kaison K1 v{BRANDING.version}</td>
          </tr>
          <tr>
            <td>Phase</td>
            <td>{BRANDING.phase}</td>
          </tr>
          <tr>
            <td>Status</td>
            <td>
              <span className="badge" style={{ backgroundColor: COLORS.status.success }}>
                {ICONS.success} Production Ready
              </span>
            </td>
          </tr>
          <tr>
            <td>Last Updated</td>
            <td>{new Date().toLocaleDateString()}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
  );
};

/**
 * Tools Section - Manage and execute tools
 */
const ToolsSection: React.FC<{ tools: ToolSummary[] }> = ({ tools }) => {
  const [localTools, setLocalTools] = useState<ToolSummary[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('k1_local_tools') || '[]')
    } catch {
      return []
    }
  })
  const [name, setName] = useState('')
  const [category, setCategory] = useState('')

  const allTools = [...localTools, ...tools]

  const addTool = () => {
    if (!name.trim()) return
    const newTool: ToolSummary = {
      id: `local-${Date.now()}`,
      name: name.trim(),
      category: category.trim() || 'custom',
      use_count: 0,
    }
    const next = [newTool, ...localTools]
    setLocalTools(next)
    localStorage.setItem('k1_local_tools', JSON.stringify(next))
    setName('')
    setCategory('')
  }

  return (
    <div className="tools-section">
      <h2>Available Tools</h2>

      <div className="tool-details" style={{ marginBottom: 16 }}>
        <h3>Add Tool</h3>
        <p>Add a local placeholder tool while the backend registry loads. This does not execute anything.</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 8 }}>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Tool name"
            style={{ flex: '1 1 180px', padding: '6px 8px', background: 'var(--color-neutral-gray-50)', color: 'var(--color-neutral-gray-900)', border: '1px solid var(--color-neutral-gray-300)', borderRadius: 6 }}
          />
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="Category"
            style={{ flex: '1 1 140px', padding: '6px 8px', background: 'var(--color-neutral-gray-50)', color: 'var(--color-neutral-gray-900)', border: '1px solid var(--color-neutral-gray-300)', borderRadius: 6 }}
          />
          <button className="btn btn-small btn-secondary" onClick={addTool}>Add Tool</button>
        </div>
      </div>

      {/* Tool Categories */}
      <div className="tools-grid">
        {allTools.length === 0 ? (
          <div className="empty-state">
            <p>No tools available. Initialize the backend registry or add a local tool above.</p>
          </div>
        ) : (
          allTools.map((tool) => (
            <div key={tool.id} className="tool-card">
              <div className="tool-header">
                <h3>{tool.name}</h3>
                <span className="tool-category">{tool.category}</span>
              </div>
              <div className="tool-stats">
                <p>Used {tool.use_count} times</p>
                {tool.last_used && <p>Last used: {tool.last_used}</p>}
              </div>
              <button className="btn btn-small btn-primary">Execute</button>
            </div>
          ))
        )}
      </div>

      {/* Tool Details */}
      <div className="tool-details">
        <h3>Tool Information</h3>
        <p>
          Click on any tool to execute it. Tools are categorized by function:
          validation, analysis, reporting, and orchestration.
        </p>
      </div>
    </div>
  )
};

/**
 * Programs Section - Manage bug bounty programs
 */
const ProgramsSection: React.FC<{ programs: ProgramSummary[] }> = ({ programs }) => (
  <div className="programs-section">
    <h2>Bug Bounty Programs</h2>

    {/* Action Buttons */}
    <div className="programs-actions">
      <button className="btn btn-primary">Scrape New Programs</button>
      <button className="btn btn-outline">Filter</button>
    </div>

    {/* Programs List */}
    <div className="programs-grid">
      {programs.length === 0 ? (
        <div className="empty-state">
          <p>No programs loaded. Click "Scrape Programs" to load available programs.</p>
        </div>
      ) : (
        programs.map((prog) => (
          <div key={prog.id} className="program-card">
            <div className="program-header">
              <h3>{prog.name}</h3>
              <span className="platform-badge">{prog.platform}</span>
            </div>
            <div className="program-payout">
              <p className="payout-amount">${prog.max_payout.toLocaleString()}</p>
              <p className="payout-label">Max Payout</p>
            </div>
            <button className="btn btn-small btn-primary">Target Program</button>
          </div>
        ))
      )}
    </div>
  </div>
);

/**
 * Security Section - Kai authorization and audit
 */
const SecuritySection: React.FC<{ authStatus: AuthorizationStatus }> = ({ authStatus }) => (
  <div className="security-section">
    <h2>Security & Compliance</h2>

    {/* Authorization Status */}
    <div className="auth-status">
      <h3>Authorization Status</h3>
      <div className="status-breakdown">
        <div className="status-item">
          <span className="status-label">Total Authorizations</span>
          <span className="status-value">{authStatus.total}</span>
        </div>
        <div className="status-item">
          <span className="status-label">Active</span>
          <span className="status-value" style={{ color: COLORS.status.success }}>
            {authStatus.active}
          </span>
        </div>
        <div className="status-item">
          <span className="status-label">Expired</span>
          <span className="status-value" style={{ color: COLORS.status.error }}>
            {authStatus.expired}
          </span>
        </div>
      </div>
    </div>

    {/* Audit & Compliance */}
    <div className="audit-section">
      <h3>Audit & Compliance</h3>
      <div className="audit-actions">
        <button className="btn btn-outline">View Audit Logs</button>
        <button className="btn btn-outline">Security Alerts</button>
        <button className="btn btn-outline">Compliance Report</button>
      </div>
    </div>

    {/* Security Features */}
    <div className="security-features">
      <h3>Security Features</h3>
      <ul>
        <li>{ICONS.success} Authorization certificate validation</li>
        <li>{ICONS.success} Complete immutable audit trail</li>
        <li>{ICONS.success} Rate limiting protection</li>
        <li>{ICONS.success} Anomaly detection</li>
        <li>{ICONS.success} KMS encryption</li>
        <li>{ICONS.success} Compliance reporting (SOC2, GDPR, HIPAA)</li>
      </ul>
    </div>
  </div>
);



export default Dashboard;
