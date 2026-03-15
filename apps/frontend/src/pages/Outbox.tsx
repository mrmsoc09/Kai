import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useStore } from '../store/system';

export default function Outbox() {
  const [files, setFiles] = useState<any[]>([]);
  const token = useStore(state => state.auth.token);
  const navigate = useNavigate();

  async function load() {
    if (!token) { navigate('/login'); return; }
    const r = await fetch('/api/submissions/outbox', { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) { return; }
    const j = await r.json();
    setFiles(j.files || []);
  }
  useEffect(() => {
    if (!token) { navigate('/login'); return; }
    void load();
  }, [token]);
  return (
    <div style={{ padding: 20, color: '#8FAF9B' }}>
      <h2>Outbox</h2>
      <button onClick={() => load()}>Refresh</button>
      <table style={{ width: '100%', marginTop: 12 }}>
        <thead><tr><th>Name</th><th>Size</th></tr></thead>
        <tbody>
          {files.map((f, i) => <tr key={i}><td>{f.name}</td><td>{f.size}</td></tr>)}
        </tbody>
      </table>
      <p>Note: Download serving can be added via a static file route if desired.</p>
    </div>
  );
}
