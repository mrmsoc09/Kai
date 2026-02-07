import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import './theme.css'
import './theme/branding.css'

// Main Dashboard Component - Updated with K1 branding
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

// Pages
import Planner from './pages/Planner'
import Outbox from './pages/Outbox'
import HiLReview from './pages/HiLReview'

// Layout
import Layout from './components/Layout'

export default function App(){
  return <BrowserRouter>
    <Layout>
      <Routes>
        {/* Main Dashboard - K1 Unified Platform */}
        <Route path='/' element={<Navigate to='/dashboard' replace />} />
        <Route path='/dashboard' element={<Dashboard />} />

        {/* Core Operations */}
        <Route path='/operations' element={<Operations />} />
        <Route path='/operations/hil-review' element={<HiLReview />} />
        <Route path='/operations/outbox' element={<Outbox />} />
        <Route path='/operations/logs' element={<Logs />} />

        {/* Reconnaissance & Analysis */}
        <Route path='/recon' element={<Recon />} />
        <Route path='/attack-graph' element={<AttackGraph />} />
        <Route path='/chains' element={<Chains />} />

        {/* Tools & Execution */}
        <Route path='/arsenal' element={<Arsenal />} />
        <Route path='/validation' element={<Validation />} />
        <Route path='/intelligence' element={<Intelligence />} />
        <Route path='/agent-zero' element={<AgentZero />} />

        {/* Reporting & Planning */}
        <Route path='/report-builder' element={<ReportBuilder />} />
        <Route path='/plans' element={<Plans />} />
        <Route path='/recordings' element={<Recordings />} />

        {/* Platform Management */}
        <Route path='/programs' element={<Programs />} />
        <Route path='/mcp-registry' element={<MCPRegistry />} />
        <Route path='/persona-market' element={<PersonaMarket />} />

        {/* Admin & Settings */}
        <Route path='/logs' element={<Logs />} />
        <Route path='/settings' element={<Settings />} />
        <Route path='/docs' element={<Docs />} />
        <Route path='/wizard' element={<Wizard />} />
      </Routes>
    </Layout>
  </BrowserRouter>
}
