import React from 'react';
export default function LogList({ items }: { items: any[] }) {
  return (
    <div style={{ maxHeight: 240, overflow: 'auto', background: '#0b1220', padding: 10, borderRadius: 8 }}>
      {items && items.length ? items.map((e: any, i: number) => (
        <div key={i} style={{ borderBottom: '1px solid #223', padding: '6px 0' }}>
          <div style={{ color: '#9cf' }}>{e.event}</div>
          <pre style={{ margin: 0, color: '#8FAF9B' }}>{JSON.stringify(e.data || {}, null, 2)}</pre>
        </div>
      )) : <div style={{ color: '#64748b' }}>No events</div>}
    </div>
  );
}
