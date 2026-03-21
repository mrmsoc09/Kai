import type { IntelligenceMemory } from '../types';
import { formatConfidence, formatTimestamp } from '../utils/format';

interface MemoryDetailsPanelProps {
  memory: IntelligenceMemory | null;
}

export function MemoryDetailsPanel({ memory }: MemoryDetailsPanelProps) {
  if (!memory) {
    return (
      <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
        Select a memory item to inspect details.
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <h3 className="text-sm font-semibold text-slate-100">Memory Details</h3>
      <dl className="mt-3 space-y-2 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Memory ID</dt>
          <dd className="break-all text-slate-100">{memory.memory_id}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Type</dt>
          <dd className="text-slate-100">{memory.memory_type}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Scope</dt>
          <dd className="text-slate-100">{memory.scope}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Validation</dt>
          <dd className="text-slate-100">{memory.validation_status}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Confidence</dt>
          <dd className="text-slate-100">{formatConfidence(memory.confidence_score)}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-400">Timestamp</dt>
          <dd className="text-slate-100">{formatTimestamp(memory.created_at)}</dd>
        </div>
      </dl>

      <div className="mt-4 space-y-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Target</p>
        <p className="text-sm text-slate-200">{memory.domain}</p>
        {memory.ip ? <p className="text-xs text-slate-400">{memory.ip}</p> : null}
      </div>

      <div className="mt-4 space-y-2">
        <p className="text-xs uppercase tracking-wide text-slate-500">Tags</p>
        <p className="text-sm text-slate-200">{memory.tags.length > 0 ? memory.tags.join(', ') : 'No tags'}</p>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-2 text-xs md:grid-cols-2">
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <p className="uppercase tracking-wide text-slate-500">Tech Stack</p>
          <p className="mt-1 text-slate-200">{memory.tech_stack.length > 0 ? memory.tech_stack.join(', ') : 'unknown'}</p>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2">
          <p className="uppercase tracking-wide text-slate-500">Services</p>
          <p className="mt-1 text-slate-200">{memory.services.length > 0 ? memory.services.join(', ') : 'unknown'}</p>
        </div>
      </div>
    </section>
  );
}
