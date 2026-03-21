import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute } from './components/ProtectedRoute';
import { AppLayout } from './layouts/AppLayout';
import { Artifacts } from './pages/Artifacts';
import { Dashboard } from './pages/Dashboard';
import { Governance } from './pages/Governance';
import { IntelligenceCenter } from './pages/IntelligenceCenter';
import { Login } from './pages/Login';
import { MissionControl } from './pages/MissionControl';
import { Opportunities } from './pages/Opportunities';
import { Reports } from './pages/Reports';
import { Simulation } from './pages/Simulation';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/mission-control" element={<MissionControl />} />
            <Route path="/intelligence-center" element={<IntelligenceCenter />} />
            <Route path="/opportunities" element={<Opportunities />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/artifacts" element={<Artifacts />} />
            <Route path="/governance" element={<Governance />} />
            <Route path="/simulation" element={<Simulation />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
