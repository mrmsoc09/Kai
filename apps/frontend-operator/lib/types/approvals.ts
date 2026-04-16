/**
 * All states a gate can be in over its lifecycle.
 * Narrowed from `string` to prevent silent drift when the backend emits an
 * unexpected status value — unknown values are caught at inference time and
 * fall back to "PENDING" rather than propagating opaque strings.
 */
export type ApprovalGateStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "DEFERRED"
  | "CANCELED"
  | "EXPIRED"
  | "WAITING_APPROVAL";

export type InferredApprovalGate = {
  gate_id: string;
  campaign_id: string;
  phase_job_id: string | null;
  phase_name: string | null;
  status: ApprovalGateStatus;
  source_event_type: string;
  happened_at: string | null;
  requested_at: string | null;
  decided_at: string | null;
  request_title: string;
  requested_action: string;
  requesting_agent: string;
  scope_target: string;
  risk_band: string;
  evidence_attached: string;
  intention: string;
  justification: string;
  expected_impact: string;
  safety_constraints: string;
  reviewer_notes: string;
  message: string | null;
};
