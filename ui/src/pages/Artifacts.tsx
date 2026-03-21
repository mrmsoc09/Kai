import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { artifactService, missionService } from '../api';
import { useWebSocket } from '../hooks/useWebSocket';
import { useAppStore } from '../store/appStore';
import { appConfig } from '../utils/config';
import { extractRealtimeMissionEvent } from '../lib/realtime/missionEventReducer';
import type { Artifact, ArtifactContent, Mission } from '../types';
import { formatTimestamp } from '../utils/format';

const toPreview = (content: ArtifactContent | null): string => {
  if (content === null) {
    return '';
  }

  if (typeof content === 'string') {
    return content;
  }

  try {
    return JSON.stringify(content, null, 2);
  } catch {
    return String(content);
  }
};

const importantDetails = (artifact: Artifact): Array<[string, string]> => {
  const pairs: Array<[string, string]> = [];
  const details = artifact.details_json;

  for (const key of ['classification', 'severity', 'validation_status', 'report_type', 'tool_name']) {
    const value = details[key];
    if (typeof value === 'string' && value) {
      pairs.push([key, value]);
    }
  }

  return pairs;
};

export function Artifacts() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [selectedMissionId, setSelectedMissionId] = useState<string | null>(null);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);
  const [content, setContent] = useState<ArtifactContent | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [liveArtifactNotices, setLiveArtifactNotices] = useState(0);
  const navigate = useNavigate();
  const setCurrentMission = useAppStore((state) => state.setCurrentMission);
  const webSocketState = useAppStore((state) => state.webSocketState);

  const loadMissions = async () => {
    try {
      const missionRows = await missionService.list();
      setMissions(missionRows);
      if (!selectedMissionId && missionRows[0]) {
        setSelectedMissionId(missionRows[0].id);
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load missions for artifacts.');
    }
  };

  const loadArtifacts = async (missionId: string) => {
    setError(null);
    try {
      const rows = await artifactService.listByMission(missionId);
      setArtifacts(rows);
      setSelectedArtifactId(rows[0]?.id ?? null);
    } catch (fetchError) {
      setArtifacts([]);
      setSelectedArtifactId(null);
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load artifacts.');
    }
  };

  useEffect(() => {
    void loadMissions();
  }, []);

  useEffect(() => {
    if (!selectedMissionId) {
      return;
    }
    setLiveArtifactNotices(0);
    void loadArtifacts(selectedMissionId);
  }, [selectedMissionId]);

  useEffect(() => {
    const loadContent = async () => {
      if (!selectedArtifactId) {
        setContent(null);
        return;
      }

      try {
        const nextContent = await artifactService.getContent(selectedArtifactId);
        setContent(nextContent);
      } catch (fetchError) {
        setContent(null);
        setError(fetchError instanceof Error ? fetchError.message : 'Failed to load artifact content.');
      }
    };

    void loadContent();
  }, [selectedArtifactId]);

  const { connect, disconnect, subscribe, unsubscribe } = useWebSocket<unknown>({
    path: appConfig.missionEventsPath,
    onMessage: (message) => {
      const event = extractRealtimeMissionEvent(message);
      if (!event || event.category !== 'artifact') {
        return;
      }
      if (!selectedMissionId || event.mission_id !== selectedMissionId) {
        return;
      }

      setLiveArtifactNotices((previous) => previous + 1);
      void loadArtifacts(selectedMissionId);
    },
  });

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  useEffect(() => {
    if (webSocketState === 'connected' && selectedMissionId) {
      subscribe('artifact_events', selectedMissionId);
      return () => {
        unsubscribe('artifact_events', selectedMissionId);
      };
    }
    return undefined;
  }, [selectedMissionId, subscribe, unsubscribe, webSocketState]);

  useEffect(() => {
    if (!selectedMissionId || webSocketState === 'connected') {
      return undefined;
    }
    const pollId = window.setInterval(() => {
      void loadArtifacts(selectedMissionId);
    }, 12000);
    return () => window.clearInterval(pollId);
  }, [selectedMissionId, webSocketState]);

  const selectedArtifact = useMemo(
    () => artifacts.find((artifact) => artifact.id === selectedArtifactId) ?? null,
    [artifacts, selectedArtifactId],
  );

  const preview = toPreview(content);

  return (
    <section className="grid grid-cols-1 gap-6 xl:grid-cols-4">
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-1">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Artifacts</h2>
        <select
          value={selectedMissionId ?? ''}
          onChange={(event) => setSelectedMissionId(event.target.value || null)}
          className="mb-3 w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
        >
          <option value="">Select mission</option>
          {missions.map((mission) => (
            <option key={mission.id} value={mission.id}>
              {mission.id}
            </option>
          ))}
        </select>
        <div className="space-y-2">
          {artifacts.map((artifact) => (
            <button
              key={artifact.id}
              type="button"
              onClick={() => setSelectedArtifactId(artifact.id)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                selectedArtifactId === artifact.id ? 'border-cyan-500/60 bg-cyan-500/10' : 'border-slate-800 bg-slate-900/80 hover:border-slate-600'
              }`}
            >
              <p className="text-sm text-slate-100">{artifact.artifact_type}</p>
              <p className="mt-1 break-all text-xs text-slate-400">{artifact.id}</p>
            </button>
          ))}
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-2">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Preview</h2>
        {liveArtifactNotices > 0 ? <p className="mb-3 text-xs text-emerald-300">Live: {liveArtifactNotices} new artifact event(s) received.</p> : null}
        {selectedArtifact ? (
          <pre className="max-h-[540px] overflow-auto rounded-lg border border-slate-800 bg-slate-950 p-3 text-xs text-slate-200">{preview || 'No preview data.'}</pre>
        ) : (
          <p className="text-sm text-slate-400">Select an artifact to preview content.</p>
        )}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-1">
        <h2 className="mb-3 text-sm font-semibold text-slate-100">Metadata</h2>
        {selectedArtifact ? (
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Artifact Type</dt>
              <dd className="text-slate-100">{selectedArtifact.artifact_type}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Mission</dt>
              <dd className="break-all text-right text-slate-100">{selectedArtifact.campaign_id}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">MIME</dt>
              <dd className="text-slate-100">{selectedArtifact.mime_type ?? 'unknown'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Size</dt>
              <dd className="text-slate-100">{selectedArtifact.size_bytes ?? '-'}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className="text-slate-400">Created</dt>
              <dd className="text-slate-100">{formatTimestamp(selectedArtifact.created_at)}</dd>
            </div>
            {importantDetails(selectedArtifact).map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3">
                <dt className="text-slate-400">{key}</dt>
                <dd className="max-w-[65%] text-right text-slate-100">{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-sm text-slate-400">No artifact selected.</p>
        )}

        {selectedArtifact ? (
          <button
            type="button"
            onClick={() => {
              setCurrentMission(selectedArtifact.campaign_id);
              navigate('/mission-control');
            }}
            className="mt-4 w-full rounded border border-slate-700 bg-slate-800/60 px-3 py-2 text-xs text-slate-200 hover:border-slate-500"
          >
            Open Mission Context
          </button>
        ) : null}

        {error ? <p className="mt-3 text-xs text-rose-300">{error}</p> : null}
      </section>
    </section>
  );
}
