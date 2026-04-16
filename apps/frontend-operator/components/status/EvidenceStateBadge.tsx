import { StatusBadge } from "@/components/status/StatusBadge";

function normalizeEvidenceState(state: string | null | undefined): string {
  const normalized = (state ?? "").trim().toUpperCase();
  if (!normalized) {
    return "UNKNOWN";
  }
  if (normalized.includes("READY")) {
    return "READY_FOR_SUBMISSION";
  }
  if (normalized.includes("INSUFFICIENT")) {
    return "NEEDS_REVIEW";
  }
  if (normalized.includes("BLOCKED")) {
    return "BLOCKED";
  }
  return normalized;
}

export function EvidenceStateBadge({ state }: { state: string | null | undefined }) {
  return <StatusBadge status={normalizeEvidenceState(state)} />;
}
