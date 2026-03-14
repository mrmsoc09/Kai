import { cn } from "@/lib/utils";

type ScoreScale = "auto" | "ratio" | "percent100";

function normalizedScore(
  score: number | null | undefined,
  scale: ScoreScale
): number | null {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return null;
  }
  if (scale === "ratio") {
    return score;
  }
  if (scale === "percent100") {
    return score / 100;
  }
  return score > 1 ? score / 100 : score;
}

function bandFromScore(
  score: number | null | undefined,
  scale: ScoreScale
): "unknown" | "low" | "medium" | "high" | "critical" {
  const normalized = normalizedScore(score, scale);
  if (normalized === null) {
    return "unknown";
  }
  if (normalized >= 0.85) {
    return "critical";
  }
  if (normalized >= 0.7) {
    return "high";
  }
  if (normalized >= 0.45) {
    return "medium";
  }
  return "low";
}

function renderScore(
  score: number | null | undefined,
  scale: ScoreScale
): string {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "n/a";
  }
  const resolvedScale = scale === "auto" ? (score > 1 ? "percent100" : "ratio") : scale;
  if (resolvedScale === "percent100") {
    return `${score.toFixed(1)}%`;
  }
  return score.toFixed(2);
}

const bandClasses: Record<ReturnType<typeof bandFromScore>, string> = {
  unknown: "border-slate-600 bg-slate-500/10 text-slate-300",
  low: "border-success/40 bg-success/15 text-success",
  medium: "border-review/40 bg-review/15 text-review",
  high: "border-blocked/40 bg-blocked/15 text-blocked",
  critical: "border-danger/40 bg-danger/15 text-danger"
};

export function ScoreBadge({
  value,
  label = "score",
  className,
  showBand = true,
  scale = "auto"
}: {
  value: number | null | undefined;
  label?: string;
  className?: string;
  showBand?: boolean;
  scale?: ScoreScale;
}) {
  const band = bandFromScore(value, scale);
  const text = renderScore(value, scale);
  const normalized = normalizedScore(value, scale);
  const normalizedText = normalized === null ? "n/a" : normalized.toFixed(2);
  return (
    <span
      title={`${label}: ${text} (${band}, normalized=${normalizedText})`}
      aria-label={`${label} ${text} ${band}`}
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        bandClasses[band],
        className
      )}
    >
      <span>{label}</span>
      <span>{text}</span>
      {showBand ? <span className="opacity-70">{band}</span> : null}
    </span>
  );
}
