/**
 * Kaison Composer Communications + Agent Zero Dashboard
 *
 * Left column (existing): audit log from /agent0/logs relay
 * Right column (expanded): live agent registry, team metrics, LLM usage,
 *   and health status from:
 *   - /api/autonomous/agents        (agent list + performance)
 *   - /api/autonomous/status        (team metrics)
 *   - /api/v1/agent-zero/llm/usage  (token / cost)
 *   - /api/v1/agent-zero/health     (system health)
 */
import React, { useEffect, useState } from 'react';

const apiBase = import.meta.env.VITE_API_BASE || '';

// All fetches use credentials:'include' — JWT lives in HttpOnly cookie.
// No manual token header: the cookie is sent automatically.
async function apiFetch(path: string) {
  const r = await fetch(apiBase + path, { credentials: 'include', cache: 'no-store' });
  if (!r.ok) throw new Error(`${r.status}`);
  return r.json();
}

type LogEntry = { ts: number; source: string; text: string; client?: string };

interface AgentInfo {
  agent_id: string;
  name: string;
  objective: string | null;
  autonomy_level: number;
  status: string;
  performance: { success_rate: number; success_count: number; failure_count: number };
  skills: Record<string, number>;
}

interface TeamMetrics {
  learning_rate: number;
  cooperation_level: number;
  efficiency_score: number;
}

interface LLMUsage {
  total_requests?: number;
  total_tokens?: number;
  total_cost_usd?: number;
  by_model?: Record<string, { requests: number; tokens: number; cost: number }>;
}

interface SystemHealth {
  k1_status?: string;
  systems?: Record<string, string>;
}

export default function AgentZero() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [teamMetrics, setTeamMetrics] = useState<TeamMetrics | null>(null);
  const [totalAgents, setTotalAgents] = useState<number | null>(null);
  const [llmUsage, setLlmUsage] = useState<LLMUsage | null>(null);
  const [health, setHealth] = useState<SystemHealth | null>(null);

  // Load relay audit logs (existing behaviour)
  const loadLogs = async () => {
    try {
      const j = await apiFetch('/agent0/logs');
      setLogs(j.logs || []);
    } catch { /* relay offline — silently keep previous state */ }
  };

  // Load agent registry from autonomous system
  const loadAgents = async () => {
    try {
      const j = await apiFetch('/api/autonomous/agents');
      setAgents(j.agents || []);
      setTotalAgents(j.total_agents ?? null);
      if (j.team_metrics) setTeamMetrics(j.team_metrics);
    } catch { /* system not initialised */ }
  };

  // Load LLM token / cost usage
  const loadLLMUsage = async () => {
    try {
      const j = await apiFetch('/api/v1/agent-zero/llm/usage');
      setLlmUsage(j);
    } catch { /* agent-zero integration offline */ }
  };

  // Load health / relay status
  const loadHealth = async () => {
    try {
      const j = await apiFetch('/api/v1/agent-zero/health');
      setHealth(j);
    } catch { /* agent-zero health not available */ }
  };

  useEffect(() => {
    loadLogs();
    loadAgents();
    loadLLMUsage();
    loadHealth();

    // Relay log + agent state refresh every 5 s
    const id = setInterval(() => {
      loadLogs();
      loadAgents();
    }, 5000);
    // Cost refreshes less often (60 s) — it's cumulative
    const costId = setInterval(loadLLMUsage, 60000);
    const healthId = setInterval(loadHealth, 15000);

    return () => { clearInterval(id); clearInterval(costId); clearInterval(healthId); };
  }, []);

  const autonomyLabel = (level: number) => {
    const labels: Record<number, string> = {
      0: 'Reactive',
      1: 'Semi-auto',
      2: 'Mostly auto',
      3: 'Full auto',
    };
    return labels[level] ?? `L${level}`;
  };

  const pct = (v: number) => `${Math.round(v * 100)}%`;

  const relayStatus = health?.k1_status ?? 'unknown';
  const relayColor = relayStatus === 'healthy' ? 'text-teal-400' : 'text-slate-400';

  return (
    <div className='h-full'>
      <h2 className='text-xl mb-2 font-semibold text-purple-300'>
        Kaison Composer Communications
      </h2>

      <div className='grid grid-cols-12 gap-4'>
        {/* ── Left: relay audit log (existing) ──────────────────────── */}
        <div className='col-span-7 p-3 bg-slate-950/60 rounded border border-slate-800 h-[70vh] overflow-auto'>
          <table className='w-full text-sm'>
            <thead className='text-slate-400'>
              <tr>
                <th className='text-left'>Time</th>
                <th className='text-left'>Client</th>
                <th className='text-left'>Text</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((e, i) => (
                <tr key={i} className='border-t border-slate-800'>
                  <td className='py-1 pr-2 text-slate-300'>{new Date(e.ts).toLocaleString()}</td>
                  <td className='py-1 pr-2 text-slate-400'>{e.client || 'n/a'}</td>
                  <td className='py-1 text-slate-200'>{e.text}</td>
                </tr>
              ))}
              {logs.length === 0 && (
                <tr>
                  <td colSpan={3} className='py-4 text-center text-slate-600 text-xs'>
                    No relay messages logged yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* ── Right: status + agent registry + metrics ──────────────── */}
        <div className='col-span-5 space-y-3 h-[70vh] overflow-auto'>

          {/* Policy (unchanged) */}
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-1'>Policy</h3>
            <p className='text-slate-300 text-sm'>
              Human-in-the-Loop required for all external comms and submissions.
              Kaison Composer is the single gateway.
            </p>
          </section>

          {/* Status — wired to /api/v1/agent-zero/health */}
          <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
            <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-1'>Status</h3>
            <ul className='text-slate-200 text-sm space-y-1'>
              <li>
                Relay:{' '}
                <span className={relayColor}>
                  {health ? relayStatus : 'connecting…'}
                </span>
              </li>
              <li>
                Audit: <span className='text-cyan-300'>Merkle logged</span>
              </li>
              {health?.systems && Object.entries(health.systems).map(([k, v]) => (
                <li key={k}>
                  {k}:{' '}
                  <span className={v === 'healthy' || v === 'available' ? 'text-teal-400' : 'text-amber-400'}>
                    {v}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          {/* Team metrics — from /api/autonomous/agents */}
          {teamMetrics && (
            <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
              <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-2'>
                Swarm Metrics
                {totalAgents !== null && (
                  <span className='ml-2 text-purple-400 normal-case'>{totalAgents} agents</span>
                )}
              </h3>
              <div className='grid grid-cols-3 gap-2 text-center'>
                {[
                  { label: 'Efficiency', value: pct(teamMetrics.efficiency_score) },
                  { label: 'Cooperation', value: pct(teamMetrics.cooperation_level) },
                  { label: 'Learning', value: pct(teamMetrics.learning_rate) },
                ].map(m => (
                  <div key={m.label} className='p-2 bg-slate-900 rounded border border-slate-800'>
                    <div className='text-cyan-300 font-bold text-base'>{m.value}</div>
                    <div className='text-slate-500 text-xs mt-0.5'>{m.label}</div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Agent registry — from /api/autonomous/agents */}
          {agents.length > 0 && (
            <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
              <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-2'>
                Active Agents
              </h3>
              <div className='space-y-2'>
                {agents.map(a => (
                  <div
                    key={a.agent_id}
                    className='p-2 bg-slate-900 rounded border border-slate-800 text-xs'
                  >
                    <div className='flex items-center justify-between mb-1'>
                      <span className='text-slate-200 font-medium truncate mr-2'>{a.name}</span>
                      <span
                        className={
                          'shrink-0 px-1.5 py-0.5 rounded text-xs font-bold ' +
                          (a.status === 'idle'
                            ? 'bg-slate-800 text-slate-400'
                            : a.status === 'executing'
                            ? 'bg-purple-900/40 text-purple-300'
                            : 'bg-cyan-900/30 text-cyan-300')
                        }
                      >
                        {a.status}
                      </span>
                    </div>
                    <div className='flex gap-3 text-slate-500'>
                      <span>{a.objective ?? 'general'}</span>
                      <span>·</span>
                      <span>{autonomyLabel(a.autonomy_level)}</span>
                      <span>·</span>
                      <span
                        className={
                          a.performance.success_rate >= 0.7
                            ? 'text-teal-400'
                            : a.performance.success_rate >= 0.4
                            ? 'text-amber-400'
                            : 'text-slate-500'
                        }
                      >
                        {pct(a.performance.success_rate)} success
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* LLM usage — from /api/v1/agent-zero/llm/usage */}
          {llmUsage && (
            <section className='p-3 bg-slate-950/60 rounded border border-slate-800'>
              <h3 className='text-sm uppercase tracking-wider text-slate-400 mb-2'>LLM Usage</h3>
              <div className='grid grid-cols-3 gap-2 text-center'>
                {[
                  {
                    label: 'Requests',
                    value:
                      llmUsage.total_requests != null
                        ? llmUsage.total_requests.toLocaleString()
                        : '—',
                  },
                  {
                    label: 'Tokens',
                    value:
                      llmUsage.total_tokens != null
                        ? (llmUsage.total_tokens / 1000).toFixed(1) + 'k'
                        : '—',
                  },
                  {
                    label: 'Cost',
                    value:
                      llmUsage.total_cost_usd != null
                        ? '$' + llmUsage.total_cost_usd.toFixed(4)
                        : '—',
                  },
                ].map(m => (
                  <div key={m.label} className='p-2 bg-slate-900 rounded border border-slate-800'>
                    <div className='text-purple-300 font-bold text-sm'>{m.value}</div>
                    <div className='text-slate-500 text-xs mt-0.5'>{m.label}</div>
                  </div>
                ))}
              </div>
              {llmUsage.by_model && Object.keys(llmUsage.by_model).length > 0 && (
                <div className='mt-2 space-y-1'>
                  {Object.entries(llmUsage.by_model).map(([model, stats]) => (
                    <div key={model} className='flex justify-between text-xs text-slate-500'>
                      <span className='truncate text-slate-400 mr-2'>{model}</span>
                      <span>{stats.requests} req · {(stats.tokens / 1000).toFixed(1)}k tok</span>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
