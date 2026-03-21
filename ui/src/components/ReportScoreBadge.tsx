interface ReportScoreBadgeProps {
  score: number;
  label: string;
}

const scoreClass = (score: number): string => {
  if (score >= 0.85) {
    return 'border-emerald-500/50 bg-emerald-500/15 text-emerald-200';
  }
  if (score >= 0.65) {
    return 'border-cyan-500/50 bg-cyan-500/15 text-cyan-200';
  }
  if (score >= 0.45) {
    return 'border-amber-500/50 bg-amber-500/15 text-amber-200';
  }
  return 'border-rose-500/50 bg-rose-500/15 text-rose-200';
};

export function ReportScoreBadge({ score, label }: ReportScoreBadgeProps) {
  return (
    <span className={`rounded border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide ${scoreClass(score)}`}>
      {label}: {Math.round(score * 100)}%
    </span>
  );
}
