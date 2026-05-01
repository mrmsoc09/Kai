import { Routes, Route } from 'react-router-dom'
import { DashboardLayout } from './components/Layout/DashboardLayout'
import { AgentControlPanel } from './features/Agents/AgentControlPanel'
import { ScanDashboard } from './features/Scans/ScanDashboard'
import { MindmapCanvas } from './features/Mindmap/MindmapCanvas'
import { WordlistManager } from './features/Wordlists/WordlistManager'
import { Overview } from './features/Overview/Overview'

function App() {
  return (
    <DashboardLayout>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/agents" element={<AgentControlPanel />} />
        <Route path="/scans" element={<ScanDashboard />} />
        <Route path="/mindmap" element={<MindmapCanvas />} />
        <Route path="/wordlists" element={<WordlistManager />} />
      </Routes>
    </DashboardLayout>
  )
}

export default App
