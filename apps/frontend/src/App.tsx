import React, { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './theme.css'
import './theme/branding.css'

// Auth
import Login from './routes/Login'
import PrivateRoute from './components/PrivateRoute'

// Main Dashboard Component
import Dashboard from './components/Dashboard'

// Route Components
import Programs from './routes/Programs'
import Plans from './routes/Plans'
import Recordings from './routes/Recordings'
import ReportBuilder from './routes/ReportBuilder'
import Chains from './routes/Chains'
import Recon from './routes/Recon'
import AttackGraph from './routes/AttackGraph'
import Docs from './routes/Docs'
import Wizard from './routes/Wizard'
import Operations from './routes/Operations'
import Arsenal from './routes/Arsenal'
import Intelligence from './routes/Intelligence'
import MCPRegistry from './routes/MCPRegistry'
import PersonaMarket from './routes/PersonaMarket'
import Logs from './routes/Logs'
import Settings from './routes/Settings'
import Validation from './routes/Validation'
import KPI from './routes/KPI'

// Pages
import Planner from './pages/Planner'
import Outbox from './pages/Outbox'
import HiLReview from './pages/HiLReview'
import ApprovalsDashboard from './pages/ApprovalsDashboard'
import OperationalDashboard from './pages/OperationalDashboard'
import VisualizationPage from './pages/VisualizationPage'

// Layout
import Layout from './components/Layout'

// Finding Management (Phase 2)
import Findings from './routes/Findings'
import FindingDetail from './routes/FindingDetail'

// Scope Management (Phase 3)
import Scopes from './routes/Scopes'

// Opportunity Hub + Workflow (Phase 6)
import Opportunities from './routes/Opportunities'
import WorkflowDashboard from './routes/WorkflowDashboard'

// Phase 7 — Consolidated 8-page nav
import HuntOps from './routes/HuntOps'
import AIEngine from './routes/AIEngine'
import ScanOps from './routes/ScanOps'
import ScanPoolDashboard from './routes/ScanPoolDashboard'

// Wave 6D Frontend — Tool and Crew Agents
import ToolAgentDashboard from './components/ToolAgentDashboard'
import CrewAgentMonitor from './components/CrewAgentMonitor'
import OrchestratorPanel from './components/OrchestratorPanel'
import MasterFindingsView from './components/MasterFindingsView'
import CommandConsole from './components/CommandConsole'
import LLMProviderDashboard from './components/LLMProviderDashboard'
import ToolRegistryBrowser from './components/ToolRegistryBrowser'
import CrewYAMLBrowser from './components/CrewYAMLBrowser'
import PlatformStatus from './components/PlatformStatus'

function NotFound() {
  return (
    <div style={{ padding: '3rem', textAlign: 'center', fontFamily: 'monospace' }}>
      <div style={{ color: '#355E3B', fontSize: '3rem', fontWeight: 700 }}>404</div>
      <div style={{ color: '#6F8E7A', marginTop: 8 }}>Page not found</div>
      <a href='/dashboard' style={{ color: '#355E3B', marginTop: 16, display: 'inline-block' }}>← Back to Dashboard</a>
    </div>
  )
}

export default function App() {
  useEffect(() => {
    const applyIcon = () => {
      const icon = localStorage.getItem('k1_icon_dataurl')
      const link = document.querySelector<HTMLLinkElement>('#app-favicon')
      if (icon && link) {
        link.href = icon
      }
    }
    applyIcon()
    window.addEventListener('k1-branding', applyIcon)
    return () => window.removeEventListener('k1-branding', applyIcon)
  }, [])

  return (
    <BrowserRouter>
      <Routes>
        {/* Public: Login (no sidebar) */}
        <Route path='/login' element={<Login />} />

        {/* Operational Command Center — full-viewport, no Layout chrome */}
        <Route path='/operational' element={
          <PrivateRoute>
            <OperationalDashboard />
          </PrivateRoute>
        } />

        {/* All authenticated routes inside PrivateRoute + Layout */}
        <Route path='/*' element={
          <PrivateRoute>
            <Layout>
              <Routes>
                <Route path='/' element={<Navigate to='/dashboard' replace />} />
                <Route path='/dashboard' element={<Dashboard />} />

                {/* Core Operations */}
                <Route path='/operations' element={<Operations />} />
                <Route path='/operations/hil-review' element={<HiLReview />} />
                <Route path='/operations/approvals' element={<ApprovalsDashboard />} />
                <Route path='/operations/outbox' element={<Outbox />} />
                <Route path='/operations/logs' element={<Logs />} />

                {/* Finding Management */}
                <Route path='/findings' element={<Findings />} />
                <Route path='/findings/:id' element={<FindingDetail />} />

                {/* Scope Management */}
                <Route path='/scopes' element={<Scopes />} />

                {/* Reconnaissance & Analysis */}
                <Route path='/recon' element={<Recon />} />
                <Route path='/attack-graph' element={<AttackGraph />} />
                <Route path='/chains' element={<Chains />} />

                {/* Tools & Execution */}
                <Route path='/arsenal' element={<Arsenal />} />
                <Route path='/validation' element={<Validation />} />
                <Route path='/intelligence' element={<Intelligence />} />
                <Route path='/kpi' element={<KPI />} />
                {/* Reporting & Planning */}
                <Route path='/report-builder' element={<ReportBuilder />} />
                <Route path='/plans' element={<Plans />} />
                <Route path='/recordings' element={<Recordings />} />

                {/* Consolidated 8-page nav (Phase 7) */}
                <Route path='/hunt' element={<HuntOps />} />
                <Route path='/ai' element={<AIEngine />} />
                <Route path='/scans' element={<ScanOps />} />
                <Route path='/scan-pool' element={<ScanPoolDashboard />} />
                <Route path='/intel' element={<Intelligence />} />
                <Route path='/reports' element={<KPI />} />

                {/* Wave 6D Frontend — Tool and Crew Agents */}
                <Route path='/agents' element={<ToolAgentDashboard />} />
                <Route path='/crew' element={<CrewAgentMonitor />} />
                <Route path='/orchestrator' element={<OrchestratorPanel />} />
                <Route path='/master-findings' element={<MasterFindingsView />} />
                <Route path='/console' element={<CommandConsole />} />
                <Route path='/providers' element={<LLMProviderDashboard />} />
                <Route path='/registry' element={<ToolRegistryBrowser />} />
                <Route path='/crews' element={<CrewYAMLBrowser />} />
                <Route path='/status' element={<PlatformStatus />} />

                {/* Legacy routes — keep for deep-link compatibility */}
                <Route path='/opportunities' element={<Opportunities />} />
                <Route path='/workflows' element={<WorkflowDashboard />} />

                {/* Visualization — Heat Map + Analytics */}
                <Route path='/viz' element={<VisualizationPage />} />

                {/* Platform Management */}
                <Route path='/programs' element={<Programs />} />
                <Route path='/mcp-registry' element={<MCPRegistry />} />
                <Route path='/persona-market' element={<PersonaMarket />} />

                {/* Admin & Settings */}
                <Route path='/logs' element={<Logs />} />
                <Route path='/settings' element={<Settings />} />
                <Route path='/docs' element={<Docs />} />
                <Route path='/wizard' element={<Wizard />} />

                {/* 404 */}
                <Route path='*' element={<NotFound />} />
              </Routes>
            </Layout>
          </PrivateRoute>
        } />
      </Routes>
    </BrowserRouter>
  )
}
