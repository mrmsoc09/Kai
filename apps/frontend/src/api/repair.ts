/**
 * Repair Pipeline API Client
 * Provides functions to interact with vulnerability repair endpoints
 */

import { apiClient } from './client';

export interface RepairPipelineResult {
  target: string;
  vulnerabilities_found: number;
  repairs_generated: number;
  repairs_applied: number;
  total_cost_cents: number;
  total_cost_usd: number;
  local_percentage: number;
  paid_percentage: number;
  execution_time_ms: number;
  post_review_report: PostReviewReport;
  timestamp: string;
}

export interface PostReviewReport {
  header: string;
  timestamp: string;
  target: string;
  summary: {
    vulnerabilities_found: number;
    repairs_applied: number;
    total_cost_usd: number;
    local_model_usage: number;
    paid_api_usage: number;
  };
  changes: Array<{
    file: string;
    vulnerability: string;
    severity: string;
    before_code: string;
    after_code: string;
    validation: {
      is_valid: boolean;
      confidence: number;
      issues: string[];
    };
    rollback_command: string;
  }>;
  cost_breakdown: {
    discovery_cost: number;
    analysis_cost: number;
    repair_cost: number;
    validation_cost: number;
  };
  next_steps: string[];
}

export interface RepairPipelineHealth {
  ok: boolean;
  repair_pipeline_available: boolean;
  cli_tools: {
    claude_code: boolean;
    codex: boolean;
    gemini: boolean;
  };
  specialized_agents: {
    osint_agent: boolean;
    reasoning_agent: boolean;
    repair_agent: boolean;
  };
  error?: string;
}

/**
 * Execute full vulnerability repair pipeline
 */
export const discoverAndRepair = async (
  target: string,
  autoRepair: boolean = true,
  sessionId?: string
): Promise<RepairPipelineResult> => {
  const response = await apiClient.post('/findings/repair/discover-and-repair', {
    target,
    auto_repair: autoRepair,
    session_id: sessionId,
  });
  return response.data;
};

/**
 * Check repair pipeline health and CLI tool availability
 */
export const getRepairPipelineHealth = async (): Promise<RepairPipelineHealth> => {
  const response = await apiClient.get('/findings/repair/health');
  return response.data;
};
