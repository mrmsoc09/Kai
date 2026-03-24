import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { agentZeroService } from '../api';

type ChatRole = 'user' | 'assistant' | 'system' | 'tool';

interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: string;
}

interface ApprovalItem {
  approvalId: string;
  operation: string;
  tier: number;
  message: string;
}

interface AgentItem {
  agentId: string;
  name: string;
  status: string;
  objective: string;
  autonomyLevel: number;
}

interface WorkflowItem {
  workflowId: string;
  target: string;
  status: string;
  createdAt: string;
}

const asObject = (value: unknown): Record<string, unknown> =>
  value && typeof value === 'object' ? (value as Record<string, unknown>) : {};

const asArray = (value: unknown): unknown[] =>
  Array.isArray(value) ? value : [];

const asText = (value: unknown, fallback = ''): string =>
  typeof value === 'string' ? value : fallback;

const asNumber = (value: unknown, fallback = 0): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : fallback;

const toChatRole = (value: string): ChatRole =>
  value === 'user' || value === 'assistant' || value === 'tool' ? value : 'system';

const nowIso = (): string => new Date().toISOString();

const buildWsUrl = (sessionId: string | null): string => {
  const explicit = import.meta.env.VITE_AGENT_ZERO_WS_URL as string | undefined;
  const base = explicit && explicit.trim().length > 0
    ? explicit.trim()
    : `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.hostname}:8080/api/v1/agent-zero/ws/chat`;
  if (!sessionId) {
    return base;
  }
  const queryJoin = base.includes('?') ? '&' : '?';
  return `${base}${queryJoin}session_id=${encodeURIComponent(sessionId)}`;
};

const roleClass = (role: ChatRole): string => {
  switch (role) {
    case 'user':
      return 'border-cyan-500/40 bg-cyan-500/10 text-cyan-100';
    case 'assistant':
      return 'border-emerald-500/40 bg-emerald-500/10 text-emerald-100';
    case 'tool':
      return 'border-violet-500/40 bg-violet-500/10 text-violet-100';
    default:
      return 'border-amber-500/40 bg-amber-500/10 text-amber-100';
  }
};

export function AgentZero() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [quickTarget, setQuickTarget] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [pendingApprovals, setPendingApprovals] = useState<ApprovalItem[]>([]);
  const [streamingBuffer, setStreamingBuffer] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const [relayLogs, setRelayLogs] = useState<Record<string, unknown>[]>([]);
  const [agents, setAgents] = useState<AgentItem[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [health, setHealth] = useState<Record<string, unknown>>({});
  const [llmUsage, setLlmUsage] = useState<Record<string, unknown>>({});
  const [pluginInfo, setPluginInfo] = useState<Record<string, unknown>>({});
  const [chatError, setChatError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [runningHunt, setRunningHunt] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(false);

  const messagePanelRef = useRef<HTMLDivElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const loadSessionHistory = useCallback(async (nextSessionId: string) => {
    setLoadingHistory(true);
    try {
      const payload = await agentZeroService.getChatHistory(nextSessionId, 120);
      const rows = asArray(payload.messages).map((row) => {
        const item = asObject(row);
        return {
          id: asText(item.id, `history-${Math.random()}`),
          role: toChatRole(asText(item.role, 'system')),
          content: asText(item.content, ''),
          timestamp: asText(item.timestamp, nowIso()),
        } satisfies ChatMessage;
      });
      setMessages(rows);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Unable to load chat history.');
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  const refreshStatusPanels = useCallback(async () => {
    const [healthResult, agentResult, workflowResult, llmResult, pluginResult, relayResult] = await Promise.allSettled([
      agentZeroService.getHealth(),
      agentZeroService.getAgents(),
      agentZeroService.getWorkflows(30),
      agentZeroService.getLlmUsage(),
      agentZeroService.getPluginInfo(),
      agentZeroService.getRelayLogs(40),
    ]);

    if (healthResult.status === 'fulfilled') {
      setHealth(asObject(healthResult.value));
    }
    if (llmResult.status === 'fulfilled') {
      setLlmUsage(asObject(llmResult.value));
    }
    if (pluginResult.status === 'fulfilled') {
      setPluginInfo(asObject(pluginResult.value));
    }
    if (relayResult.status === 'fulfilled') {
      const rows = asArray(asObject(relayResult.value).logs)
        .map((row) => asObject(row))
        .filter((row) => Object.keys(row).length > 0);
      setRelayLogs(rows);
    }
    if (agentResult.status === 'fulfilled') {
      const payload = asObject(agentResult.value);
      const rows = asArray(payload.agents).map((row) => {
        const item = asObject(row);
        const performance = asObject(item.performance);
        return {
          agentId: asText(item.agent_id),
          name: asText(item.name, asText(item.agent_id, 'agent')),
          status: asText(item.status, 'unknown'),
          objective: asText(item.objective, 'general'),
          autonomyLevel: asNumber(item.autonomy_level, asNumber(performance.autonomy_level, 0)),
        } satisfies AgentItem;
      }).filter((row) => row.agentId.length > 0);
      setAgents(rows);
    }
    if (workflowResult.status === 'fulfilled') {
      const payload = asObject(workflowResult.value);
      const rows = asArray(payload.workflows).map((row) => {
        const item = asObject(row);
        return {
          workflowId: asText(item.workflow_id, asText(item.id, 'workflow')),
          target: asText(item.target, asText(item.program_id, 'target')),
          status: asText(item.status, 'unknown'),
          createdAt: asText(item.created_at, ''),
        } satisfies WorkflowItem;
      }).filter((row) => row.workflowId.length > 0);
      setWorkflows(rows);
    }

    const failures = [healthResult, agentResult, workflowResult, llmResult, pluginResult, relayResult].filter((row) => row.status === 'rejected');
    setStatusError(failures.length > 0 ? 'Some Agent-Zero status panels are unavailable in this runtime.' : null);
  }, []);

  const handleWsEvent = useCallback((payload: Record<string, unknown>) => {
    const eventType = asText(payload.type, '');
    if (!eventType) {
      return;
    }
    if (eventType === 'session_started') {
      const nextSession = asText(payload.session_id);
      if (nextSession) {
        setSessionId(nextSession);
      }
      return;
    }
    if (eventType === 'token') {
      const token = asText(payload.content);
      if (token) {
        setStreamingBuffer((previous) => previous + token);
      }
      return;
    }
    if (eventType === 'message_complete') {
      const messageObj = asObject(payload.message);
      const content = asText(messageObj.content, streamingBuffer);
      if (content) {
        setMessages((previous) => [
          ...previous,
          {
            id: asText(messageObj.id, `assistant-${Date.now()}`),
            role: toChatRole(asText(messageObj.role, 'assistant')),
            content,
            timestamp: asText(messageObj.timestamp, nowIso()),
          },
        ]);
      }
      setStreamingBuffer('');
      return;
    }
    if (eventType === 'tool_result') {
      setMessages((previous) => [
        ...previous,
        {
          id: `tool-${Date.now()}`,
          role: 'tool',
          content: JSON.stringify(asObject(payload.data).result ?? asObject(payload.data), null, 2),
          timestamp: nowIso(),
        },
      ]);
      return;
    }
    if (eventType === 'approval_required') {
      const data = asObject(payload.data);
      const approvalId = asText(data.approval_id);
      if (!approvalId) {
        return;
      }
      setPendingApprovals((previous) => [
        ...previous,
        {
          approvalId,
          operation: asText(data.operation, 'operation'),
          tier: asNumber(data.tier, 0),
          message: asText(data.message, 'Approval required.'),
        },
      ]);
      return;
    }
    if (eventType === 'approval_granted' || eventType === 'approval_rejected') {
      const data = asObject(payload.data);
      const approvalId = asText(data.approval_id);
      if (approvalId) {
        setPendingApprovals((previous) => previous.filter((row) => row.approvalId !== approvalId));
      }
      return;
    }
    if (eventType === 'error') {
      const data = asObject(payload.data);
      setChatError(asText(data.message, 'Agent-Zero websocket error.'));
    }
  }, [streamingBuffer]);

  const connectWs = useCallback((requestedSession: string | null) => {
    if (wsRef.current) {
      return;
    }
    const ws = new WebSocket(buildWsUrl(requestedSession));
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      setChatError(null);
    };

    ws.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as Record<string, unknown>;
        handleWsEvent(parsed);
      } catch {
        // ignore malformed events
      }
    };

    ws.onclose = () => {
      wsRef.current = null;
      setWsConnected(false);
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      reconnectTimeoutRef.current = window.setTimeout(() => {
        connectWs(sessionId);
      }, 2000);
    };

    ws.onerror = () => {
      setChatError('Agent-Zero websocket connection failed. Falling back to REST where available.');
    };
  }, [handleWsEvent, sessionId]);

  useEffect(() => {
    void refreshStatusPanels();
    const statusPoll = window.setInterval(() => {
      void refreshStatusPanels();
    }, 10000);
    return () => window.clearInterval(statusPoll);
  }, [refreshStatusPanels]);

  useEffect(() => {
    connectWs(sessionId);
    return () => {
      if (reconnectTimeoutRef.current !== null) {
        window.clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
      wsRef.current = null;
    };
  }, [connectWs, sessionId]);

  useEffect(() => {
    const panel = messagePanelRef.current;
    if (!panel) {
      return;
    }
    panel.scrollTop = panel.scrollHeight;
  }, [messages, pendingApprovals, streamingBuffer]);

  const sendMessage = useCallback(async (event: FormEvent) => {
    event.preventDefault();
    const content = draft.trim();
    if (!content) {
      return;
    }

    setChatError(null);
    setMessages((previous) => [
      ...previous,
      {
        id: `user-${Date.now()}`,
        role: 'user',
        content,
        timestamp: nowIso(),
      },
    ]);
    setDraft('');
    setStreamingBuffer('');

    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'message',
        content,
        context: { source: 'k1-console' },
      }));
      return;
    }

    try {
      const payload = await agentZeroService.sendChatMessage({
        content,
        session_id: sessionId ?? undefined,
        context: { source: 'k1-console' },
      });
      const nextSession = asText(payload.session_id);
      if (nextSession) {
        setSessionId(nextSession);
      }
      if (Boolean(payload.approval_required)) {
        const approvalId = asText(payload.approval_id);
        if (approvalId) {
          setPendingApprovals((previous) => [
            ...previous,
            {
              approvalId,
              operation: asText(payload.operation, 'operation'),
              tier: asNumber(payload.tier, 0),
              message: asText(payload.message, 'Approval required.'),
            },
          ]);
        }
        return;
      }
      setMessages((previous) => [
        ...previous,
        {
          id: asText(payload.message_id, `assistant-${Date.now()}`),
          role: 'assistant',
          content: asText(payload.response, ''),
          timestamp: asText(payload.timestamp, nowIso()),
        },
      ]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Unable to send message to Agent-Zero.');
    }
  }, [draft, sessionId]);

  const handleApproval = useCallback(async (approvalId: string, decision: 'approved' | 'rejected') => {
    setChatError(null);
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'approval_response',
        approval_id: approvalId,
        decision,
        reason: decision === 'rejected' ? 'Rejected from K1 console' : undefined,
      }));
      setPendingApprovals((previous) => previous.filter((row) => row.approvalId !== approvalId));
      return;
    }

    try {
      const payload = await agentZeroService.respondToApproval({
        approval_id: approvalId,
        decision,
        reason: decision === 'rejected' ? 'Rejected from K1 console' : undefined,
      });
      setPendingApprovals((previous) => previous.filter((row) => row.approvalId !== approvalId));
      setMessages((previous) => [
        ...previous,
        {
          id: `approval-${Date.now()}`,
          role: 'system',
          content: asText(payload.message, `Approval ${decision}.`),
          timestamp: nowIso(),
        },
      ]);
    } catch (error) {
      setChatError(error instanceof Error ? error.message : 'Failed to send approval decision.');
    }
  }, []);

  const runQuickHunt = useCallback(async (event: FormEvent) => {
    event.preventDefault();
    const target = quickTarget.trim();
    if (!target || runningHunt) {
      return;
    }
    setRunningHunt(true);
    setStatusError(null);
    try {
      await agentZeroService.createHuntWorkflow(target);
      setQuickTarget('');
      await refreshStatusPanels();
    } catch (error) {
      setStatusError(error instanceof Error ? error.message : 'Unable to start hunt workflow.');
    } finally {
      setRunningHunt(false);
    }
  }, [quickTarget, refreshStatusPanels, runningHunt]);

  const systems = useMemo(() => asObject(health.systems), [health]);
  const llmByModel = useMemo(() => asObject(llmUsage.by_model), [llmUsage]);

  return (
    <section className="grid grid-cols-1 gap-6 xl:grid-cols-12">
      <section className="space-y-4 xl:col-span-8">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-slate-100">Agent-Zero Workspace</h2>
              <p className="text-xs text-slate-400">Default Agent-Zero style chat workspace, adapted to Kai branding and controls.</p>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className={`rounded px-2 py-1 ${wsConnected ? 'bg-emerald-500/15 text-emerald-300' : 'bg-rose-500/15 text-rose-300'}`}>
                ws: {wsConnected ? 'connected' : 'offline'}
              </span>
              <button
                type="button"
                onClick={() => sessionId && void loadSessionHistory(sessionId)}
                disabled={!sessionId || loadingHistory}
                className="rounded border border-slate-700 px-2 py-1 text-slate-200 disabled:opacity-50"
              >
                {loadingHistory ? 'Loading…' : 'History'}
              </button>
              <span className="rounded border border-cyan-500/30 px-2 py-1 text-cyan-200">
                session: {sessionId ?? 'new'}
              </span>
            </div>
          </div>

          <div ref={messagePanelRef} className="max-h-[26rem] space-y-2 overflow-y-auto rounded border border-slate-800 bg-slate-950/50 p-3">
            {messages.map((message) => (
              <article key={message.id} className={`rounded border px-3 py-2 text-sm ${roleClass(message.role)}`}>
                <div className="mb-1 flex items-center justify-between gap-2 text-[10px] uppercase tracking-wide">
                  <span>{message.role}</span>
                  <span>{new Date(message.timestamp).toLocaleString()}</span>
                </div>
                <p className="whitespace-pre-wrap break-words">{message.content}</p>
              </article>
            ))}
            {streamingBuffer ? (
              <article className="rounded border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm text-emerald-100">
                <div className="mb-1 text-[10px] uppercase tracking-wide">assistant streaming</div>
                <p className="whitespace-pre-wrap break-words">{streamingBuffer}</p>
              </article>
            ) : null}
            {messages.length === 0 && !streamingBuffer ? <p className="text-xs text-slate-500">No messages yet. Send a command to begin.</p> : null}
          </div>

          {pendingApprovals.length > 0 ? (
            <div className="mt-3 space-y-2 rounded border border-amber-500/30 bg-amber-500/5 p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-amber-300">Pending approvals</p>
              {pendingApprovals.map((approval) => (
                <div key={approval.approvalId} className="rounded border border-amber-500/30 bg-slate-950/50 p-2 text-xs">
                  <p className="text-amber-200">{approval.message}</p>
                  <p className="text-slate-400">operation: {approval.operation} · tier {approval.tier}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => void handleApproval(approval.approvalId, 'approved')}
                      className="rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-emerald-200"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleApproval(approval.approvalId, 'rejected')}
                      className="rounded border border-rose-500/40 bg-rose-500/10 px-2 py-1 text-rose-200"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          <form className="mt-3 space-y-2" onSubmit={(event) => void sendMessage(event)}>
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="Ask Agent-Zero to hunt, recon, triage, execute workflows, or summarize findings..."
              className="min-h-[5.5rem] w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
            />
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs text-slate-500">HiL approvals appear inline and can be approved/rejected immediately.</p>
              <button
                type="submit"
                disabled={!draft.trim()}
                className="rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
              >
                Send
              </button>
            </div>
          </form>
          {chatError ? <p className="mt-2 text-xs text-rose-300">{chatError}</p> : null}
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">Relay Audit</h3>
          <div className="max-h-72 overflow-y-auto rounded border border-slate-800">
            <table className="min-w-full text-left text-xs">
              <thead className="sticky top-0 bg-slate-950 text-slate-400">
                <tr>
                  <th className="px-2 py-2">Time</th>
                  <th className="px-2 py-2">Client</th>
                  <th className="px-2 py-2">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {relayLogs.map((entry, index) => (
                  <tr key={`${asText(entry.ts, String(index))}-${index}`}>
                    <td className="px-2 py-2 text-slate-300">
                      {entry.ts ? new Date(Number(entry.ts)).toLocaleString() : '-'}
                    </td>
                    <td className="px-2 py-2 text-slate-400">{asText(entry.client, 'n/a')}</td>
                    <td className="px-2 py-2 text-slate-200">{asText(entry.text, '')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {relayLogs.length === 0 ? <p className="p-3 text-xs text-slate-500">No relay entries recorded.</p> : null}
          </div>
        </section>
      </section>

      <section className="space-y-4 xl:col-span-4">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">Agent-Zero Status</h3>
          <p className="text-xs text-slate-400">k1 status: {asText(health.k1_status, 'unknown')}</p>
          <p className="text-xs text-slate-400">plugin: {asText(pluginInfo.plugin_id, 'n/a')}</p>
          <p className="text-xs text-slate-400">registered: {String(pluginInfo.registered ?? false)}</p>
          <div className="mt-2 space-y-1 text-xs">
            {Object.entries(systems).map(([key, value]) => (
              <p key={key} className="text-slate-300">
                {key}: <span className="text-cyan-200">{asText(value, String(value))}</span>
              </p>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">Quick Hunt</h3>
          <form className="space-y-2" onSubmit={(event) => void runQuickHunt(event)}>
            <input
              value={quickTarget}
              onChange={(event) => setQuickTarget(event.target.value)}
              placeholder="example.com"
              className="w-full rounded border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none ring-cyan-500/40 placeholder:text-slate-500 focus:ring"
            />
            <button
              type="submit"
              disabled={!quickTarget.trim() || runningHunt}
              className="w-full rounded border border-cyan-500/40 bg-cyan-500/10 px-3 py-1.5 text-xs font-medium text-cyan-200 disabled:opacity-50"
            >
              {runningHunt ? 'Launching…' : 'Start Hunt Workflow'}
            </button>
          </form>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">Active Agents</h3>
          <div className="space-y-2 text-xs">
            {agents.map((agent) => (
              <article key={agent.agentId} className="rounded border border-slate-800 bg-slate-950/50 p-2">
                <p className="text-slate-100">{agent.name}</p>
                <p className="text-slate-400">status: {agent.status}</p>
                <p className="text-slate-400">objective: {agent.objective}</p>
                <p className="text-slate-400">autonomy: {agent.autonomyLevel}</p>
              </article>
            ))}
            {agents.length === 0 ? <p className="text-slate-500">No agent records returned.</p> : null}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">Workflow Queue</h3>
          <div className="space-y-2 text-xs">
            {workflows.map((workflow) => (
              <article key={workflow.workflowId} className="rounded border border-slate-800 bg-slate-950/50 p-2">
                <p className="text-slate-100">{workflow.target}</p>
                <p className="text-slate-400">id: {workflow.workflowId}</p>
                <p className="text-slate-400">status: {workflow.status}</p>
                <p className="text-slate-500">{workflow.createdAt ? new Date(workflow.createdAt).toLocaleString() : ''}</p>
              </article>
            ))}
            {workflows.length === 0 ? <p className="text-slate-500">No workflow entries returned.</p> : null}
          </div>
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-100">LLM Usage</h3>
          <p className="text-xs text-slate-300">requests: {String(llmUsage.total_requests ?? '0')}</p>
          <p className="text-xs text-slate-300">tokens: {String(llmUsage.total_tokens ?? '0')}</p>
          <p className="text-xs text-slate-300">cost usd: {String(llmUsage.total_cost_usd ?? '0')}</p>
          <div className="mt-2 space-y-1 text-xs">
            {Object.entries(llmByModel).map(([model, row]) => {
              const stats = asObject(row);
              return (
                <p key={model} className="text-slate-400">
                  {model}: {String(stats.requests ?? 0)} req · {String(stats.tokens ?? 0)} tok
                </p>
              );
            })}
          </div>
        </section>

        {statusError ? <p className="text-xs text-amber-300">{statusError}</p> : null}
      </section>
    </section>
  );
}

