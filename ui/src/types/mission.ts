export type MissionStatus = 'created' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled' | 'unknown';
export type MissionExecutionMode = 'live' | 'graph_only' | 'tool_mock' | 'replay' | string;

export interface MissionResponse {
  mission_id: string;
  workflow_id: string;
  program_id: string;
  state: string;
  execution_mode: MissionExecutionMode;
  phase: string;
  active_node: string;
  progress: number;
  error?: string | null;
}

export interface Mission {
  id: string;
  workflowId: string;
  programId: string;
  state: MissionStatus;
  executionMode: MissionExecutionMode;
  phase: string;
  activeNode: string;
  progress: number;
  error: string | null;
}

export type MissionNodeStatus = 'pending' | 'running' | 'completed' | 'failed' | 'blocked';

export interface MissionGraphNode {
  id: string;
  label: string;
  type: string;
  agentClass: string;
  clusterId: string;
  status: MissionNodeStatus;
  isActive: boolean;
  lastExecuted: string | null;
}

export interface MissionGraphEdge {
  id: string;
  source: string;
  target: string;
  condition?: string | null;
  label?: string | null;
}

export interface MissionGraphResponse {
  mission_id: string;
  workflow_id: string;
  program_id: string;
  phase: string;
  execution_status: string;
  nodes: Array<{
    id: string;
    label: string;
    type: string;
    agent_class: string;
    cluster_id: string;
  }>;
  edges: Array<{
    id: string;
    source: string;
    target: string;
    condition?: string | null;
    label?: string | null;
  }>;
  node_state: Record<string, { status: string; last_executed?: string | null }>;
  progress: number;
  error?: string | null;
}

export interface MissionGraphData {
  missionId: string;
  workflowId: string;
  programId: string;
  phase: string;
  executionStatus: MissionStatus;
  progress: number;
  error: string | null;
  nodes: MissionGraphNode[];
  edges: MissionGraphEdge[];
}

export interface MissionTimelineEventResponse {
  id: string;
  timestamp: string;
  event_type: string;
  actor?: string | null;
  message?: string | null;
  phase_job_id?: string | null;
  tool_execution_id?: string | null;
  approval_gate_id?: string | null;
  details?: Record<string, unknown>;
}

export type MissionTimelineCategory = 'governance' | 'lifecycle' | 'artifact' | 'error' | 'operation';
export type TimelineSeverity = 'info' | 'warning' | 'error';

export interface MissionTimelineEvent {
  id: string;
  timestamp: string;
  eventType: string;
  actor: string | null;
  message: string;
  category: MissionTimelineCategory;
  severity: TimelineSeverity;
  details: Record<string, unknown>;
}

export interface MissionEventMessage {
  type?: string;
  data?: Record<string, unknown>;
  mission_id?: string;
  event_type?: string;
  timestamp?: string;
  detail?: Record<string, unknown>;
}
