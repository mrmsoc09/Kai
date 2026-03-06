import React from 'react'
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
import AgentZero from './routes/AgentZero'
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

function NotFound() {
  return (
    <div style={{ padding: '3rem', textAlign: 'center', fontFamily: 'monospace' }}>
      <div style={{ color: '#00FF41', fontSize: '3rem', fontWeight: 700 }}>404</div>
      <div style={{ color: '#8892a4', marginTop: 8 }}>Page not found</div>
      <a href='/dashboard' style={{ color: '#00FF41', marginTop: 16, display: 'inline-block' }}>← Back to Dashboard</a>
    </div>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Public: Login (no sidebar) */}
        <Route path='/login' element={<Login />} />

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
                <Route path='/agent-zero' element={<AgentZero />} />

                {/* Reporting & Planning */}
                <Route path='/report-builder' element={<ReportBuilder />} />
                <Route path='/plans' element={<Plans />} />
                <Route path='/recordings' element={<Recordings />} />

                {/* Opportunity Hub + Hunt Workflows */}
                <Route path='/opportunities' element={<Opportunities />} />
                <Route path='/workflows' element={<WorkflowDashboard />} />

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
