import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/system';
import LogList from '../components/LogList';

export default function Logs() {
  const [runId, setRunId] = useState('');
  const [items, setItems] = useState<any[]>([]);
  const token = useStore(state => state.auth.token);
  const navigate = useNavigate();

  async function load() {
    if (!token) {
      navigate('/login');
      return;
    }
    const r = await fetch(`/api/logs/${runId}/decision_trace`, { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) { alert(`error ${r.status}`); return; }
    const j = await r.json();
    setItems(j.decision_trace || []);
  }

  if (!token) {
    navigate('/login');
    return null;
  }

  return (
    <div style={{ padding: 20, color: '#8FAF9B' }}>
      <h2>Decision Logs</h2>
      <input value={runId} onChange={e=>setRunId(e.target.value)} placeholder='run_id' />
      <button onClick={() => load()}>Load</button>
      <LogList items={items} />
    </div>
  );
}
