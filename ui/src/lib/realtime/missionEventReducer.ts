import type { Mission, MissionGraphData, MissionNodeStatus, MissionTimelineEvent, MissionStatus, RealtimeEnvelope, RealtimeMissionEvent } from '../../types';

const nodeStatusValues: MissionNodeStatus[] = ['pending', 'running', 'completed', 'failed', 'blocked'];
const missionStatusValues: MissionStatus[] = ['created', 'running', 'paused', 'completed', 'failed', 'cancelled', 'unknown'];

const toNodeStatus = (status: string | null | undefined): MissionNodeStatus => {
  if (!status) {
    return 'pending';
  }
  const normalized = status.toLowerCase();
  if (nodeStatusValues.includes(normalized as MissionNodeStatus)) {
    return normalized as MissionNodeStatus;
  }
  if (normalized === 'pending_approval' || normalized === 'rejected') {
    return 'blocked';
  }
  return 'pending';
};

const toMissionStatus = (status: string | null | undefined): MissionStatus => {
  if (!status) {
    return 'unknown';
  }
  const normalized = status.toLowerCase();
  if (missionStatusValues.includes(normalized as MissionStatus)) {
    return normalized as MissionStatus;
  }
  if (normalized === 'resolved' || normalized === 'approved') {
    return 'running';
  }
  if (normalized === 'rejected' || normalized === 'blocked') {
    return 'paused';
  }
  return 'unknown';
};

const timelineSeverity = (event: RealtimeMissionEvent): MissionTimelineEvent['severity'] => {
  if (event.status === 'failed' || event.status === 'rejected') {
    return 'error';
  }
  if (event.category === 'governance' && event.status === 'pending') {
    return 'warning';
  }
  return 'info';
};

export const isRealtimeMissionEvent = (value: unknown): value is RealtimeMissionEvent => {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const record = value as Record<string, unknown>;
  return typeof record.event_id === 'string' && typeof record.event_type === 'string' && typeof record.mission_id === 'string';
};

export const extractRealtimeMissionEvent = (payload: unknown): RealtimeMissionEvent | null => {
  if (isRealtimeMissionEvent(payload)) {
    return payload;
  }

  if (!payload || typeof payload !== 'object') {
    return null;
  }

  const envelope = payload as RealtimeEnvelope;
  if (envelope.type === 'mission_event' && isRealtimeMissionEvent(envelope.data)) {
    return envelope.data;
  }
  return null;
};

export const applyMissionEventToMission = (mission: Mission, event: RealtimeMissionEvent): Mission => {
  if (mission.id !== event.mission_id) {
    return mission;
  }

  const next = { ...mission };
  if (event.phase) {
    next.phase = event.phase;
  }
  if (event.node_id && (event.status === 'running' || event.status === 'completed')) {
    next.activeNode = event.node_id;
  }
  if (typeof event.detail.progress === 'number') {
    next.progress = Math.min(1, Math.max(0, event.detail.progress));
  }

  const mappedState = toMissionStatus(event.status);
  if (mappedState !== 'unknown') {
    next.state = mappedState;
  }
  return next;
};

export const applyMissionEventToMissionList = (missions: Mission[], event: RealtimeMissionEvent): Mission[] => {
  return missions.map((mission) => applyMissionEventToMission(mission, event));
};

export const applyMissionEventToGraph = (graph: MissionGraphData, event: RealtimeMissionEvent): MissionGraphData => {
  if (!graph.missionId || graph.missionId !== event.mission_id) {
    return graph;
  }

  const nextGraph: MissionGraphData = {
    ...graph,
    phase: event.phase ?? graph.phase,
  };

  const mappedMissionStatus = toMissionStatus(event.status);
  if (mappedMissionStatus !== 'unknown') {
    nextGraph.executionStatus = mappedMissionStatus;
  }

  if (event.node_id) {
    nextGraph.nodes = graph.nodes.map((node) =>
      node.id === event.node_id
        ? {
            ...node,
            status: toNodeStatus(event.status),
            isActive: event.status === 'running',
            lastExecuted: event.timestamp,
          }
        : {
            ...node,
            isActive: event.status === 'running' ? false : node.isActive,
          },
    );
  }

  if (typeof event.detail.progress === 'number') {
    nextGraph.progress = Math.min(1, Math.max(0, event.detail.progress));
  }

  return nextGraph;
};

export const appendMissionTimelineEvent = (
  timeline: MissionTimelineEvent[],
  event: RealtimeMissionEvent,
  maxItems = 200,
): MissionTimelineEvent[] => {
  if (timeline.some((item) => item.id === event.event_id)) {
    return timeline;
  }

  const category: MissionTimelineEvent['category'] =
    event.category === 'node' || event.category === 'simulation' ? 'operation' : event.category;

  const timelineEvent: MissionTimelineEvent = {
    id: event.event_id,
    timestamp: event.timestamp,
    eventType: event.event_type,
    actor: typeof event.detail.resolved_by === 'string' ? event.detail.resolved_by : null,
    message: event.summary,
    category,
    severity: timelineSeverity(event),
    details: event.detail ?? {},
  };

  return [timelineEvent, ...timeline].slice(0, maxItems);
};
