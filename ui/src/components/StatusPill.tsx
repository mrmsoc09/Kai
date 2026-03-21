import type { MissionStatus } from '../types';

interface StatusPillProps {
  status: MissionStatus;
}

const statusClass: Record<MissionStatus, string> = {
  created: 'bg-blue-500/20 text-blue-200',
  running: 'bg-teal-500/20 text-teal-200',
  paused: 'bg-amber-500/20 text-amber-200',
  completed: 'bg-emerald-500/20 text-emerald-200',
  failed: 'bg-rose-500/20 text-rose-200',
  cancelled: 'bg-violet-500/20 text-violet-200',
  unknown: 'bg-slate-700/70 text-slate-200',
};

export function StatusPill({ status }: StatusPillProps) {
  return <span className={`rounded-full px-2 py-1 text-xs font-medium uppercase tracking-wide ${statusClass[status]}`}>{status}</span>;
}
