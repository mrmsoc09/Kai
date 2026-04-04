import React, { useState } from 'react';
import { COLORS } from '@/theme/branding';

export default function KeyManagement() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ message: string, keys_processed: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File too large. Max size is 10MB.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    const headers: Record<string, string> = {};
    try {
      const csrfRes = await fetch('/auth/csrf-token', { credentials: 'include' });
      const csrfData = await csrfRes.json();
      if (csrfData?.csrf_token) headers['X-CSRF-Token'] = csrfData.csrf_token;
    } catch {
      /* ignore */
    }

    try {
      const response = await fetch('/keys/import', {
        method: 'POST',
        headers,
        body: formData,
        credentials: 'include',
      });
      const contentType = response.headers.get('content-type') || '';
      const data = contentType.includes('application/json') ? await response.json() : null;

      if (!response.ok) {
        const detail = data?.detail || (response.status === 403 ? 'Admin token required to import keys.' : 'Failed to upload keys');
        throw new Error(detail);
      }
      if (!data) {
        throw new Error('Backend returned a non-JSON response. Check API routing/proxy.');
      }

      setResult(data as { message: string, keys_processed: string[] });
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: COLORS.surface, border: `2px solid ${COLORS.border}`, borderRadius: 10, padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h3 style={{ fontSize: '1.1rem', fontWeight: 800, color: COLORS.text }}>Bulk Key Import</h3>
        <span style={{ padding: '4px 8px', border: `1px solid ${COLORS.border}`, fontSize: '0.65rem', letterSpacing: '0.12em', textTransform: 'uppercase', color: COLORS.text }}>
          Vault Secured
        </span>
      </div>

      <p style={{ color: COLORS.textSecondary, fontSize: '0.8rem', marginBottom: 12 }}>
        Securely upload your external API keys (Shodan, ZoomEye, AlienVault, etc.) in bulk.
        Supported formats: <strong>CSV</strong> (Service,Key) or <strong>PDF</strong>.
      </p>

      <div style={{ display: 'grid', gap: 12 }}>
        <div style={{ border: `2px dashed ${COLORS.border}`, borderRadius: 10, padding: 16, textAlign: 'center' }}>
          <input
            type="file"
            accept=".csv,.pdf"
            onChange={handleFileChange}
            style={{ display: 'none' }}
            id="key-upload"
          />
          <label htmlFor="key-upload" style={{ cursor: 'pointer' }}>
            <div style={{ fontSize: '1.6rem', marginBottom: 6 }}>📁</div>
            <span style={{ color: COLORS.text, fontWeight: 700 }}>
              {file ? file.name : "Click to select or drag and drop"}
            </span>
            <p style={{ fontSize: '0.7rem', color: COLORS.textSecondary, marginTop: 4 }}>CSV or PDF up to 10MB</p>
          </label>
        </div>

        {error && (
          <div style={{ padding: 10, background: 'rgba(161,43,43,0.12)', border: `1px solid ${COLORS.status.critical}`, color: COLORS.status.critical, borderRadius: 6, fontSize: '0.75rem' }}>
            ⚠️ {error}
          </div>
        )}

        {result && (
          <div style={{ padding: 10, background: 'rgba(53,94,59,0.12)', border: `1px solid ${COLORS.status.success}`, color: COLORS.text, borderRadius: 6, fontSize: '0.75rem' }}>
            <p style={{ fontWeight: 700, marginBottom: 6 }}>✅ {result.message}</p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {result.keys_processed.map(key => (
                <span key={key} style={{ padding: '2px 6px', border: `1px solid ${COLORS.border}`, borderRadius: 4, fontFamily: 'monospace', fontSize: '0.7rem' }}>{key}</span>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={loading || !file}
          style={{
            width: '100%',
            padding: '10px 12px',
            borderRadius: 8,
            background: COLORS.secondary.main,
            color: COLORS.textInverse,
            border: `1px solid ${COLORS.border}`,
            fontWeight: 800,
            cursor: loading || !file ? 'not-allowed' : 'pointer',
            opacity: loading || !file ? 0.6 : 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 8,
          }}
        >
          {loading ? 'Processing…' : 'Import to Vault'}
        </button>
      </div>

      <div style={{ marginTop: 14, paddingTop: 12, borderTop: `1px solid ${COLORS.border}` }}>
        <h4 style={{ fontSize: '0.8rem', fontWeight: 800, color: COLORS.text, marginBottom: 6 }}>Security Notes</h4>
        <ul style={{ fontSize: '0.7rem', color: COLORS.textSecondary, display: 'grid', gap: 4, paddingLeft: 16 }}>
          <li>Files are sent directly to the backend Vault importer; keys are never stored in the browser.</li>
          <li>PDF parsing accepts lines like <code>Service: Key</code>, <code>Service = Key</code>, or <code>Service | Key</code>.</li>
          <li>Use an admin token to import. If you see a 403, switch to an admin bearer token.</li>
        </ul>
      </div>
    </div>
  );
}
