import type { AuditEvent } from "@/lib/types/api";

export type FindingStatus =
  | "NEW"
  | "IN_REVIEW"
  | "HIL_APPROVED"
  | "REJECTED"
  | "DUPLICATE"
  | "RESOLVED"
  | "SUBMITTED";

export type FindingReviewQueueResponse = {
  count: number;
  items: FindingQueueItem[];
};

export type FindingQueueItem = {
  finding_id: string;
  draft_id: string;
  campaign_id: string;
  branch_id: string | null;
  program: string;
  asset: string;
  title: string;
  finding_status: FindingStatus;
  readiness_status: string;
  evidence_count: number;
  observation_summary: {
    count: number;
    items: Array<{
      id: string;
      category: string | null;
      title: string | null;
      summary: string | null;
    }>;
  };
};

export type FindingDiagnosticsResponse = {
  finding: {
    id: string;
    program: string;
    asset: string;
    title: string;
    status: FindingStatus;
    severity: string | null;
    scope_json: Record<string, unknown>;
  };
  counts: {
    evidence: number;
    observations: number;
    artifacts: number;
    submission_drafts: number;
    audit_events: number;
  };
  submission_drafts: Array<{
    id: string;
    campaign_id: string;
    branch_id: string | null;
    status: string;
    prepared_by: string | null;
    approved_by: string | null;
    approved_at: string | null;
  }>;
  recent_observations: Array<{
    id: string;
    category: string | null;
    title: string | null;
    summary: string | null;
    tool_execution_id: string | null;
    phase_job_id: string | null;
  }>;
  recent_audit_events: AuditEvent[];
};

export type FindingReviewActionRequest = {
  action: "APPROVE" | "REJECT" | "NEEDS_MORE_EVIDENCE" | "DUPLICATE" | "SUPPRESS";
  reviewer_id: string;
  review_notes?: string;
  duplicate_of_finding_id?: string;
};

export type FindingReviewActionResponse = {
  finding_id: string;
  finding_status: FindingStatus;
  submission_draft_id: string;
  submission_draft_status: string;
  campaign_id: string;
  review_timestamp: string;
};

export type PrepareSubmissionResponse = {
  finding_id: string;
  submission_draft_id: string;
  submission_draft_status: string;
  package_json: Record<string, unknown>;
};

export type SubmissionExportResponse = {
  provider: string;
  finding_id: string;
  submission_draft_id: string;
  ready: boolean;
  state: string;
  missing_fields: string[];
  warnings: string[];
  payload: Record<string, unknown>;
  stored: boolean;
  exported_at: string | null;
};
