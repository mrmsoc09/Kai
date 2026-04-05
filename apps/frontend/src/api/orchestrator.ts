/**
 * Midnight Orchestrator API Client
 * Manages API budget, quota, and signal tracking
 */

import { apiClient } from './client'

export interface QuotaStatus {
  source: string
  env_var: string
  daily_limit: number
  remaining: number
  used: number
  has_budget: boolean
  signal_score?: number
  reset_time: string
}

export interface OrchestratorStatus {
  last_run: string
  next_run: string
  scans_planned: number
  sources: QuotaStatus[]
  spiderfoot_modules: string[]
  budget_summary_path: string
}

export const orchestratorApi = {
  getStatus: () =>
    apiClient.get<OrchestratorStatus>(
      '/orchestrator/quota'
    ),

  getSignalHistory: () =>
    apiClient.get<Record<string, any[]>>(
      '/orchestrator/quota/signals'
    ),

  getHealth: () =>
    apiClient.get<{ status: string }>(
      '/orchestrator/health'
    ),

  getProviders: () =>
    apiClient.get<any[]>(
      '/orchestrator/llm/providers'
    ),

  getLLMUsage: () =>
    apiClient.get<any>(
      '/orchestrator/llm/usage'
    ),
}
