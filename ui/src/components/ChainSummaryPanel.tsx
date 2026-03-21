import type { ReactNode } from 'react';

interface ChainSummaryPanelProps {
  chain?: Record<string, unknown> | null;
  summary?: {
    chain_count?: number;
    chain_bonus?: number;
    chain_ids?: string[];
    has_chain?: boolean;
  } | null;
  title?: string;
  emptyLabel?: string;
}

const asNumber = (value: unknown): number | null => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  return null;
};

const asString = (value: unknown): string => (typeof value === 'string' ? value : '');

const renderChainNodes = (value: unknown): ReactNode => {
  if (!Array.isArray(value) || value.length === 0) {
    return <p className="text-xs text-slate-500">No chain steps available.</p>;
  }
  const rows = value.filter((row): row is Record<string, unknown> => !!row && typeof row === 'object').slice(0, 8);
  if (!rows.length) {
    return <p className="text-xs text-slate-500">No chain steps available.</p>;
  }
  return (
    <ol className="list-decimal space-y-1 pl-5 text-xs text-slate-200">
      {rows.map((row, index) => {
        const vuln = asString(row.vuln_type) || 'step';
        const valueLabel = asString(row.value) || asString(row.node_id) || `node-${index + 1}`;
        return (
          <li key={`${vuln}-${valueLabel}-${index}`}>
            <span className="font-medium text-slate-100">{vuln}</span>
            <span className="text-slate-400"> · {valueLabel}</span>
          </li>
        );
      })}
    </ol>
  );
};

export function ChainSummaryPanel({
  chain,
  summary,
  title = 'Exploit Chain',
  emptyLabel = 'No exploit chain evidence available.',
}: ChainSummaryPanelProps) {
  const hasChain = Boolean(chain) || Boolean(summary?.has_chain);
  if (!hasChain) {
    return (
      <section className="rounded border border-slate-800 bg-slate-950/40 p-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
        <p className="mt-1 text-xs text-slate-500">{emptyLabel}</p>
      </section>
    );
  }

  const score = asNumber(chain?.score);
  const confidence = asNumber(chain?.confidence_score);
  const bonus = summary?.chain_bonus;
  const chainCount = summary?.chain_count;
  const reasoning = asString(chain?.reasoning_summary);
  const chainIds = Array.isArray(summary?.chain_ids) ? summary?.chain_ids : [];

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
        {score !== null ? <span className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-violet-200">score {Math.round(score * 100)}%</span> : null}
        {confidence !== null ? <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-cyan-200">confidence {Math.round(confidence * 100)}%</span> : null}
        {typeof bonus === 'number' ? <span className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-indigo-200">bonus {bonus.toFixed(2)}</span> : null}
        {typeof chainCount === 'number' ? <span className="rounded border border-slate-700 px-2 py-0.5 text-slate-300">{chainCount} linked chains</span> : null}
      </div>
      {reasoning ? <p className="mt-2 text-xs text-slate-300">{reasoning}</p> : null}
      {chainIds.length > 0 ? <p className="mt-2 text-[11px] text-slate-400">chain ids: {chainIds.join(', ')}</p> : null}
      <div className="mt-2">{renderChainNodes(chain?.nodes)}</div>
    </section>
  );
}
