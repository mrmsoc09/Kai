import { FormEvent, useEffect, useMemo, useState } from 'react';
import { vaultService } from '../api';
import { 
  Key, 
  Shield, 
  Trash2, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle2, 
  XCircle, 
  Plus, 
  Info, 
  Activity,
  Database,
  ExternalLink
} from 'lucide-react';

interface ProviderRecord {
  id: string;
  name: string;
  market: string;
}

interface SecretRecord {
  name: string;
  type: string;
  status: string;
  lastUpdated?: string | null;
}

const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];

const asText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

export function VaultKeys() {
  // States from original
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<string | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const [providers, setProviders] = useState<ProviderRecord[]>([]);
  const [selectedProvider, setSelectedProvider] = useState('');
  
  // New States
  const [secrets, setSecrets] = useState<SecretRecord[]>([]);
  const [loadingSecrets, setLoadingSecrets] = useState(false);
  const [vaultHealth, setVaultHealth] = useState<{connected: boolean; status: string} | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  
  const [manualSubmitting, setManualSubmitting] = useState(false);
  const [manualResult, setManualResult] = useState<string | null>(null);
  const [manualError, setManualError] = useState<string | null>(null);
  const [form, setForm] = useState({
    name: '',
    value: '',
    type: 'API Key',
    description: '',
  });

  const loadData = async () => {
    setLoadingSecrets(true);
    try {
      const [catalogPayload, secretsList, health] = await Promise.all([
        vaultService.getProviderCatalog(),
        vaultService.listSecrets(),
        vaultService.getHealth()
      ]);

      // Process Catalog
      const rows = asArray(asObject(catalogPayload).providers).map((row) => {
        const item = asObject(row);
        return {
          id: asText(item.id),
          name: asText(item.name, asText(item.id, 'provider')),
          market: asText(item.market, 'cross'),
        } satisfies ProviderRecord;
      }).filter((row) => row.id);
      setProviders(rows);
      if (rows.length > 0 && !selectedProvider) {
        setSelectedProvider(rows[0].id);
      }

      // Process Secrets
      setSecrets(secretsList);
      
      // Process Health
      setVaultHealth({
        connected: !!asObject(health).connected,
        status: asText(asObject(health).status, 'Unknown')
      });

    } catch (error) {
      setManualError(error instanceof Error ? error.message : 'Unable to load Vault data.');
    } finally {
      setLoadingSecrets(false);
    }
  };

  useEffect(() => {
    void loadData();
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
      void loadData();
    } catch (error) {
      setUploadError(error instanceof Error ? error.message : 'Key import failed.');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Are you sure you want to delete secret "${name}"?`)) return;
    try {
      await vaultService.deleteSecret(name);
      void loadData();
    } catch (error) {
      alert(error instanceof Error ? error.message : 'Delete failed');
    }
  };

  const saveSecret = async (event: FormEvent) => {
    event.preventDefault();
    const nameToUse = form.name || selectedProvider;
    if (!nameToUse || manualSubmitting) return;

    setManualSubmitting(true);
    setManualError(null);
    setManualResult(null);
    try {
      await vaultService.storeSecret({
        name: nameToUse,
        type: form.type,
        value: form.value,
        description: form.description
      });
      setManualResult(`Secret for ${nameToUse} stored successfully.`);
      setForm({ name: '', value: '', type: 'API Key', description: '' });
      setShowAddForm(false);
      void loadData();
    } catch (error) {
      setManualError(error instanceof Error ? error.message : 'Failed to store secret.');
    } finally {
      setManualSubmitting(false);
    }
  };

  const requiredSecrets = ['OPENAI_API_KEY', 'GEMINI_API_KEY', 'SHODAN_API_KEY'];
  const missingSecrets = requiredSecrets.filter(req => !secrets.some(s => s.name.toUpperCase().includes(req)));

  return (
    <div className="space-y-6 pb-12">
      <header className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Shield className="h-6 w-6 text-cyan-400" />
            Platform Secrets Management
          </h2>
          <p className="text-sm text-slate-400">Securely manage API keys and credentials in HashiCorp Vault.</p>
        </div>
        <div className="flex gap-2">
          <button 
            onClick={() => void loadData()}
            className="flex items-center gap-2 rounded-md bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
          >
            <RefreshCw className={`h-4 w-4 ${loadingSecrets ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button 
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-2 rounded-md bg-cyan-600 px-3 py-2 text-sm font-medium text-white hover:bg-cyan-500 transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add New Secret
          </button>
        </div>
      </header>

      {/* Stats Section */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase">Total Secrets</p>
            <Database className="h-4 w-4 text-slate-400" />
          </div>
          <p className="mt-1 text-2xl font-bold text-slate-100">{secrets.length}</p>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase">Vault Connection</p>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-1 flex items-center gap-2">
            {vaultHealth?.connected ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            ) : (
              <XCircle className="h-5 w-5 text-rose-500" />
            )}
            <p className="text-lg font-bold text-slate-100">{vaultHealth?.status || 'Connecting...'}</p>
          </div>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase">Missing Required</p>
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          </div>
          <p className="mt-1 text-2xl font-bold text-slate-100">{missingSecrets.length}</p>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-slate-500 uppercase">Encryption</p>
            <Shield className="h-4 w-4 text-cyan-400" />
          </div>
          <p className="mt-1 text-lg font-bold text-slate-100 uppercase">AES-256-GCM</p>
        </div>
      </div>

      {/* Missing Secrets Alert */}
      {missingSecrets.length > 0 && (
        <div className="rounded-lg border border-amber-900/50 bg-amber-900/10 p-4 flex gap-4">
          <AlertTriangle className="h-6 w-6 text-amber-500 shrink-0" />
          <div className="flex-1">
            <h3 className="text-sm font-bold text-amber-200">Missing Required Secrets</h3>
            <p className="text-xs text-amber-200/70 mt-1">
              The following secrets are required for full platform functionality: {missingSecrets.join(', ')}
            </p>
            <button 
              onClick={() => setShowAddForm(true)}
              className="mt-3 text-xs font-bold text-amber-400 hover:text-amber-300 flex items-center gap-1"
            >
              Add Missing Secrets <Plus className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}

      {/* Add Secret Form */}
      {showAddForm && (
        <section className="rounded-lg border border-slate-700 bg-slate-900 p-6 shadow-xl animate-in slide-in-from-top duration-300">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-slate-100">Add New Secret</h3>
            <button onClick={() => setShowAddForm(false)} className="text-slate-400 hover:text-slate-200">
              <XCircle className="h-5 w-5" />
            </button>
          </div>
          <form onSubmit={(event) => void saveSecret(event)} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-400">Service / Name</label>
                <div className="flex gap-2">
                  <select
                    value={selectedProvider}
                    onChange={(event) => {
                      setSelectedProvider(event.target.value);
                      setForm(prev => ({ ...prev, name: '' }));
                    }}
                    className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50"
                  >
                    <option value="">Custom...</option>
                    {providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>{provider.name}</option>
                    ))}
                  </select>
                  {!selectedProvider && (
                    <input 
                      value={form.name}
                      onChange={(e) => setForm(prev => ({ ...prev, name: e.target.value }))}
                      placeholder="Custom name..."
                      className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50"
                    />
                  )}
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-400">Secret Type</label>
                <input 
                  value={form.type}
                  onChange={(e) => setForm(prev => ({ ...prev, type: e.target.value }))}
                  className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50"
                />
              </div>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-400">Secret Value</label>
              <input 
                type="password"
                value={form.value}
                onChange={(e) => setForm(prev => ({ ...prev, value: e.target.value }))}
                placeholder="••••••••••••••••"
                className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50 font-mono"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-400">Description (Optional)</label>
              <textarea 
                value={form.description}
                onChange={(e) => setForm(prev => ({ ...prev, description: e.target.value }))}
                rows={2}
                className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:ring-1 focus:ring-cyan-500/50"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <button 
                type="button"
                onClick={() => setShowAddForm(false)}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800"
              >
                Cancel
              </button>
              <button 
                type="submit"
                disabled={manualSubmitting || (!selectedProvider && !form.name) || !form.value}
                className="flex items-center gap-2 rounded-md bg-cyan-600 px-4 py-2 text-sm font-bold text-white hover:bg-cyan-500 disabled:opacity-50 transition-all"
              >
                {manualSubmitting ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Shield className="h-4 w-4" />}
                Save to Vault
              </button>
            </div>
            {manualError && <p className="text-xs text-rose-400 mt-2 flex items-center gap-1"><XCircle className="h-3 w-3" /> {manualError}</p>}
            {manualResult && <p className="text-xs text-emerald-400 mt-2 flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> {manualResult}</p>}
          </form>
        </section>
      )}

      {/* Main Secrets Table */}
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 overflow-hidden">
        <div className="bg-slate-800/50 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Key className="h-4 w-4 text-cyan-400" />
            Secrets Inventory
          </h3>
          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-700 text-slate-300">VAULT v2</span>
        </div>
        
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-[10px] uppercase font-bold text-slate-500 tracking-wider">
                <th className="px-4 py-3">Service / Secret Name</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {secrets.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-12 text-center text-sm text-slate-500">
                    {loadingSecrets ? (
                      <div className="flex flex-col items-center gap-2">
                        <RefreshCw className="h-6 w-6 animate-spin text-cyan-500" />
                        Scanning Vault...
                      </div>
                    ) : (
                      "No secrets configured. Add your first secret to get started."
                    )}
                  </td>
                </tr>
              ) : (
                secrets.map((secret) => (
                  <tr key={secret.name} className="hover:bg-slate-800/30 transition-colors group">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded bg-slate-950 border border-slate-800 group-hover:border-cyan-500/30 transition-colors">
                          <Key className="h-4 w-4 text-slate-400 group-hover:text-cyan-400" />
                        </div>
                        <span className="text-sm font-medium text-slate-200">{secret.name}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-slate-400">{secret.type}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-xs text-emerald-400 font-medium">
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {secret.status}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex justify-end gap-2">
                        <button className="p-1.5 rounded bg-slate-800 text-slate-400 hover:text-slate-100 hover:bg-slate-700">
                          <Info className="h-4 w-4" />
                        </button>
                        <button 
                          onClick={() => void handleDelete(secret.name)}
                          className="p-1.5 rounded bg-slate-800 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30"
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* Bulk Import Section */}
      <section className="rounded-lg border border-slate-800 bg-slate-900/40 p-6">
        <div className="flex items-start gap-4">
          <div className="p-3 rounded-lg bg-cyan-500/10 border border-cyan-500/20">
            <ExternalLink className="h-6 w-6 text-cyan-400" />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-slate-100">Bulk Key Import</h3>
            <p className="text-sm text-slate-400 mt-1">
              Upload your prepared `.csv` or `.pdf` key file. This will process and encrypt keys into Vault automatically.
            </p>
            <form onSubmit={(event) => void uploadCsv(event)} className="mt-4 flex flex-col md:flex-row gap-3">
              <input
                type="file"
                accept=".csv,.pdf,text/csv,application/pdf"
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
                className="flex-1 rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-200 file:mr-3 file:rounded file:border-0 file:bg-cyan-500/20 file:px-3 file:py-1 file:text-cyan-200"
              />
              <button
                type="submit"
                disabled={!uploadFile || uploading}
                className="rounded-md bg-slate-800 px-6 py-2 text-sm font-bold text-slate-100 hover:bg-slate-700 disabled:opacity-50 flex items-center justify-center gap-2"
              >
                {uploading ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                Import File
              </button>
            </form>
            {uploadResult ? <p className="mt-2 text-xs text-emerald-400 flex items-center gap-1"><CheckCircle2 className="h-3 w-3" /> {uploadResult}</p> : null}
            {uploadError ? <p className="mt-2 text-xs text-rose-400 flex items-center gap-1"><XCircle className="h-3 w-3" /> {uploadError}</p> : null}
          </div>
        </div>
      </section>
    </div>
  );
}

