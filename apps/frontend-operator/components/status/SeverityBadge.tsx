import { cn } from "@/lib/utils";

const severityStyle: Record<string, string> = {
  INFO: "border-intelligence/40 bg-intelligence/15 text-intelligence",
  LOW: "border-success/40 bg-success/15 text-success",
  MEDIUM: "border-review/40 bg-review/15 text-review",
  HIGH: "border-blocked/40 bg-blocked/15 text-blocked",
  CRITICAL: "border-danger/40 bg-danger/15 text-danger"
};

export function SeverityBadge({ severity }: { severity: string | null | undefined }) {
  const normalized = (severity ?? "UNKNOWN").toUpperCase();
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        severityStyle[normalized] ?? "border-slate-600 bg-slate-500/10 text-slate-300"
      )}
    >
      {normalized}
    </span>
  );
}
