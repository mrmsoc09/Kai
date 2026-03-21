import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { missionService, realtimeService } from '../api';
import { useWebSocket } from './useWebSocket';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import {
  appendMissionTimelineEvent,
  applyMissionEventToGraph,
  applyMissionEventToMissionList,
} from '../lib/realtime/missionEventReducer';
import type { Mission, MissionGraphData, MissionTimelineEvent, RealtimeMissionEvent } from '../types';

const emptyGraph: MissionGraphData = {
  missionId: '',
  workflowId: '',
  programId: '',
  phase: '',
  executionStatus: 'unknown',
  progress: 0,
  error: null,
  nodes: [],
  edges: [],
};

export function useMissionControl() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [graph, setGraph] = useState<MissionGraphData>(emptyGraph);
  const [timeline, setTimeline] = useState<MissionTimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentMissionId = useAppStore((state) => state.currentMissionId);
  const setCurrentMission = useAppStore((state) => state.setCurrentMission);
  const webSocketState = useAppStore((state) => state.webSocketState);
  const seenEventIdsRef = useRef<Set<string>>(new Set());
  const subscribedMissionRef = useRef<string | null>(null);

  const refreshMissionDetails = useCallback(async (missionId: string) => {
    const [nextGraph, nextTimeline] = await Promise.all([
      missionService.getGraph(missionId),
      missionService.getTimeline(missionId),
    ]);
    setGraph(nextGraph);
    setTimeline(nextTimeline);
  }, []);

  const refreshMissions = useCallback(async () => {
    const missionRows = await missionService.list();
    setMissions(missionRows);

    const selectedStillExists = currentMissionId && missionRows.some((mission) => mission.id === currentMissionId);
    if (!selectedStillExists) {
      setCurrentMission(missionRows[0]?.id ?? null);
    }
  }, [currentMissionId, setCurrentMission]);

  const selectedMission = useMemo(
    () => missions.find((mission) => mission.id === currentMissionId) ?? null,
    [currentMissionId, missions],
  );

  const loadAll = useCallback(
    async (showLoading = false) => {
      if (showLoading) {
        setIsLoading(true);
      } else {
        setIsRefreshing(true);
      }
      setError(null);

      try {
        await refreshMissions();
        const missionId = useAppStore.getState().currentMissionId;
        if (missionId) {
          await refreshMissionDetails(missionId);
        } else {
          setGraph(emptyGraph);
          setTimeline([]);
        }
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : 'Failed to load mission control state.');
      } finally {
        setIsLoading(false);
        setIsRefreshing(false);
      }
    },
    [refreshMissionDetails, refreshMissions],
  );

  const applyRealtimeEvent = useCallback(
    (event: RealtimeMissionEvent) => {
      if (seenEventIdsRef.current.has(event.event_id)) {
        return;
      }
      seenEventIdsRef.current.add(event.event_id);
      if (seenEventIdsRef.current.size > 2000) {
        const ids = [...seenEventIdsRef.current];
        seenEventIdsRef.current = new Set(ids.slice(ids.length - 1200));
      }

      setMissions((previous) => applyMissionEventToMissionList(previous, event));

      const selected = useAppStore.getState().currentMissionId;
      if (selected && selected === event.mission_id) {
        setGraph((previous) => applyMissionEventToGraph(previous, event));
        setTimeline((previous) => appendMissionTimelineEvent(previous, event));
      }
    },
    [],
  );

  const selectMission = useCallback(
    async (missionId: string) => {
      setCurrentMission(missionId);
      setError(null);

      try {
        await refreshMissionDetails(missionId);
        const recent = await realtimeService.getRecentMissionEvents(missionId, 80);
        recent.forEach((event) => applyRealtimeEvent(event));
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : 'Failed to load mission details.');
      }
    },
    [applyRealtimeEvent, refreshMissionDetails, setCurrentMission],
  );

  const runMissionAction = useCallback(
    async (operation: 'start' | 'stop' | 'replay', missionId: string) => {
      setError(null);
      try {
        if (operation === 'start') {
          await missionService.start(missionId);
        } else if (operation === 'stop') {
          await missionService.stop(missionId);
        } else {
          await missionService.replay(missionId);
        }
        await refreshMissions();
        if (webSocketState !== 'connected') {
          await refreshMissionDetails(missionId);
        }
      } catch (actionError) {
        setError(actionError instanceof Error ? actionError.message : `Failed to ${operation} mission.`);
      }
    },
    [refreshMissionDetails, refreshMissions, webSocketState],
  );

  const handleLiveMessage = useCallback(
    (message: unknown) => {
      const event = realtimeService.normalizeMissionEvent(message);
      if (!event) {
        return;
      }
      applyRealtimeEvent(event);
    },
    [applyRealtimeEvent],
  );

  const { connect, disconnect, subscribeToMission, unsubscribe } = useWebSocket<unknown>({
    path: appConfig.missionEventsPath,
    onMessage: handleLiveMessage,
  });

  useEffect(() => {
    void loadAll(true);
  }, [loadAll]);

  useEffect(() => {
    const pollMs = webSocketState === 'connected' ? 30000 : 7000;
    const pollId = window.setInterval(() => {
      if (webSocketState === 'connected') {
        void refreshMissions();
      } else {
        void loadAll();
      }
    }, pollMs);
    return () => window.clearInterval(pollId);
  }, [loadAll, refreshMissions, webSocketState]);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  useEffect(() => {
    if (webSocketState !== 'connected') {
      return;
    }

    if (!currentMissionId) {
      const previous = subscribedMissionRef.current;
      if (previous) {
        unsubscribe('mission_events', previous);
        subscribedMissionRef.current = null;
      }
      return;
    }

    const previous = subscribedMissionRef.current;
    if (previous && previous !== currentMissionId) {
      unsubscribe('mission_events', previous);
    }

    subscribeToMission(currentMissionId);
    subscribedMissionRef.current = currentMissionId;
    void realtimeService
      .getRecentMissionEvents(currentMissionId, 80)
      .then((events) => events.forEach((event) => applyRealtimeEvent(event)))
      .catch(() => null);
  }, [applyRealtimeEvent, currentMissionId, subscribeToMission, unsubscribe, webSocketState]);

  useEffect(
    () => () => {
      const current = subscribedMissionRef.current;
      if (current) {
        unsubscribe('mission_events', current);
      }
    },
    [unsubscribe],
  );

  return {
    missions,
    graph,
    timeline,
    selectedMission,
    isLoading,
    isRefreshing,
    error,
    selectMission,
    startMission: (missionId: string) => runMissionAction('start', missionId),
    stopMission: (missionId: string) => runMissionAction('stop', missionId),
    replayMission: (missionId: string) => runMissionAction('replay', missionId),
    refreshMissions: loadAll,
  };
}
