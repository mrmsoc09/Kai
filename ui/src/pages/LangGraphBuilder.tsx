import { DragEvent, FormEvent, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { missionService } from '../api';

const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];

const countNodes = (graphSpec: Record<string, unknown>): number => {
  const nodes = graphSpec.nodes;
  if (Array.isArray(nodes)) {
    return nodes.length;
  }
  if (nodes && typeof nodes === 'object') {
    return Object.keys(nodes as Record<string, unknown>).length;
  }
  return 0;
};

export function LangGraphBuilder() {
  const [graphText, setGraphText] = useState('');
  const [workflowId, setWorkflowId] = useState('custom-graph');
  const [programId, setProgramId] = useState('custom-target');
  const [missionName, setMissionName] = useState('Custom Graph Mission');
  const [executionMode, setExecutionMode] = useState<'live' | 'graph_only' | 'tool_mock'>('graph_only');
  const [resultMessage, setResultMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [createdMissionId, setCreatedMissionId] = useState<string | null>(null);

  const parsedGraph = useMemo(() => {
    const value = graphText.trim();
    if (!value) {
      return null;
    }
    try {
      const payload = JSON.parse(value);
      return asObject(payload);
    } catch {
      return null;
    }
  }, [graphText]);

  const parseError = useMemo(() => {
    const value = graphText.trim();
    if (!value) {
      return null;
    }
    try {
      JSON.parse(value);
      return null;
    } catch (parseErr) {
      return parseErr instanceof Error ? parseErr.message : 'Invalid JSON';
    }
  }, [graphText]);

  const loadGraphFile = async (file: File) => {
    const text = await file.text();
    setGraphText(text);
    setResultMessage(null);
    setError(null);
    setCreatedMissionId(null);
  };

  const handleFileDrop = async (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    const file = event.dataTransfer.files?.[0];
    if (!file) {
      return;
    }
    await loadGraphFile(file);
  };

  const createMissionFromGraph = async (event: FormEvent) => {
    event.preventDefault();
    if (!parsedGraph || parseError || submitting) {
      return;
    }
    setSubmitting(true);
    setError(null);
    setResultMessage(null);
    setCreatedMissionId(null);
    try {
      const response = await missionService.create({
        workflow_id: workflowId,
        program_id: programId,
        mission_name: missionName,
        execution_mode: executionMode,
        graph_spec: parsedGraph,
      });
      setCreatedMissionId(response.mission_id);
      setResultMessage(`Mission created from uploaded graph: ${response.mission_id}`);
    } catch (submitErr) {
      setError(submitErr instanceof Error ? submitErr.message : 'Failed to create mission from graph spec.');
    } finally {
      setSubmitting(false);
    }
  };

  const nodeCount = parsedGraph ? countNodes(parsedGraph) : 0;
  const edgeCount = parsedGraph ? asArray(parsedGraph.edges).length : 0;
  const clusterCount = parsedGraph ? asArray(parsedGraph.clusters).length : 0;
  const entryNode = parsedGraph ? String(parsedGraph.entry_node ?? '') : '';
  const exitNode = parsedGraph ? String(parsedGraph.exit_node ?? '') : '';

  return (
    <section className="space-y-6">
      <header>
        <h2 className="text-sm font-semibold text-slate-100">LangGraph Builder</h2>
        <p className="text-xs text-slate-400">Drag and drop a LangGraph/Mission graph JSON spec, validate it, and create a mission directly.</p>
      </header>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => void handleFileDrop(event)}
          className="rounded border border-dashed border-cyan-500/40 bg-slate-950/40 p-6 text-center"
        >
          <p className="text-sm text-cyan-200">Drag and drop graph JSON here</p>
          <p className="mt-1 text-xs text-slate-500">or choose a file manually</p>
          <input
            type="file"
            accept=".json,application/json,text/plain"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) {
                void loadGraphFile(file);
              }
            }}
            className="mx-auto mt-3 block text-xs text-slate-300 file:mr-3 file:rounded file:border-0 file:bg-cyan-500/20 file:px-3 file:py-1 file:text-cyan-200"
          />
        </div>

        <textarea
          value={graphText}
          onChange={(event) => setGraphText(event.target.value)}
          placeholder='Paste graph JSON here (must include "nodes" and "edges").'
          className="mt-4 min-h-[18rem] w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
        />

        {parseError ? <p className="mt-2 text-xs text-rose-300">JSON parse error: {parseError}</p> : null}

        {parsedGraph ? (
          <div className="mt-3 rounded border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-300">
            <p>nodes: {nodeCount} · edges: {edgeCount} · clusters: {clusterCount}</p>
            <p>entry: {entryNode || 'auto'} · exit: {exitNode || 'auto'}</p>
          </div>
        ) : null}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-100">Mission Config</h3>
        <form onSubmit={(event) => void createMissionFromGraph(event)} className="space-y-3">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            <input
              value={workflowId}
              onChange={(event) => setWorkflowId(event.target.value)}
              placeholder="workflow_id"
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            />
            <input
              value={programId}
              onChange={(event) => setProgramId(event.target.value)}
              placeholder="program_id"
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            />
            <input
              value={missionName}
              onChange={(event) => setMissionName(event.target.value)}
              placeholder="mission_name"
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            />
            <select
              value={executionMode}
              onChange={(event) => setExecutionMode(event.target.value as 'live' | 'graph_only' | 'tool_mock')}
              className="rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100"
            >
              <option value="graph_only">graph_only</option>
              <option value="tool_mock">tool_mock</option>
              <option value="live">live</option>
            </select>
          </div>
          <button
            type="submit"
            disabled={submitting || !parsedGraph || !!parseError}
            className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
          >
            {submitting ? 'Creating…' : 'Create Mission From Graph'}
          </button>
        </form>
        {resultMessage ? <p className="mt-2 text-xs text-emerald-300">{resultMessage}</p> : null}
        {error ? <p className="mt-2 text-xs text-rose-300">{error}</p> : null}
        {createdMissionId ? (
          <p className="mt-2 text-xs text-cyan-200">
            Open mission:
            {' '}
            <Link className="underline" to={`/mission-control?mission=${encodeURIComponent(createdMissionId)}`}>
              {createdMissionId}
            </Link>
          </p>
        ) : null}
      </section>
    </section>
  );
}
