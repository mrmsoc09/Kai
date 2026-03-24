import { FormEvent, useEffect, useMemo, useState } from 'react';
import { vaultService } from '../api';

interface ProviderRecord {
  id: string;
  name: string;
  market: string;
}

const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];

const asText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

export function VaultKeys() {
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  const [manualSubmitting, setManualSubmitting] = useState(false);
  const [manualResult, setManualResult] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);
  const [form, setForm] = useState({
    api_key: '',
    token: '',
    client_id: '',
    client_secret: '',
    notes: '',
    rate_limit: '',
    tos_version: '',
  });

  useEffect(() => {
    const loadCatalog = async () => {
      try {
        const payload = await vaultService.getProviderCatalog();
        const rows = asArray(asObject(payload).providers).map((row) => {
          const item = asObject(row);
          return {
            id: asText(item.id),
            name: asText(item.name, asText(item.id, 'provider')),
            market: asText(item.market, 'cross'),
          } satisfies ProviderRecord;
        }).filter((row) => row.id);
        setProviders(rows);
        if (rows.length > 0) {
          setSelectedProvider(rows[0].id);
        }
      } catch (error) {
        setManualError(error instanceof Error ? error.message : 'Unable to load provider catalog.');
      }
    };
    void loadCatalog();
  }, []);

  const providerLabel = useMemo(() => {
    const found = providers.find((row) => row.id === selectedProvider);
    return found ? `${found.name} (${found.market})` : selectedProvider;
  }, [providers, selectedProvider]);

  const uploadCsv = async (event: FormEvent) => {
    event.preventDefault();
    if (!uploadFile || uploading) {
      return;
    }
    setUploading(true);
    setUploadError(null);
    setUploadResult(null);
    try {
      const payload = await vaultService.importKeyFile(uploadFile);
      const imported = asObject(payload).imported_count;
      setUploadResult(
        imported !== undefined
          ? `Upload complete. Imported ${String(imported)} key entries.`
          : `Upload complete: ${JSON.stringify(payload)}`,
      );
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Key import failed.');
    } finally {
      setUploading(false);
    }
  };

  const saveManualKey = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedProvider || manualSubmitting) {
      return;
    }
    const payload = Object.fromEntries(
      Object.entries(form).filter(([, value]) => value.trim().length > 0),
    );
    if (Object.keys(payload).length === 0) {
      setManualError('Provide at least one field before storing a key.');
      return;
    }
    setManualSubmitting(true);
    setManualError(null);
    setManualResult(null);
    try {
      const result = await vaultService.storeProviderKey(selectedProvider, payload);
      setManualResult(`Stored Vault secret for ${providerLabel}: ${JSON.stringify(result)}`);
      setForm({
        api_key: '',
        token: '',
        client_id: '',
        client_secret: '',
        notes: '',
        rate_limit: '',
        tos_version: '',
      });
    } catch (error) {
      setManualError(error instanceof Error ? error.message : 'Failed to store provider key in Vault.');
    } finally {
      setManualSubmitting(false);
    }
  };

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-sm font-semibold text-slate-100">Vault + API Keys</h2>
        <p className="text-xs text-slate-400">Bulk import key files and manually store provider credentials in HashiCorp Vault.</p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-100">Bulk Import</h3>
        <p className="mb-3 text-xs text-slate-400">Upload your prepared `.csv` or `.pdf` key file via the backend `/keys/import` path.</p>
        <form onSubmit={(event) => void uploadCsv(event)} className="space-y-3">
          <input
            type="file"
            accept=".csv,.pdf,text/csv,application/pdf"
            onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 file:mr-3 file:rounded file:border-0 file:bg-cyan-500/20 file:px-3 file:py-1 file:text-cyan-200"
          />
          <button
            type="submit"
            disabled={!uploadFile || uploading}
            className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
          >
            {uploading ? 'Uploading…' : 'Import File'}
          </button>
        </form>
        {uploadResult ? <p className="mt-2 text-xs text-emerald-300">{uploadResult}</p> : null}
        {uploadError ? <p className="mt-2 text-xs text-rose-300">{uploadError}</p> : null}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-100">Manual Provider Entry</h3>
        <p className="mb-3 text-xs text-slate-400">Store provider secrets into Vault path `secret/osint/&lt;provider_id&gt;`.</p>
        <form onSubmit={(event) => void saveManualKey(event)} className="space-y-3">
          <select
            value={selectedProvider}
            onChange={(event) => setSelectedProvider(event.target.value)}
            className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name} ({provider.market})
              </option>
            ))}
            {providers.length === 0 ? <option value="">No providers loaded</option> : null}
          </select>

          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <input value={form.api_key} onChange={(event) => setForm((prev) => ({ ...prev, api_key: event.target.value }))} placeholder="API Key" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
            <input value={form.token} onChange={(event) => setForm((prev) => ({ ...prev, token: event.target.value }))} placeholder="Token" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
            <input value={form.client_id} onChange={(event) => setForm((prev) => ({ ...prev, client_id: event.target.value }))} placeholder="Client ID" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
            <input value={form.client_secret} onChange={(event) => setForm((prev) => ({ ...prev, client_secret: event.target.value }))} placeholder="Client Secret" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
            <input value={form.rate_limit} onChange={(event) => setForm((prev) => ({ ...prev, rate_limit: event.target.value }))} placeholder="Rate Limit Notes" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
            <input value={form.tos_version} onChange={(event) => setForm((prev) => ({ ...prev, tos_version: event.target.value }))} placeholder="ToS Version" className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100" />
          </div>
          <textarea
            value={form.notes}
            onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
            placeholder="Notes"
            className="min-h-[5rem] w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
          />
          <button
            type="submit"
            disabled={!selectedProvider || manualSubmitting}
            className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
          >
            {manualSubmitting ? 'Saving…' : 'Store in Vault'}
          </button>
        </form>
        {manualResult ? <p className="mt-2 text-xs text-emerald-300">{manualResult}</p> : null}
        {manualError ? <p className="mt-2 text-xs text-rose-300">{manualError}</p> : null}
      </section>
    </section>
  );
}

