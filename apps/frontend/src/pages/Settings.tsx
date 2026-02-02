import React, { useEffect, useState } from 'react';
import { State } from '../lib/api';

type ProviderModel = { name?: string; valid: boolean };

type ConfigResp = {
  providers: { preferred: string; models: Record<string, ProviderModel> };
  vector: { backend: string; mem_count: number };
  hil_gate_enforced: boolean;
  scope_policy: string;
};

export default function Settings() {
  const [cfg, setCfg] = useState<ConfigResp | null>(null);
  const [err, setErr] = useState<string>('');

  useEffect(() => {
    State.config()
      .then(setCfg)
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <div className="p-6 text-sm text-gray-200">
      <h1 className="text-2xl font-bold mb-4">System Settings</h1>
      {err && <div className="text-red-400">{err}</div>}
      {!cfg && !err && <div>Loading…</div>}
      {cfg && (
        <div className="space-y-6">
          <section>
            <h2 className="text-xl font-semibold mb-2">Providers / Models</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {Object.entries(cfg.providers.models).map(([k, v]) => (
                <div key={k} className={`p-3 rounded border ${v.valid ? 'border-emerald-500/40' : 'border-amber-500/40'} bg-black/30` }>
                  <div className="flex justify-between">
                    <span className="font-mono">{k}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${v.valid ? 'bg-emerald-600/40' : 'bg-amber-600/40'}`}>{v.valid ? 'valid' : 'invalid'}</span>
                  </div>
                  <div className="opacity-80 text-xs mt-1">{v.name || 'unset'}</div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-xs opacity-70">Preferred: <span className="font-mono">{cfg.providers.preferred}</span></div>
          </section>
          <section>
            <h2 className="text-xl font-semibold mb-2">Vector Backend</h2>
            <div className="p-3 rounded border border-cyan-500/40 bg-black/30">
              <div>Backend: <span className="font-mono">{cfg.vector.backend}</span></div>
              <div>Memory entries: <span className="font-mono">{cfg.vector.mem_count}</span></div>
            </div>
          </section>
          <section>
            <h2 className="text-xl font-semibold mb-2">Policy</h2>
            <div className="p-3 rounded border border-purple-500/40 bg-black/30 grid grid-cols-2 gap-2">
              <div>HiL Gate: <span className="font-mono">{cfg.hil_gate_enforced ? 'ENFORCED' : 'off'}</span></div>
              <div>Scope Policy: <span className="font-mono">{cfg.scope_policy}</span></div>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
