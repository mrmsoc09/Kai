import React, { useEffect, useState } from 'react';

export default function Outbox() {
  const [files, setFiles] = useState<any[]>([]);
  const token = localStorage.getItem('token') || 'devtoken';
  async function load() {
    const r = await fetch('/api/submissions/outbox', { headers: { Authorization: `Bearer ${token}` } });
    if (!r.ok) { return; }
    const j = await r.json();
    setFiles(j.files || []);
  }
  useEffect(() => { void load(); }, []);
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
