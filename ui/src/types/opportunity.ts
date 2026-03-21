export interface Opportunity {
  id: string;
  name: string;
  organization: string;
  platform: string;
  access_type: string;
  program_url: string;
  scope_url: string;
  scope_summary: string;
  scope_domains: string[];
  max_payout_usd: number;
  min_payout_usd: number;
  vdp_only: boolean;
  response_sla_days: number;
  tags: string[];
  vuln_types: string[];
  priority_score: number;
  is_public: boolean;
  payout_label: string;
  notes: string;
  credential_requirements: Array<{
    kind: string;
    label: string;
    signup_url: string;
    notes: string;
    required: boolean;
  }>;
  needs_credentials: boolean;
  status?: 'proposed' | 'approved' | 'rejected' | 'executing' | 'completed' | 'failed' | 'cancelled' | string;
  approval_state?: 'pending' | 'approved' | 'rejected' | string;
  approval_reason?: string | null;
  rejection_reason?: string | null;
  execution_metadata?: Record<string, unknown>;
  source_memory_id?: string | null;
  source_pattern_id?: string | null;
  source_type?: string | null;
  source_object_id?: string | null;
  candidate_targets?: string[];
  expansion_candidates?: Array<{
    target: string;
    similarity_score: number;
    confidence: number;
    memory_match_strength: number;
    duplicate_risk: number;
    target_importance: number;
    expected_report_quality: number;
    expansion_score: number;
    estimated_yield: number;
    risk_band: string;
    matching_factors: string[];
    rationale: string;
  }>;
  approved_targets?: string[];
  rejected_targets?: string[];
  target_batches?: Array<{
    batch_id: string;
    targets: string[];
    expected_yield: number;
    risk_band: string;
    rationale: string;
  }>;
  expansion_rationale?: string;
  expansion_score?: number;
  expected_report_quality?: number;
  recommended_execution_order?: string[];
  linked_mission_count?: number;
  linked_report_count?: number;
  decision_summary?: string | null;
  chain_summary?: {
    chain_count?: number;
    chain_bonus?: number;
    chain_ids?: string[];
    has_chain?: boolean;
  } | null;
  confidence_score?: number;
  estimated_yield?: number;
  expected_yield?: number;
  duplicate_risk?: number;
  created_at?: string;
  updated_at?: string;
  created_by?: string | null;
}

export interface OpportunityListResponse {
  total: number;
  offset: number;
  limit: number;
  opportunities: Opportunity[];
}

export interface OpportunityRankedResponse {
  count: number;
  opportunities: Opportunity[];
}

export interface OpportunityDecisionInput {
  reason?: string;
  approved_targets?: string[];
  rejected_targets?: string[];
  batch_ids?: string[];
}

export interface OpportunityExecuteInput {
  reason?: string;
  execution_mode?: string;
  max_targets?: number;
}

export interface OpportunityExpandInput {
  vuln_type?: string;
  candidate_targets?: string[];
}
