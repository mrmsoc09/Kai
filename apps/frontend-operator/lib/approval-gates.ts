import type { CampaignDiagnosticsResponse } from "@/lib/types";

import type { InferredApprovalGate } from "@/components/approvals/ApprovalGateTable";

function parseTimestamp(raw: string | null): number {
  if (!raw) {
    return 0;
  }
  const t = Date.parse(raw);
  return Number.isNaN(t) ? 0 : t;
}

function inferStatus(eventType: string, payload: Record<string, unknown>): string {
  const payloadStatus = payload.status;
  if (typeof payloadStatus === "string" && payloadStatus.length > 0) {
    return payloadStatus.toUpperCase();
  }
  const normalizedType = eventType.toLowerCase();
  if (normalizedType.includes("approved")) {
    return "APPROVED";
  }
  if (normalizedType.includes("rejected")) {
    return "REJECTED";
  }
  if (normalizedType.includes("deferred")) {
    return "DEFERRED";
  }
  if (normalizedType.includes("canceled")) {
    return "CANCELED";
  }
  if (normalizedType.includes("expired")) {
    return "EXPIRED";
  }
  return "PENDING";
}

export function inferApprovalGates(
  campaignDiagnostics: CampaignDiagnosticsResponse
): InferredApprovalGate[] {
  const byGateId = new Map<string, InferredApprovalGate>();
  for (const event of campaignDiagnostics.recent_audit_events) {
    if (!event.approval_gate_id) {
      continue;
    }
    const current = byGateId.get(event.approval_gate_id);
    const next: InferredApprovalGate = {
      gate_id: event.approval_gate_id,
      campaign_id: campaignDiagnostics.campaign.id,
      phase_job_id:
        event.phase_job_id ??
        (typeof event.payload.phase_job_id === "string" ? event.payload.phase_job_id : null),
      status: inferStatus(event.event_type, event.payload),
      source_event_type: event.event_type,
      happened_at: event.happened_at ?? null,
      message: event.message ?? null
    };
    if (!current || parseTimestamp(next.happened_at) >= parseTimestamp(current.happened_at)) {
      byGateId.set(next.gate_id, next);
    }
  }
  return Array.from(byGateId.values()).sort(
    (a, b) => parseTimestamp(b.happened_at) - parseTimestamp(a.happened_at)
  );
}

export function gateIsPending(status: string): boolean {
  return status === "PENDING" || status === "DEFERRED" || status === "WAITING_APPROVAL";
}
