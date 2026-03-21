import { useMemo } from 'react';
import type { MissionTimelineCategory, MissionTimelineEvent, TimelineSeverity } from '../types';
import { formatTimestamp } from '../utils/format';

interface MissionTimelineProps {
  events: MissionTimelineEvent[];
}

const severityClasses: Record<TimelineSeverity, string> = {
  info: 'border-cyan-400/50 bg-cyan-500/10 text-cyan-100',
  warning: 'border-amber-400/60 bg-amber-400/15 text-amber-100',
  error: 'border-rose-400/60 bg-rose-500/15 text-rose-100',
};

const categoryClasses: Record<MissionTimelineCategory, string> = {
  governance: 'bg-violet-500/15 text-violet-200',
  lifecycle: 'bg-blue-500/15 text-blue-200',
  artifact: 'bg-emerald-500/15 text-emerald-200',
  error: 'bg-rose-500/15 text-rose-200',
  operation: 'bg-slate-700 text-slate-200',
};

const groupedByDay = (events: MissionTimelineEvent[]): Array<{ day: string; rows: MissionTimelineEvent[] }> => {
  const groupMap = new Map<string, MissionTimelineEvent[]>();
  for (const event of events) {
    const day = new Date(event.timestamp).toLocaleDateString();
    const current = groupMap.get(day) ?? [];
    current.push(event);
    groupMap.set(day, current);
  }

  return [...groupMap.entries()].map(([day, rows]) => ({ day, rows }));
};

export function MissionTimeline({ events }: MissionTimelineProps) {
  const groups = useMemo(() => groupedByDay(events), [events]);

  if (events.length === 0) {
    return <p className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">No timeline events yet.</p>;
  }

  return (
    <div className="max-h-[420px] space-y-4 overflow-y-auto pr-1">
      {groups.map((group) => (
        <section key={group.day} className="space-y-2">
          <h4 className="text-xs uppercase tracking-wide text-slate-400">{group.day}</h4>
          <div className="space-y-2">
            {group.rows.map((event) => (
              <article key={event.id} className={`rounded-lg border p-3 ${severityClasses[event.severity]}`}>
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium">{event.message}</p>
                  <span className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide ${categoryClasses[event.category]}`}>
                    {event.category}
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-slate-300">
                  <span>{event.eventType}</span>
                  {event.actor ? <span>by {event.actor}</span> : null}
                  <span>{formatTimestamp(event.timestamp)}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
