/**
 * Tool and Crew Agent API Client
 * Handles all agent-related API calls
 */

import { apiClient } from './client'

export interface ToolAgent {
  name: string
  display_name: string
  category: string
  safety_classification: 'passive' | 'active' | 'intrusive'
  phase: number
  enabled: boolean
  timeout_seconds: number
  last_execution?: {
    scan_id: string
    started_at: string
    completed_at: string
    finding_count: number
    status: 'running' | 'complete' | 'error'
  }
  memory?: {
    confirmed_findings_count: number
    scan_count: number
  }
}

export interface AgentExecution {
  tool_name: string
  scan_id: string
  mission_id: string
  target: string
  status: 'queued' | 'running' | 'complete' | 'error'
  started_at: string
  completed_at?: string
  finding_count: number
  error?: string
}

export interface CrewAgent {
  name: string
  phase_group: 'A' | 'B' | 'C' | 'D'
  tool_agents: string[]
  status: 'idle' | 'running' | 'complete' | 'error'
  current_tool?: string
  findings_collected: number
  errors: string[]
}

export const agentsApi = {
  listAgents: () =>
    apiClient.get<ToolAgent[]>('/orchestrator/agents'),

  getAgentStatus: (toolName: string) =>
    apiClient.get<ToolAgent>(
      `/orchestrator/agents/${toolName}`
    ),

  getAgentExecutions: (toolName: string) =>
    apiClient.get<AgentExecution[]>(
      `/orchestrator/agents/${toolName}/executions`
    ),

  listCrewAgents: () =>
    apiClient.get<CrewAgent[]>('/orchestrator/agents/crew'),

  getCrewExecution: (missionId: string) =>
    apiClient.get<CrewAgent[]>(
      `/orchestrator/missions/${missionId}/crew-status`
    ),
}
