const base = "border";

export const STATUS_STYLE_MAP: Record<string, string> = {
  CREATED: `${base} border-slate-700 bg-slate-500/15 text-slate-300`,
  READY: `${base} border-slate-600 bg-slate-400/10 text-slate-200`,
  RUNNING: `${base} border-active/40 bg-active/15 text-active`,
  WAITING_APPROVAL: `${base} border-review/40 bg-review/15 text-review`,
  BLOCKED: `${base} border-blocked/40 bg-blocked/15 text-blocked`,
  COMPLETED: `${base} border-intelligence/40 bg-intelligence/15 text-intelligence`,
  FAILED: `${base} border-danger/40 bg-danger/15 text-danger`,
  CANCELED: `${base} border-slate-600 bg-slate-500/10 text-slate-300`,
  HIL_APPROVED: `${base} border-success/40 bg-success/15 text-success`,
  NEEDS_REVIEW: `${base} border-review/40 bg-review/15 text-review`,
  READY_FOR_SUBMISSION: `${base} border-success/40 bg-success/15 text-success`,
  SUPPRESSED_DUPLICATE: `${base} border-finding/40 bg-finding/15 text-finding`,
  APPROVED: `${base} border-success/40 bg-success/15 text-success`,
  REJECTED: `${base} border-danger/40 bg-danger/15 text-danger`,
  DEFERRED: `${base} border-review/40 bg-review/15 text-review`,
  EXPIRED: `${base} border-slate-600 bg-slate-500/10 text-slate-300`,
  NEW: `${base} border-intelligence/40 bg-intelligence/15 text-intelligence`,
  IN_REVIEW: `${base} border-review/40 bg-review/15 text-review`,
  DUPLICATE: `${base} border-finding/40 bg-finding/15 text-finding`,
  RESOLVED: `${base} border-success/40 bg-success/15 text-success`,
  SUBMITTED: `${base} border-success/40 bg-success/15 text-success`,
  QUEUED: `${base} border-active/30 bg-active/10 text-active`,
  SKIPPED: `${base} border-slate-600 bg-slate-500/10 text-slate-300`,
  PENDING: `${base} border-review/30 bg-review/10 text-review`
};

export function normalizeStatus(status: string | null | undefined): string {
  return (status ?? "UNKNOWN").toUpperCase();
}

export function statusClassName(status: string | null | undefined): string {
  const normalized = normalizeStatus(status);
  return STATUS_STYLE_MAP[normalized] ?? `${base} border-slate-600 bg-slate-500/10 text-slate-300`;
}
