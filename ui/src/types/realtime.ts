export type RealtimeEventCategory = 'lifecycle' | 'node' | 'governance' | 'artifact' | 'simulation' | 'operation';

export interface RealtimeMissionEvent {
  schema_version: string;
  event_id: string;
  event_type: string;
  timestamp: string;
  tenant_id: string | null;
  mission_id: string;
  workflow_id: string;
  program_id: string;
  node_id: string | null;
  phase: string | null;
  status: string | null;
  summary: string;
  detail: Record<string, unknown>;
  artifact_id: string | null;
  approval_id: string | null;
  category: RealtimeEventCategory;
}

export interface RealtimeEnvelope {
  type: string;
  data?: unknown;
}

export interface RealtimeRecentMissionEventsResponse {
  mission_id: string;
  events: RealtimeMissionEvent[];
}

export interface OpportunityActionCapabilities {
  approve: boolean;
  reject: boolean;
  execute: boolean;
  reason: string;
  requires_role: string;
}
