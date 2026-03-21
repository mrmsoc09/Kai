export interface Report {
  report_id: string;
  title: string;
  vulnerability_type: string;
  severity: string;
  target: string;
  summary: string;
  reproduction_steps: string[];
  http_requests: string[];
  http_responses: string[];
  exploit_chain: Record<string, unknown> | null;
  impact: string;
  remediation: string;
  references: string[];
  validation_evidence: string[];
  confidence_score: number;
  quality_score: number;
  duplicate_hash: string;
  duplicate_risk?: number;
  mission_id?: string | null;
  opportunity_id?: string | null;
  finding_id?: string | null;
  artifact_uri?: string | null;
  generated_by?: string | null;
  created_at: string;
  updated_at: string;
  rendered_markdown?: string;
}

export interface ReportListResponse {
  total: number;
  offset: number;
  limit: number;
  reports: Report[];
}

export interface MissionReportListResponse {
  mission_id: string;
  total: number;
  offset: number;
  limit: number;
  reports: Report[];
}

export interface GenerateReportInput {
  finding: Record<string, unknown>;
  exploit_chain?: Record<string, unknown> | null;
  artifacts?: Record<string, unknown>[];
  mission_id?: string;
  opportunity_id?: string;
  generated_by?: string;
  deduplicate?: boolean;
}

export interface GenerateReportResponse {
  deduplicated: boolean;
  report: Report;
}
