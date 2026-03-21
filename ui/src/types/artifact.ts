export interface Artifact {
  id: string;
  campaign_id: string;
  branch_id?: string | null;
  phase_job_id?: string | null;
  tool_execution_id?: string | null;
  finding_id?: string | null;
  report_id?: string | null;
  intention_id?: string | null;
  artifact_type: string;
  uri: string;
  content_hash?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  description?: string | null;
  policy_class?: string | null;
  details_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export type ArtifactContent = string | Record<string, unknown> | Array<unknown>;
