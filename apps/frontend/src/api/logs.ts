
import api from './client'
import type { DecisionTraceEntry, ReasoningSummary, EvidenceLink, KnowledgeDeltaEntry, LogIndex, LogType, LogCategory } from './types'

export async function getLogIndex(run_id: string): Promise<LogIndex> {
  const r = await api.get(`/logs/${run_id}/index`)
  return r.data
}
export async function getDecisionTrace(run_id: string): Promise<DecisionTraceEntry[]> {
  const r = await api.get(`/logs/${run_id}/decision_trace`)
  return r.data
}
export async function getSummary(run_id: string): Promise<ReasoningSummary> {
  const r = await api.get(`/logs/${run_id}/summary`)
  return r.data
}
export async function getEvidenceLinks(run_id: string): Promise<EvidenceLink[]> {
  const r = await api.get(`/logs/${run_id}/evidence_links`)
  return r.data
}
export async function getKnowledgeDelta(run_id: string): Promise<KnowledgeDeltaEntry[]> {
  const r = await api.get(`/logs/${run_id}/knowledge_delta`)
  return r.data
}
export async function searchLogs(run_id: string, q?: string, category?: LogCategory) : Promise<DecisionTraceEntry[]> {
  const r = await api.get('/logs/search', { params: { run_id, q, category }})
  return r.data
}
