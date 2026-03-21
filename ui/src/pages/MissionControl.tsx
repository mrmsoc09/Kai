import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { DecisionSummaryPanel } from '../components/DecisionSummaryPanel';
import { MissionGraph } from '../components/MissionGraph';
import { MissionTimeline } from '../components/MissionTimeline';
import { StatusPill } from '../components/StatusPill';
import { useAuth } from '../hooks/useAuth';
import { useMissionControl } from '../hooks/useMissionControl';

const isSimulationMode = (mode: string | undefined): boolean =>
  Boolean(mode) && mode !== 'live';

export function MissionControl() {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [searchParams] = useSearchParams();
  const missionFromQuery = searchParams.get('mission');
  const { permissions } = useAuth();
  const {
    missions,
    graph,
    timeline,
    selectedMission,
    isLoading,
    isRefreshing,
    error,
    selectMission,
    startMission,
    stopMission,
    replayMission,
    refreshMissions,
  } = useMissionControl();

  useEffect(() => {
    if (missionFromQuery) {
      void selectMission(missionFromQuery);
    }
  }, [missionFromQuery, selectMission]);

  const selectedNode = useMemo(() => graph.nodes.find((node) => node.id === selectedNodeId) ?? null, [graph.nodes, selectedNodeId]);
  const latestDecisionEvent = useMemo(
    () =>
      timeline.find(
        (event) =>
          event.eventType === 'policy_decision'
          || event.eventType === 'runtime_decision'
          || typeof event.details.decision_action === 'string',
      ) ?? null,
    [timeline],
  );

  return (
    <section className="grid grid-cols-1 gap-6 xl:grid-cols-4">
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-1">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-100">Missions</h2>
          <button
            type="button"
            onClick={() => void refreshMissions()}
            className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
          >
            {isRefreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        </div>
        <div className="space-y-2">
          {missions.map((mission) => (
            <button
              key={mission.id}
              type="button"
              onClick={() => void selectMission(mission.id)}
              className={`w-full rounded-lg border p-3 text-left transition ${
                selectedMission?.id === mission.id ? 'border-cyan-500/60 bg-cyan-500/10' : 'border-slate-800 bg-slate-900/80 hover:border-slate-600'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-medium text-slate-100">{mission.id}</p>
                {isSimulationMode(mission.executionMode) ? (
                  <span className="rounded border border-violet-500/40 bg-violet-500/10 px-2 py-0.5 text-[10px] uppercase text-violet-200">
                    simulation
                  </span>
                ) : (
                  <span className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-0.5 text-[10px] uppercase text-emerald-200">
                    live
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-400">{mission.workflowId}</p>
              <div className="mt-2 flex items-center justify-between gap-2">
                <StatusPill status={mission.state} />
                <span className="text-xs text-slate-400">{Math.round(mission.progress * 100)}%</span>
              </div>
            </button>
          ))}
        </div>
        {missions.length === 0 ? <p className="mt-3 text-sm text-slate-400">No missions available.</p> : null}
      </section>

      <section className="space-y-6 xl:col-span-3">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Mission Graph</h2>
              <p className="text-xs text-slate-400">
                Active: {selectedMission?.activeNode || 'none'} · Phase: {selectedMission?.phase || '-'} · Mode:{' '}
                {selectedMission?.executionMode || '-'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={!selectedMission || !permissions.canOperateMissions}
                onClick={() => selectedMission && void startMission(selectedMission.id)}
                className="rounded bg-emerald-500/20 px-3 py-1.5 text-xs font-medium text-emerald-200 disabled:opacity-50"
              >
                Start
              </button>
              <button
                type="button"
                disabled={!selectedMission || !permissions.canOperateMissions}
                onClick={() => selectedMission && void stopMission(selectedMission.id)}
                className="rounded bg-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-200 disabled:opacity-50"
              >
                Stop
              </button>
              <button
                type="button"
                disabled={!selectedMission || !permissions.canOperateMissions}
                onClick={() => selectedMission && void replayMission(selectedMission.id)}
                className="rounded bg-violet-500/20 px-3 py-1.5 text-xs font-medium text-violet-200 disabled:opacity-50"
              >
                Replay
              </button>
            </div>
          </div>
          <MissionGraph graph={graph} selectedNodeId={selectedNodeId} onNodeSelect={setSelectedNodeId} />
          {error ? <p className="mt-3 text-xs text-amber-300">{error}</p> : null}
        </section>

        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-100">Timeline</h3>
            <MissionTimeline events={timeline} />
          </section>

          <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
            <h3 className="text-sm font-semibold text-slate-100">Status Panel</h3>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-slate-400">Mission</dt>
                <dd className="max-w-[65%] break-all text-right text-slate-100">{selectedMission?.id ?? '-'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-400">Mission Status</dt>
                <dd>{selectedMission ? <StatusPill status={selectedMission.state} /> : '-'}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-400">Execution Mode</dt>
                <dd className="text-slate-100">{selectedMission?.executionMode ?? '-'}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-400">Selected Graph Node</dt>
                <dd className="text-slate-100">{selectedNode?.label ?? 'none'}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-slate-400">Node Status</dt>
                <dd className="text-slate-100">{selectedNode?.status ?? '-'}</dd>
              </div>
            </dl>

            <DecisionSummaryPanel
              summary={latestDecisionEvent?.message}
              detail={(latestDecisionEvent?.details as Record<string, unknown> | undefined) ?? null}
              title="Latest Runtime Decision"
            />

            {selectedMission ? (
              <div className="flex flex-wrap gap-2 text-xs">
                <Link
                  to={`/reports?mission_id=${encodeURIComponent(selectedMission.id)}`}
                  className="rounded border border-violet-500/30 px-2 py-1 text-violet-200 hover:border-violet-400"
                >
                  Reports for this mission
                </Link>
                <Link
                  to={`/artifacts?mission=${encodeURIComponent(selectedMission.id)}`}
                  className="rounded border border-slate-700 px-2 py-1 text-slate-300 hover:border-slate-500"
                >
                  Artifacts
                </Link>
              </div>
            ) : null}

            {!permissions.canOperateMissions ? (
              <p className="text-xs text-amber-300">Start/stop/replay requires analyst or admin role.</p>
            ) : null}
          </section>
        </section>
      </section>

      {isLoading ? <p className="text-sm text-slate-500 xl:col-span-4">Loading mission control data...</p> : null}
    </section>
  );
}
