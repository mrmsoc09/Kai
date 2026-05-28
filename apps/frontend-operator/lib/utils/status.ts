const base = "border font-mono";

export const STATUS_STYLE_MAP: Record<string, string> = {
  CREATED:              `${base} border-border   bg-panel        text-muted`,
  READY:                `${base} border-muted/40  bg-muted/10     text-muted`,
  RUNNING:              `${base} border-active/40 bg-active/15    text-active`,
  WAITING_APPROVAL:     `${base} border-review/40 bg-review/15    text-review`,
  BLOCKED:              `${base} border-blocked/40 bg-blocked/15  text-blocked`,
  COMPLETED:            `${base} border-intelligence/40 bg-intelligence/10 text-intelligence`,
  FAILED:               `${base} border-danger/40  bg-danger/10   text-danger`,
  CANCELED:             `${base} border-border   bg-panel         text-muted`,
  HIL_APPROVED:         `${base} border-success/40 bg-success/10  text-success`,
  NEEDS_REVIEW:         `${base} border-review/40  bg-review/10   text-review`,
  READY_FOR_SUBMISSION: `${base} border-success/40 bg-success/10  text-success`,
  SUPPRESSED_DUPLICATE: `${base} border-finding/40 bg-finding/10  text-finding`,
  APPROVED:             `${base} border-success/40 bg-success/10  text-success`,
  REJECTED:             `${base} border-danger/40  bg-danger/10   text-danger`,
  DEFERRED:             `${base} border-review/40  bg-review/10   text-review`,
  EXPIRED:              `${base} border-border   bg-panel         text-muted`,
  NEW:                  `${base} border-intelligence/40 bg-intelligence/10 text-intelligence`,
  IN_REVIEW:            `${base} border-review/40  bg-review/10   text-review`,
  DUPLICATE:            `${base} border-finding/40 bg-finding/10  text-finding`,
  RESOLVED:             `${base} border-success/40 bg-success/10  text-success`,
  ACKNOWLEDGED:         `${base} border-review/40  bg-review/10   text-review`,
  TRIAGING:             `${base} border-review/40  bg-review/10   text-review`,
  OPEN:                 `${base} border-danger/40  bg-danger/10   text-danger`,
  SUPPRESSED:           `${base} border-finding/40 bg-finding/10  text-finding`,
  SUBMITTED:            `${base} border-success/40 bg-success/10  text-success`,
  IMMEDIATE:            `${base} border-danger/40  bg-danger/10   text-danger`,
  QUEUED:               `${base} border-active/30  bg-active/10   text-active`,
  SKIPPED:              `${base} border-border   bg-panel         text-muted`,
  PENDING:              `${base} border-review/30  bg-review/10   text-review`,
  KILLED:               `${base} border-danger/50  bg-danger/10   text-danger`,
  UNKNOWN:              `${base} border-border   bg-panel         text-muted`,
};

export function normalizeStatus(status: string | null | undefined): string {
  return (status ?? "UNKNOWN").toUpperCase();
}

export function statusClassName(status: string | null | undefined): string {
  const normalized = normalizeStatus(status);
  return STATUS_STYLE_MAP[normalized] ?? `${base} border-border bg-panel text-muted`;
}
