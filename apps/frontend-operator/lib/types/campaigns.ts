import type { AuditEvent } from "@/lib/types/api";

export type CampaignStatus =
  | "CREATED"
  | "READY"
  | "RUNNING"
  | "PAUSED"
  | "BLOCKED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELED";

export type BranchStatus =
  | "PENDING"
  | "READY"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "BLOCKED"
  | "COMPLETED"
  | "FAILED"
  | "CANCELED";

export type PhaseStatus =
  | "CREATED"
  | "QUEUED"
  | "RUNNING"
  | "WAITING_APPROVAL"
  | "BLOCKED"
  | "COMPLETED"
  | "FAILED"
  | "SKIPPED"
  | "CANCELED";

export type ApprovalStatus =
  | "PENDING"
  | "APPROVED"
  | "REJECTED"
  | "DEFERRED"
  | "EXPIRED"
  | "CANCELED";

export type CampaignScheduleSummary = {
  campaign_id: string;
  considered_jobs: number;
  queued_jobs: number;
  blocked_jobs: number;
  waiting_approval_jobs: number;
  created_approval_gates: number;
  dispatched_tool_executions: number;
};

export type CampaignListItem = {
  id: string;
  status: CampaignStatus;
  program_id: string;
  created_at: string | null;
  updated_at: string | null;
  branch_count?: number;
  phase_job_count?: number;
};

export type CampaignStatusResponse = {
  campaign: CampaignListItem;
  branches: Array<{
    id: string;
    branch_key: string;
    status: BranchStatus;
    depends_on_branch_id: string | null;
  }>;
  phase_jobs: Array<{
    id: string;
    phase_name: string;
    phase_order: number;
    status: PhaseStatus;
    depends_on_job_id: string | null;
    approval_required: boolean;
    worker_task_id: string | null;
  }>;
};

export type CampaignStartRequest = {
  initiated_by: string;
  declared_goal: string;
  declared_reason?: string;
  policy_basis?: string;
  program_id?: string;
  program_name?: string;
  program_key?: string;
  target?: string;
  campaign_name?: string;
  initial_branch_key?: string;
  initial_branch_name?: string;
};

export type CampaignStartResponse = {
  campaign_id: string;
  program_id: string;
  branch_id: string;
  campaign_status: CampaignStatus;
  branch_status: BranchStatus;
  scheduler: CampaignScheduleSummary;
  idempotent_replay: boolean;
  phase_jobs: Array<{
    id: string;
    phase_name: string;
    phase_order: number;
    status: PhaseStatus;
    approval_required: boolean;
    worker_task_id: string | null;
  }>;
};

export type CampaignDiagnosticsResponse = {
  campaign: {
    id: string;
    status: CampaignStatus;
    created_at: string | null;
    updated_at: string | null;
    blocked_reason: string | null;
    last_error: string | null;
  };
  counts: {
    branches: number;
    phase_jobs: number;
    tool_executions: number;
    approval_gates: number;
    artifacts: number;
    observations: number;
    submission_drafts: number;
  };
  status_breakdown: Record<string, Record<string, number>>;
  phase_links: Array<{
    phase_job_id: string;
    phase_name: string;
    phase_status: PhaseStatus;
    worker_task_id: string | null;
    depends_on_job_id: string | null;
  }>;
  recent_audit_events: AuditEvent[];
};

export type CampaignCorrelationResponse = {
  campaign_id: string;
  processed: number;
  created_findings: number;
  attached_existing: number;
  context_only: number;
  duplicates: number;
  evidence_created: number;
};

export type CampaignApprovalDecisionResponse = {
  gate_id: string;
  campaign_id: string;
  status: ApprovalStatus;
  decided_by: string | null;
  decided_at: string | null;
  scheduler: CampaignScheduleSummary | null;
};
