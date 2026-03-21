import { useEffect, useState } from 'react';
import { missionService, simulationService } from '../api';
import { useAuth } from '../hooks/useAuth';
import type { Mission, SimulationCompareResponse, SimulationMode, SimulationResult } from '../types';

const simulationModes: SimulationMode[] = ['graph_only', 'tool_mock', 'replay'];

export function Simulation() {
  const { permissions } = useAuth();
  const [mode, setMode] = useState<SimulationMode>('tool_mock');
  const [workflowId, setWorkflowId] = useState('');
  const [programId, setProgramId] = useState('');
  const [missionName, setMissionName] = useState('simulation_run');
  const [scenarioPack, setScenarioPack] = useState('');
  const [targetsText, setTargetsText] = useState('');
  const [scenarios, setScenarios] = useState<string[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [resultMission, setResultMission] = useState<Mission | null>(null);
  const [compareBaselineId, setCompareBaselineId] = useState('');
  const [compareVariantId, setCompareVariantId] = useState('');
  const [comparison, setComparison] = useState<SimulationCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isComparing, setIsComparing] = useState(false);

  useEffect(() => {
    const loadScenarios = async () => {
      try {
        const payload = await simulationService.listScenarios();
        setScenarios(payload.scenarios ?? []);
      } catch (scenarioError) {
        setError(scenarioError instanceof Error ? scenarioError.message : 'Unable to load simulation scenarios.');
      }
    };

    void loadScenarios();
  }, []);

  const runSimulation = async () => {
    setError(null);
    if (!workflowId.trim() || !programId.trim()) {
      setError('workflow_id and program_id are required.');
      return;
    }

    setIsRunning(true);
    try {
      const payload = await simulationService.run({
        workflow_id: workflowId.trim(),
        program_id: programId.trim(),
        mission_name: missionName.trim() || 'simulation_run',
        mode,
        scenario_pack: scenarioPack || undefined,
        targets: targetsText
          .split(',')
          .map((item) => item.trim())
          .filter(Boolean),
      });

      setResult(payload);
      const mission = await missionService.getStatus(payload.mission_id);
      setResultMission(mission);
    } catch (runError) {
      setError(runError instanceof Error ? runError.message : 'Simulation run failed.');
    } finally {
      setIsRunning(false);
    }
  };

  const compareRuns = async () => {
    setError(null);
    if (!compareBaselineId.trim() || !compareVariantId.trim()) {
      setError('Provide both baseline and variant mission IDs.');
      return;
    }

    setIsComparing(true);
    try {
      const payload = await simulationService.compare({
        baseline_mission_id: compareBaselineId.trim(),
        variant_mission_id: compareVariantId.trim(),
        metrics: ['cost', 'latency', 'findings'],
      });
      setComparison(payload);
    } catch (compareError) {
      setError(compareError instanceof Error ? compareError.message : 'Simulation comparison failed.');
    } finally {
      setIsComparing(false);
    }
  };

  return (
    <section className="space-y-4">
      <h2 className="text-sm font-semibold text-slate-100">Simulation Console</h2>
      <p className="rounded border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-200">
        Simulation mode is isolated from live execution. Tool execution is forced into safe behavior.
      </p>

      {!permissions.canRunSimulation ? <p className="text-xs text-amber-300">Running simulations requires analyst or admin role.</p> : null}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}

      <section className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="text-sm font-semibold text-slate-100">Run Simulation</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            value={workflowId}
            onChange={(event) => setWorkflowId(event.target.value)}
            placeholder="workflow_id"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
          <input
            value={programId}
            onChange={(event) => setProgramId(event.target.value)}
            placeholder="program_id"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as SimulationMode)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            {simulationModes.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <select
            value={scenarioPack}
            onChange={(event) => setScenarioPack(event.target.value)}
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 focus:ring"
          >
            <option value="">No scenario pack</option>
            {scenarios.map((scenario) => (
              <option key={scenario} value={scenario}>
                {scenario}
              </option>
            ))}
          </select>
          <input
            value={missionName}
            onChange={(event) => setMissionName(event.target.value)}
            placeholder="mission_name"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
          <input
            value={targetsText}
            onChange={(event) => setTargetsText(event.target.value)}
            placeholder="targets (comma-separated)"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
        </div>
        <button
          type="button"
          onClick={() => void runSimulation()}
          disabled={isRunning || !permissions.canRunSimulation}
          className="rounded bg-cyan-500/20 px-3 py-2 text-sm font-medium text-cyan-200 disabled:opacity-50"
        >
          {isRunning ? 'Running...' : 'Run Simulation'}
        </button>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-100">Latest Run</h3>
        {result ? (
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-400">Mission ID</dt>
              <dd className="text-slate-100">{result.mission_id}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Mode</dt>
              <dd className="text-slate-100">{result.mode}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Status</dt>
              <dd className="text-slate-100">{result.status}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Live Tools</dt>
              <dd className="text-slate-100">{result.is_live_blocked ? 'blocked' : 'enabled'}</dd>
            </div>
            {resultMission ? (
              <div className="flex justify-between">
                <dt className="text-slate-400">Mission State</dt>
                <dd className="text-slate-100">
                  {resultMission.state} ({Math.round(resultMission.progress * 100)}%)
                </dd>
              </div>
            ) : null}
          </dl>
        ) : (
          <p className="text-sm text-slate-400">No simulation runs yet.</p>
        )}
      </section>

      <section className="space-y-3 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="text-sm font-semibold text-slate-100">Compare Runs</h3>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
          <input
            value={compareBaselineId}
            onChange={(event) => setCompareBaselineId(event.target.value)}
            placeholder="baseline_mission_id"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
          <input
            value={compareVariantId}
            onChange={(event) => setCompareVariantId(event.target.value)}
            placeholder="variant_mission_id"
            className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
          />
        </div>
        <button
          type="button"
          onClick={() => void compareRuns()}
          disabled={isComparing || !permissions.canRunSimulation}
          className="rounded bg-violet-500/20 px-3 py-2 text-sm font-medium text-violet-200 disabled:opacity-50"
        >
          {isComparing ? 'Comparing...' : 'Run Comparison'}
        </button>
        {comparison ? (
          <div className="rounded border border-slate-700 bg-slate-950/60 p-3 text-xs text-slate-300">
            <p className="text-slate-100">{comparison.delta}</p>
            <pre className="mt-2 overflow-x-auto">{JSON.stringify(comparison, null, 2)}</pre>
          </div>
        ) : null}
      </section>
    </section>
  );
}
