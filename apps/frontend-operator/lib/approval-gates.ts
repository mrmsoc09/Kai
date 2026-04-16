import type { CampaignDiagnosticsResponse, InferredApprovalGate } from "@/lib/types";
import type { ApprovalGateStatus } from "@/lib/types/approvals";

function parseTimestamp(raw: string | null): number {
  if (!raw) {
    return 0;
  }
  const t = Date.parse(raw);
  return Number.isNaN(t) ? 0 : t;
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

/**
 * Exhaustive set of known gate statuses.
 * Any value the backend sends that is not in this set is treated as PENDING
 * rather than propagated as an opaque string.
 */
const KNOWN_GATE_STATUSES = new Set<ApprovalGateStatus>([
  "PENDING",
  "APPROVED",
  "REJECTED",
  "DEFERRED",
  "CANCELED",
  "EXPIRED",
  "WAITING_APPROVAL"
]);

function inferStatus(eventType: string, payload: Record<string, unknown>): ApprovalGateStatus {
  const raw = (asString(payload.status) || asString(payload.to)).toUpperCase();
  if (raw && KNOWN_GATE_STATUSES.has(raw as ApprovalGateStatus)) {
    return raw as ApprovalGateStatus;
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

function normalizeEvidenceAttached(payload: Record<string, unknown>): string {
  const evidenceCount = payload.evidence_count;
  if (typeof evidenceCount === "number") {
    return `${evidenceCount} linked item(s)`;
  }
  const refs = payload.evidence_refs_json;
  if (Array.isArray(refs)) {
    return `${refs.length} linked item(s)`;
  }
  const artifacts = payload.artifact_refs_json;
  if (Array.isArray(artifacts)) {
    return `${artifacts.length} linked item(s)`;
  }
  return "No explicit evidence references";
}

function defaultGate(gateId: string, campaignId: string): InferredApprovalGate {
  return {
    gate_id: gateId,
    campaign_id: campaignId,
    phase_job_id: null,
    phase_name: null,
    status: "PENDING",
    source_event_type: "approval_gate.created",
    happened_at: null,
    requested_at: null,
    decided_at: null,
    request_title: `Approval Request ${gateId.slice(0, 8)}`,
    requested_action: "Execute gated mission phase",
    requesting_agent: "unknown",
    scope_target: `campaign:${campaignId}`,
    risk_band: "UNSPECIFIED",
    evidence_attached: "No explicit evidence references",
    intention: "",
    justification: "No policy basis provided",
    expected_impact: "Not supplied by current API payload",
    safety_constraints: "Not supplied by current API payload",
    reviewer_notes: "",
    message: null
  };
}

export function inferApprovalGates(
  campaignDiagnostics: CampaignDiagnosticsResponse
): InferredApprovalGate[] {
  const byGateId = new Map<string, InferredApprovalGate>();
  const events = [...campaignDiagnostics.recent_audit_events]
    .filter((event) => Boolean(event.approval_gate_id))
    .sort((a, b) => parseTimestamp(a.happened_at) - parseTimestamp(b.happened_at));

  for (const event of events) {
    if (!event.approval_gate_id) {
      continue;
    }
    const gateId = event.approval_gate_id;
    const payload = event.payload ?? {};
    const existing = byGateId.get(gateId) ?? defaultGate(gateId, campaignDiagnostics.campaign.id);
    const derivedStatus = inferStatus(event.event_type, payload);
    const phaseJobFromPayload = asString(payload.phase_job_id);
    const phaseNameFromPayload = asString(payload.phase_name) || asString(payload.phase);
    const requestedAtFromPayload = asString(payload.requested_at);
    const decidedAtFromPayload = asString(payload.decided_at);
    const requestTitle =
      asString(payload.request_title) ||
      asString(payload.gate_reason) ||
      asString(payload.reason) ||
      existing.request_title;
    const requestedAction =
      asString(payload.requested_action) ||
      asString(payload.action) ||
      existing.requested_action;
    const requestingAgent =
      asString(payload.requested_by) ||
      event.actor ||
      existing.requesting_agent;
    const scopeTarget =
      asString(payload.scope_target) ||
      asString(payload.target) ||
      asString(payload.affected_target) ||
      existing.scope_target;
    const riskBand =
      asString(payload.risk_band) ||
      asString(payload.risk_class) ||
      existing.risk_band;
    const intention =
      asString(payload.intention) ||
      asString(payload.declared_goal) ||
      asString(payload.intended_outcome) ||
      existing.intention;
    const justification =
      asString(payload.policy_basis) ||
      asString(payload.gate_reason) ||
      asString(payload.reason) ||
      existing.justification;
    const expectedImpact =
      asString(payload.expected_impact) ||
      asString(payload.impact_summary) ||
      existing.expected_impact;
    const safetyConstraints =
      asString(payload.safety_constraints) ||
      asString(payload.policy_basis) ||
      existing.safety_constraints;
    const reviewerNotes =
      asString(payload.operator_notes) ||
      asString(payload.reviewer_notes) ||
      existing.reviewer_notes;

    const next: InferredApprovalGate = {
      ...existing,
      phase_job_id: (event.phase_job_id ?? phaseJobFromPayload) || existing.phase_job_id,
      phase_name: phaseNameFromPayload || existing.phase_name,
      status: derivedStatus || existing.status,
      source_event_type: event.event_type,
      happened_at: event.happened_at ?? existing.happened_at,
      requested_at:
        requestedAtFromPayload ||
        existing.requested_at ||
        (event.event_type.includes("created") ? event.happened_at ?? null : null),
      decided_at:
        decidedAtFromPayload ||
        existing.decided_at ||
        (["APPROVED", "REJECTED", "CANCELED", "EXPIRED"].includes(derivedStatus)
          ? event.happened_at ?? null
          : null),
      request_title: requestTitle,
      requested_action: requestedAction,
      requesting_agent: requestingAgent,
      scope_target: scopeTarget,
      risk_band: riskBand.toUpperCase(),
      evidence_attached: normalizeEvidenceAttached(payload),
      intention,
      justification,
      expected_impact: expectedImpact,
      safety_constraints: safetyConstraints,
      reviewer_notes: reviewerNotes,
      message: event.message ?? existing.message
    };
    byGateId.set(gateId, next);
  }

  return Array.from(byGateId.values()).sort(
    (a, b) => parseTimestamp(b.happened_at) - parseTimestamp(a.happened_at)
  );
}

export function gateIsPending(status: ApprovalGateStatus): boolean {
  return status === "PENDING" || status === "DEFERRED" || status === "WAITING_APPROVAL";
}
