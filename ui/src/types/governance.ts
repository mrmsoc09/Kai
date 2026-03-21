export type ApprovalStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'DEFERRED' | 'EXPIRED' | 'CANCELED';

export interface ApprovalGate {
  id: string;
  campaign_id: string;
  branch_id?: string | null;
  phase_job_id?: string | null;
  intention_id?: string | null;
  status: ApprovalStatus;
  gate_reason: string;
  policy_basis?: string | null;
  risk_class?: string | null;
  requested_by: string;
  requested_at: string;
  decided_by?: string | null;
  decided_at?: string | null;
  expires_at?: string | null;
  canceled_at?: string | null;
  canceled_by?: string | null;
  operator_notes?: string | null;
  decision_payload_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type ApprovalDecision = 'approve' | 'reject' | 'cancel';
