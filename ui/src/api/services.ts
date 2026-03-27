import { apiClient, request } from './client';
import type {
  ApprovalGate,
  ApprovalStatus,
  Artifact,
  ArtifactContent,
  AuthTokenResponse,
  AuthUser,
  IntelligenceMemory,
  IntelligenceMemoryListResponse,
  IntelligenceRelationshipsResponse,
  IntelligenceStatsResponse,
  LoginInput,
  Mission,
  MissionGraphData,
  MissionGraphResponse,
  MissionNodeStatus,
  MissionResponse,
  MissionStatus,
  MissionTimelineEvent,
  MissionTimelineEventResponse,
  Opportunity,
  OpportunityActionCapabilities,
  OpportunityDecisionInput,
  OpportunityExpandInput,
  OpportunityExecuteInput,
  OpportunityListResponse,
  OpportunityRankedResponse,
  ScanQueueSettings,
  RealtimeMissionEvent,
  RealtimeRecentMissionEventsResponse,
  Report,
  ReportListResponse,
  MissionReportListResponse,
  GenerateReportInput,
  GenerateReportResponse,
  SimulationCompareRequest,
  SimulationCompareResponse,
  SimulationRequest,
  SimulationResult,
  SimulationScenariosResponse,
  SystemStatus,
} from '../types';
import { extractRealtimeMissionEvent } from '../lib/realtime/missionEventReducer';

const nodeStatusList: MissionNodeStatus[] = ['pending', 'running', 'completed', 'failed', 'blocked'];
const missionStatuses: MissionStatus[] = ['created', 'running', 'paused', 'completed', 'failed', 'cancelled', 'unknown'];
interface AuthUserResponse {
  id: string;
  username: string;
  email?: string | null;
  full_name?: string | null;
  role: AuthUser['role'];
  tenant_id: string;
  is_active: boolean;
  is_superuser: boolean;
}

const asMissionStatus = (value: string): MissionStatus => {
  const normalized = value.toLowerCase();
  if (missionStatuses.includes(normalized as MissionStatus)) {
    return normalized as MissionStatus;
  }
  return 'unknown';
};

const asNodeStatus = (value: string): MissionNodeStatus => {
  const normalized = value.toLowerCase();
  if (nodeStatusList.includes(normalized as MissionNodeStatus)) {
    return normalized as MissionNodeStatus;
  }
  return 'pending';
};

const toMission = (payload: MissionResponse): Mission => ({
  id: payload.mission_id,
  workflowId: payload.workflow_id,
  programId: payload.program_id,
  state: asMissionStatus(payload.state),
  executionMode: payload.execution_mode,
  phase: payload.phase,
  activeNode: payload.active_node,
  progress: payload.progress ?? 0,
  error: payload.error ?? null,
});

const normalizeTimelineMessage = (event: MissionTimelineEventResponse): string => {
  if (event.message) {
    return event.message;
  }

  if (event.event_type) {
    return event.event_type.replace(/_/g, ' ');
  }

  return 'Mission event';
};

const classifyTimeline = (event: MissionTimelineEventResponse): Pick<MissionTimelineEvent, 'category' | 'severity'> => {
  const source = `${event.event_type} ${event.message ?? ''}`.toLowerCase();
  if (source.includes('approval') || source.includes('governance')) {
    return { category: 'governance', severity: event.event_type.toLowerCase().includes('reject') ? 'warning' : 'info' };
  }
  if (source.includes('artifact')) {
    return { category: 'artifact', severity: 'info' };
  }
  if (source.includes('fail') || source.includes('error') || source.includes('blocked')) {
    return { category: 'error', severity: 'error' };
  }
  if (source.includes('mission') || source.includes('phase') || source.includes('lifecycle')) {
    return { category: 'lifecycle', severity: 'info' };
  }
  return { category: 'operation', severity: 'info' };
};

const toTimelineEvent = (payload: MissionTimelineEventResponse): MissionTimelineEvent => {
  const classification = classifyTimeline(payload);

  return {
    id: payload.id,
    timestamp: payload.timestamp,
    eventType: payload.event_type,
    actor: payload.actor ?? null,
    message: normalizeTimelineMessage(payload),
    category: classification.category,
    severity: classification.severity,
    details: payload.details ?? {},
  };
};

const asApprovalStatus = (status: ApprovalStatus): string => status;

export const authService = {
  login: (input: LoginInput): Promise<AuthTokenResponse> => {
    const form = new URLSearchParams();
    form.set('username', input.username);
    form.set('password', input.password);

    return request<AuthTokenResponse>({
      method: 'POST',
      url: '/auth/token',
      data: form.toString(),
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
  },
  me: (): Promise<AuthUser> =>
    request<AuthUserResponse>({
      method: 'GET',
      url: '/auth/users/me',
    }).then((payload) => ({
      id: payload.id,
      username: payload.username,
      email: payload.email ?? null,
      fullName: payload.full_name ?? null,
      role: payload.role,
      tenantId: payload.tenant_id,
      isActive: payload.is_active,
      isSuperuser: payload.is_superuser,
    })),
  setInitialPassword: (bootstrapToken: string, newPassword: string): Promise<{ ok: boolean }> =>
    request<{ ok: boolean }>({
      method: 'POST',
      url: '/auth/users/set-initial-password',
      data: {
        new_password: newPassword,
      },
      headers: {
        Authorization: `Bearer ${bootstrapToken}`,
      },
    }),
};

export const missionService = {
  create: (payload: {
    workflow_id: string;
    program_id: string;
    mission_name?: string;
    execution_mode?: string;
    run_config?: Record<string, unknown>;
    graph_spec?: Record<string, unknown>;
  }): Promise<{ mission_id: string; workflow_id: string; program_id: string; state: string; execution_mode: string; phase: string; active_node: string; progress: number; error?: string | null }> =>
    request<{ mission_id: string; workflow_id: string; program_id: string; state: string; execution_mode: string; phase: string; active_node: string; progress: number; error?: string | null }>({
      method: 'POST',
      url: '/missions/',
      data: payload,
    }),
  list: (): Promise<Mission[]> =>
    request<MissionResponse[]>({
      method: 'GET',
      url: '/missions/',
    }).then((rows) => rows.map(toMission)),
  getStatus: (missionId: string): Promise<Mission> =>
    request<MissionResponse>({
      method: 'GET',
      url: `/missions/${missionId}`,
    }).then(toMission),
  getGraph: (missionId: string): Promise<MissionGraphData> =>
    request<MissionGraphResponse>({
      method: 'GET',
      url: `/missions/${missionId}/graph`,
    }).then((payload) => ({
      missionId: payload.mission_id,
      workflowId: payload.workflow_id,
      programId: payload.program_id,
      phase: payload.phase,
      executionStatus: asMissionStatus(payload.execution_status),
      progress: payload.progress,
      error: payload.error ?? null,
      nodes: payload.nodes.map((node) => {
        const state = payload.node_state[node.id];
        const status = asNodeStatus(state?.status ?? 'pending');
        return {
          id: node.id,
          label: node.label || node.id,
          type: node.type,
          agentClass: node.agent_class,
          clusterId: node.cluster_id,
          status,
          isActive: status === 'running',
          lastExecuted: state?.last_executed ?? null,
        };
      }),
      edges: payload.edges.map((edge) => ({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        condition: edge.condition ?? null,
        label: edge.label ?? null,
      })),
    })),
  getTimeline: (missionId: string): Promise<MissionTimelineEvent[]> =>
    request<MissionTimelineEventResponse[]>({
      method: 'GET',
      url: `/events/mission/${missionId}/timeline`,
    }).then((rows) =>
      rows
        .map(toTimelineEvent)
        .sort((left, right) => new Date(right.timestamp).getTime() - new Date(left.timestamp).getTime()),
    ),
  start: (missionId: string): Promise<{ status: string; mission_id?: string }> =>
    request<{ status: string; mission_id?: string }>({
      method: 'POST',
      url: `/missions/${missionId}/start`,
    }),
  stop: (missionId: string): Promise<{ status: string; mission_id?: string }> =>
    request<{ status: string; mission_id?: string }>({
      method: 'POST',
      url: `/missions/${missionId}/stop`,
    }),
  replay: (missionId: string): Promise<{ status: string; mission_id?: string }> =>
    request<{ status: string; mission_id?: string }>({
      method: 'POST',
      url: `/missions/${missionId}/replay`,
    }),
};

export const governanceService = {
  list: (status: ApprovalStatus = 'PENDING'): Promise<ApprovalGate[]> =>
    request<ApprovalGate[]>({
      method: 'GET',
      url: '/approvals/',
      params: { status: asApprovalStatus(status) },
    }),
  getById: (gateId: string): Promise<ApprovalGate> =>
    request<ApprovalGate>({
      method: 'GET',
      url: `/approvals/${gateId}`,
    }),
  approve: (gateId: string, notes?: string): Promise<ApprovalGate> =>
    request<ApprovalGate>({
      method: 'POST',
      url: `/approvals/${gateId}/approve`,
      params: notes ? { notes } : undefined,
    }),
  reject: (gateId: string, notes?: string): Promise<ApprovalGate> =>
    request<ApprovalGate>({
      method: 'POST',
      url: `/approvals/${gateId}/reject`,
      params: notes ? { notes } : undefined,
    }),
  cancel: (gateId: string, notes?: string): Promise<ApprovalGate> =>
    request<ApprovalGate>({
      method: 'POST',
      url: `/approvals/${gateId}/cancel`,
      params: notes ? { notes } : undefined,
    }),
};

export const artifactService = {
  listByMission: (missionId: string): Promise<Artifact[]> =>
    request<Artifact[]>({
      method: 'GET',
      url: `/artifacts/mission/${missionId}`,
    }),
  getMetadata: (artifactId: string): Promise<Artifact> =>
    request<Artifact>({
      method: 'GET',
      url: `/artifacts/${artifactId}`,
    }),
  getContent: (artifactId: string): Promise<ArtifactContent> =>
    request<ArtifactContent>({
      method: 'GET',
      url: `/artifacts/${artifactId}/content`,
    }),
};

export const simulationService = {
  listScenarios: (): Promise<SimulationScenariosResponse> =>
    request<SimulationScenariosResponse>({
      method: 'GET',
      url: '/simulation/scenarios',
    }),
  run: (payload: SimulationRequest): Promise<SimulationResult> =>
    request<SimulationResult>({
      method: 'POST',
      url: '/simulation/run',
      data: payload,
    }),
  compare: (payload: SimulationCompareRequest): Promise<SimulationCompareResponse> =>
    request<SimulationCompareResponse>({
      method: 'POST',
      url: '/simulation/compare',
      data: payload,
    }),
};

export const intelligenceService = {
  listMemory: (params?: {
    scope?: string;
    memory_type?: string;
    validation_status?: string;
    domain?: string;
    search?: string;
    min_confidence?: number;
    limit?: number;
    offset?: number;
  }): Promise<IntelligenceMemoryListResponse> =>
    request<IntelligenceMemoryListResponse>({
      method: 'GET',
      url: '/intel/memory',
      params,
    }),
  getMemory: (memoryId: string): Promise<IntelligenceMemory> =>
    request<IntelligenceMemory>({
      method: 'GET',
      url: `/intel/memory/${memoryId}`,
    }),
  getRelationships: (memoryId: string): Promise<IntelligenceRelationshipsResponse> =>
    request<IntelligenceRelationshipsResponse>({
      method: 'GET',
      url: `/intel/memory/${memoryId}/relationships`,
    }),
  getStats: (): Promise<IntelligenceStatsResponse> =>
    request<IntelligenceStatsResponse>({
      method: 'GET',
      url: '/intel/memory/stats',
    }),
};

export const opportunityService = {
  list: (params?: {
    platform?: string;
    access_type?: string;
    min_payout?: number;
    tag?: string;
    search?: string;
    public_only?: boolean;
    sort_by?: 'score' | 'payout' | 'name';
    limit?: number;
    offset?: number;
  }): Promise<OpportunityListResponse> =>
    request<OpportunityListResponse>({
      method: 'GET',
      url: '/opportunities',
      params,
    }),
  ranked: (limit = 50, publicOnly = false): Promise<OpportunityRankedResponse> =>
    request<OpportunityRankedResponse>({
      method: 'GET',
      url: '/opportunities/ranked',
      params: { limit, public_only: publicOnly },
    }),
  getById: (opportunityId: string): Promise<Opportunity> =>
    request<Opportunity>({
      method: 'GET',
      url: `/opportunities/${opportunityId}`,
    }),
  getActionCapabilities: (): Promise<OpportunityActionCapabilities> =>
    request<OpportunityActionCapabilities>({
      method: 'GET',
      url: '/opportunities/actions/capabilities',
    }),
  approve: (opportunityId: string, payload?: OpportunityDecisionInput): Promise<Opportunity> =>
    request<Opportunity>({
      method: 'POST',
      url: `/opportunities/${opportunityId}/approve`,
      data: payload ?? {},
    }),
  reject: (opportunityId: string, payload?: OpportunityDecisionInput): Promise<Opportunity> =>
    request<Opportunity>({
      method: 'POST',
      url: `/opportunities/${opportunityId}/reject`,
      data: payload ?? {},
    }),
  execute: (opportunityId: string, payload?: OpportunityExecuteInput): Promise<Opportunity> =>
    request<Opportunity>({
      method: 'POST',
      url: `/opportunities/${opportunityId}/execute`,
      data: payload ?? {},
    }),
  expand: (opportunityId: string, payload?: OpportunityExpandInput): Promise<Opportunity> =>
    request<Opportunity>({
      method: 'POST',
      url: `/opportunities/${opportunityId}/expand`,
      data: payload ?? {},
    }),
  getScanQueueSettings: (): Promise<ScanQueueSettings> =>
    request<{ min_concurrent: number; max_concurrent: number }>({
      method: 'GET',
      url: '/opportunities/scan-queue/settings',
    }).then((payload) => ({
      minConcurrent: payload.min_concurrent,
      maxConcurrent: payload.max_concurrent,
    })),
  setScanQueueSettings: (payload: ScanQueueSettings): Promise<ScanQueueSettings> =>
    request<{ min_concurrent: number; max_concurrent: number }>({
      method: 'PUT',
      url: '/opportunities/scan-queue/settings',
      data: {
        min_concurrent: payload.minConcurrent,
        max_concurrent: payload.maxConcurrent,
      },
    }).then((response) => ({
      minConcurrent: response.min_concurrent,
      maxConcurrent: response.max_concurrent,
    })),
};

export const workflowService = {
  create: (payload: { opportunity_id: string; notes?: string }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: '/workflows',
      data: payload,
    }),
  list: (params?: {
    status?: string;
    platform?: string;
    opportunity_id?: string;
    created_by?: string;
    limit?: number;
    offset?: number;
  }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/workflows',
      params,
    }),
};

export const reportService = {
  list: (params?: {
    severity?: string;
    min_confidence?: number;
    target?: string;
    mission_id?: string;
    opportunity_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<ReportListResponse> =>
    request<ReportListResponse>({
      method: 'GET',
      url: '/reports',
      params,
    }),
  getById: (reportId: string): Promise<Report> =>
    request<Report>({
      method: 'GET',
      url: `/reports/${reportId}`,
    }),
  listByMission: (missionId: string, limit = 200, offset = 0): Promise<MissionReportListResponse> =>
    request<MissionReportListResponse>({
      method: 'GET',
      url: `/reports/mission/${missionId}`,
      params: { limit, offset },
    }),
  generate: (payload: GenerateReportInput): Promise<GenerateReportResponse> =>
    request<GenerateReportResponse>({
      method: 'POST',
      url: '/reports/generate',
      data: payload,
    }),
  exportFile: async (reportId: string, format: 'markdown' | 'json'): Promise<{ blob: Blob; filename: string }> => {
    const response = await apiClient.request<Blob>({
      method: 'GET',
      url: `/reports/${reportId}/export`,
      params: { format },
      responseType: 'blob',
    });

    const disposition = response.headers['content-disposition'] ?? '';
    const filenameMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
    const filename = filenameMatch?.[1] ?? `${reportId}.${format === 'markdown' ? 'md' : 'json'}`;
    return { blob: response.data, filename };
  },
};

export const systemService = {
  status: (): Promise<SystemStatus> =>
    request<SystemStatus>({
      method: 'GET',
      url: '/system/status',
    }),
};

export const vaultService = {
  importKeyFile: async (file: File): Promise<Record<string, unknown>> => {
    const form = new FormData();
    form.append('file', file);
    const response = await apiClient.request<Record<string, unknown>>({
      method: 'POST',
      url: '/keys/import',
      data: form,
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
  getProviderCatalog: (market?: string): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/hil-api/providers/catalog',
      params: market ? { market } : undefined,
    }),
  storeProviderKey: (
    providerId: string,
    payload: {
      api_key?: string;
      token?: string;
      client_id?: string;
      client_secret?: string;
      notes?: string;
      rate_limit?: string;
      tos_version?: string;
    },
  ): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: `/hil-api/providers/${encodeURIComponent(providerId)}/key`,
      data: payload,
    }),
};

export const orchestrationService = {
  getHealth: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/health',
    }),
  getAgents: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/agents',
    }),
  getWorkflows: (limit = 30): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/workflows',
      params: { limit },
    }),
  createHuntWorkflow: (target: string): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: '/api/v1/orchestration/workflows/hunt',
      params: { target },
      data: {},
    }),
  getLlmUsage: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/llm/usage',
    }),
  getPluginInfo: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/plugin/info',
    }),
  sendChatMessage: (payload: { content: string; session_id?: string; context?: Record<string, unknown> }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: '/api/v1/orchestration/chat/message',
      data: payload,
    }),
  getChatHistory: (sessionId: string, limit = 80): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/chat/history',
      params: { session_id: sessionId, limit },
    }),
  respondToApproval: (payload: { approval_id: string; decision: 'approved' | 'rejected'; reason?: string }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: '/api/v1/orchestration/chat/approval',
      data: payload,
    }),
  getRelayLogs: (limit = 50): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/orchestration/logs',
      params: { limit },
    }),

  // --- 5-tier dispatch and quota methods ---

  dispatch: (payload: {
    instruction: string;
    task_id?: string;
    phase?: string;
    context?: Record<string, unknown>;
    tools_available?: string[];
    complexity_hint?: 'low' | 'medium' | 'high';
    timeout_seconds?: number;
    priority?: number;
    session_id?: string;
  }): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'POST',
      url: '/api/v1/orchestration/dispatch',
      data: payload,
    }),

  getQuotaStatus: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/quota',
    }),

  getActiveTier: (): Promise<Record<string, unknown>> =>
    request<Record<string, unknown>>({
      method: 'GET',
      url: '/api/v1/orchestration/tier',
    }),

  streamSession: (taskId: string): EventSource =>
    new EventSource(`/api/v1/orchestration/stream/${encodeURIComponent(taskId)}`),
};

export const realtimeService = {
  getRecentMissionEvents: (missionId: string, limit = 100): Promise<RealtimeMissionEvent[]> =>
    request<RealtimeRecentMissionEventsResponse>({
      method: 'GET',
      url: `/realtime/missions/${missionId}/recent`,
      params: { limit },
    }).then((payload) => payload.events ?? []),
  normalizeMissionEvent: (message: unknown): RealtimeMissionEvent | null => extractRealtimeMissionEvent(message),
};
