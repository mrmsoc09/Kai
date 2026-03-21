import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { MemoryDetailsPanel } from '../components/MemoryDetailsPanel';
import { MemoryGraphView } from '../components/MemoryGraphView';
import { intelligenceService } from '../api';
import type { IntelligenceMemory, IntelligenceRelationshipsResponse, IntelligenceStatsResponse } from '../types';
import { formatConfidence, formatTimestamp } from '../utils/format';

const extractVulnType = (memory: IntelligenceMemory | null): string | null => {
  if (!memory) {
    return null;
  }
  const tag = memory.tags.find((row) => row.startsWith('vuln_type:'));
  return tag ? tag.slice('vuln_type:'.length) : null;
};

export function IntelligenceCenter() {
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<IntelligenceMemory[]>([]);
  const [search, setSearch] = useState(searchParams.get('search') ?? '');
  const [filterType, setFilterType] = useState('');
  const [validationStatus, setValidationStatus] = useState('');
  const [scopeFilter, setScopeFilter] = useState('');
  const [minConfidence, setMinConfidence] = useState(0.4);
  const [selectedMemoryId, setSelectedMemoryId] = useState<string | null>(searchParams.get('memory_id'));
  const [relationships, setRelationships] = useState<IntelligenceRelationshipsResponse | null>(null);
  const [stats, setStats] = useState<IntelligenceStatsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadMemory = useCallback(async () => {
    setError(null);
    setIsLoading(true);
    try {
      const payload = await intelligenceService.listMemory({
        search: search || undefined,
        memory_type: filterType || undefined,
        validation_status: validationStatus || undefined,
        scope: scopeFilter || undefined,
        min_confidence: minConfidence,
        limit: 250,
      });

      setRows(payload.items);
      if (payload.items.length > 0) {
        setSelectedMemoryId((current) => current ?? payload.items[0].memory_id);
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load intelligence memory.');
    } finally {
      setIsLoading(false);
    }
  }, [filterType, minConfidence, scopeFilter, search, validationStatus]);

  const loadStats = useCallback(async () => {
    try {
      const payload = await intelligenceService.getStats();
      setStats(payload);
    } catch {
      setStats(null);
    }
  }, []);

  useEffect(() => {
    void loadMemory();
    void loadStats();
  }, [loadMemory, loadStats]);

  useEffect(() => {
    const id = window.setTimeout(() => {
      void loadMemory();
    }, 250);
    return () => window.clearTimeout(id);
  }, [search, filterType, validationStatus, scopeFilter, minConfidence, loadMemory]);

  useEffect(() => {
    const loadRelationships = async () => {
      if (!selectedMemoryId) {
        setRelationships(null);
        return;
      }

      try {
        const payload = await intelligenceService.getRelationships(selectedMemoryId);
        setRelationships(payload);
      } catch {
        setRelationships(null);
      }
    };

    void loadRelationships();
  }, [selectedMemoryId]);

  const selectedMemory = useMemo(
    () => rows.find((memory) => memory.memory_id === selectedMemoryId) ?? null,
    [rows, selectedMemoryId],
  );

  const memoryTypes = useMemo(() => {
    const types = new Set(rows.map((item) => item.memory_type));
    return [...types].sort();
  }, [rows]);

  const scopeValues = useMemo(() => {
    const values = new Set(rows.map((item) => item.scope));
    return [...values].sort();
  }, [rows]);

  const selectedVulnType = extractVulnType(selectedMemory);

  return (
    <section className="space-y-6">
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h2 className="text-sm font-semibold text-slate-100">Intelligence Surface</h2>
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-6">
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring md:col-span-2"
            placeholder='Search memory, domain, "what do we know about X"...'
          />
          <select
            value={filterType}
            onChange={(event) => setFilterType(event.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            <option value="">All types</option>
            {memoryTypes.map((type) => (
              <option key={type} value={type}>{type}</option>
            ))}
          </select>
          <select
            value={validationStatus}
            onChange={(event) => setValidationStatus(event.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            <option value="">All statuses</option>
            <option value="confirmed">confirmed</option>
            <option value="partial">partial</option>
            <option value="unvalidated">unvalidated</option>
            <option value="rejected">rejected</option>
          </select>
          <select
            value={scopeFilter}
            onChange={(event) => setScopeFilter(event.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            <option value="">All scopes</option>
            {scopeValues.map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={minConfidence}
            onChange={(event) => setMinConfidence(Number(event.target.value))}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
            placeholder="min confidence"
          />
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
          <span className="rounded border border-slate-700 px-2 py-1">{rows.length} memory records</span>
          {stats ? (
            <>
              <span className="rounded border border-slate-700 px-2 py-1">graph nodes {String(stats.graph.node_count ?? '-')}</span>
              <span className="rounded border border-slate-700 px-2 py-1">graph edges {String(stats.graph.edge_count ?? '-')}</span>
            </>
          ) : null}
          {isLoading ? <span className="text-slate-500">loading...</span> : null}
        </div>
        {error ? <p className="mt-3 text-xs text-rose-300">{error}</p> : null}
      </section>

      <section className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-100">Memory List</h2>
            {selectedMemory ? (
              <div className="flex flex-wrap gap-2 text-xs">
                <Link
                  to={`/opportunities?search=${encodeURIComponent(selectedVulnType ?? selectedMemory.domain)}`}
                  className="rounded border border-cyan-500/30 px-2 py-1 text-cyan-200 hover:border-cyan-400"
                >
                  related opportunities
                </Link>
                <Link
                  to={`/reports?target=${encodeURIComponent(selectedMemory.domain)}`}
                  className="rounded border border-violet-500/30 px-2 py-1 text-violet-200 hover:border-violet-400"
                >
                  related reports
                </Link>
              </div>
            ) : null}
          </div>
          <div className="max-h-[560px] overflow-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="pb-2">Type</th>
                  <th className="pb-2">Target</th>
                  <th className="pb-2">Confidence</th>
                  <th className="pb-2">Status</th>
                  <th className="pb-2">Scope</th>
                  <th className="pb-2">Tags</th>
                  <th className="pb-2">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {rows.map((row) => (
                  <tr
                    key={row.memory_id}
                    onClick={() => setSelectedMemoryId(row.memory_id)}
                    className={`cursor-pointer ${selectedMemoryId === row.memory_id ? 'bg-cyan-500/10' : 'hover:bg-slate-800/60'}`}
                  >
                    <td className="py-2 text-slate-200">{row.memory_type}</td>
                    <td className="py-2 text-slate-200">{row.domain}</td>
                    <td className="py-2 text-slate-300">{formatConfidence(row.confidence_score)}</td>
                    <td className="py-2">
                      <span className={`rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${
                        row.validation_status === 'confirmed'
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : row.validation_status === 'partial'
                          ? 'bg-amber-500/15 text-amber-300'
                          : row.validation_status === 'rejected'
                          ? 'bg-rose-500/15 text-rose-300'
                          : 'bg-slate-700/60 text-slate-400'
                      }`}>
                        {row.validation_status ?? 'unvalidated'}
                      </span>
                    </td>
                    <td className="py-2 text-slate-300">{row.scope}</td>
                    <td className="py-2 text-slate-300">{row.tags.slice(0, 3).join(', ')}</td>
                    <td className="py-2 text-slate-400">{formatTimestamp(row.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!isLoading && rows.length === 0 ? (
            <p className="mt-3 text-sm text-slate-400">No memory records for current filters.</p>
          ) : null}
        </section>

        <div className="space-y-6">
          <MemoryGraphView relationships={relationships} />
          <MemoryDetailsPanel memory={selectedMemory} />
        </div>
      </section>
    </section>
  );
}
