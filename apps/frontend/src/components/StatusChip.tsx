import React from 'react';
export default function StatusChip({ ok, label }: { ok: boolean; label: string }) {
  const bg = ok ? '#16a34a' : '#dc2626';
  return <span style={{ padding: '2px 8px', borderRadius: 12, background: bg, color: '#fff', fontSize: 12 }}>{label}</span>;
}
