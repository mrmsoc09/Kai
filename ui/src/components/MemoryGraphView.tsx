import type { IntelligenceRelationshipsResponse } from '../types';

interface MemoryGraphViewProps {
  relationships: IntelligenceRelationshipsResponse | null;
}

export function MemoryGraphView({ relationships }: MemoryGraphViewProps) {
  if (!relationships) {
    return (
      <section className="rounded-lg border border-dashed border-slate-700 bg-slate-900/40 p-4 text-sm text-slate-400">
        Relationship graph not loaded.
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">Memory Relationships</h3>
      <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
        <article className="rounded border border-slate-700 bg-slate-950/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Outbound</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">{relationships.outbound.length}</p>
        </article>
        <article className="rounded border border-slate-700 bg-slate-950/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-400">Inbound</p>
          <p className="mt-1 text-lg font-semibold text-slate-100">{relationships.inbound.length}</p>
        </article>
      </div>
      <div className="mt-3 space-y-2">
        {[...relationships.outbound.slice(0, 3), ...relationships.inbound.slice(0, 3)].map((edge) => (
          <p key={`${edge.source}:${edge.target}:${edge.timestamp}`} className="rounded border border-slate-700 bg-slate-950/60 px-2 py-1 text-xs text-slate-300">
            {edge.relationship_type}: {edge.source} → {edge.target} ({Math.round((edge.confidence_score ?? 0) * 100)}%)
          </p>
        ))}
        {relationships.outbound.length === 0 && relationships.inbound.length === 0 ? (
          <p className="text-xs text-slate-500">No relationships for this memory.</p>
        ) : null}
      </div>
    </section>
  );
}
