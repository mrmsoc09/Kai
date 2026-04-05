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

export interface ApprovalRequest {
  approval_id: string
  mission_id: string
  scan_id: string
  tool_name: string
  band: number
  action_description: string
  target: string
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  requested_at: string
  context: Record<string, any>
}

export interface ApprovalDecision {
  approval_id: string
  decision: 'approve' | 'reject'
  reason?: string
  decided_by: string
  decided_at: string
}

export interface PendingApprovals {
  items: ApprovalRequest[]
  total: number
}

export interface NLCommand {
  command: string
  context?: {
    mission_id?: string
    scan_id?: string
    target?: string
  }
}

export interface NLResponse {
  interpreted_as: string
  action_taken: string
  result: string
  follow_up_questions?: string[]
  approval_required?: boolean
  approval_id?: string
}

export interface ChatMessage {
  role: 'operator' | 'assistant' | 'system'
  content: string
  timestamp: string
  approval_request?: ApprovalRequest
}

export interface LLMUsage {
  provider: string
  model: string
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  estimated_cost_usd: number
  request_count: number
  error_count: number
  avg_latency_ms: number
  last_used: string
}

export interface LLMProvider {
  name: string
  status: 'active' | 'degraded' | 'unavailable'
  priority: number
  models: string[]
  daily_budget_usd?: number
  spent_today_usd?: number
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
    apiClient.get<LLMProvider[]>(
      '/orchestrator/llm/providers'
    ),

  getLLMUsage: () =>
    apiClient.get<LLMUsage[]>(
      '/orchestrator/llm/usage'
    ),

  getPendingApprovals: () =>
    apiClient.get<PendingApprovals>(
      '/orchestrator/scope-decisions/pending'
    ),

  submitApproval: (decision: ApprovalDecision) =>
    apiClient.post<void>(
      '/orchestrator/chat/approval',
      decision
    ),

  getApprovalHistory: () =>
    apiClient.get<ApprovalDecision[]>(
      '/orchestrator/scope-decisions'
    ),

  submitCommand: (cmd: NLCommand) =>
    apiClient.post<NLResponse>(
      '/orchestrator/commands/natural-language',
      cmd
    ),

  getChatHistory: () =>
    apiClient.get<ChatMessage[]>(
      '/orchestrator/chat/history'
    ),

  sendChatMessage: (message: string) =>
    apiClient.post<ChatMessage>(
      '/orchestrator/chat/message',
      { message }
    ),
}
