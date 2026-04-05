/**
 * Master Findings API Client
 * Handles aggregated and deduplicated findings from Faraday
 */

import { apiClient } from './client'

export interface MasterFinding {
  type: string
  value: string
  target: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  confidence: number
  confirmed_by: string[]
  source_tool: string
  raw_evidence: string
  context: Record<string, any>
  recommended_next_tools: string[]
}

export const masterFindingsApi = {
  getMasterFindings: (scanId: string) =>
    apiClient.get<MasterFinding[]>(
      `/scans/${scanId}/master-findings`
    ),

  exportFindings: (scanId: string, format: 'json' | 'csv' | 'pdf') =>
    apiClient.get(
      `/scans/${scanId}/master-findings/export`,
      { params: { format } }
    ),

  streamFindings: (scanId: string) =>
    apiClient.get(
      `/orchestrator/stream/${scanId}`,
      { responseType: 'stream' }
    ),
}
