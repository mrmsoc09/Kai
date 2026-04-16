"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { useTerminalCockpit } from "@/hooks/useTerminalCockpit";

import { MissionLinkedSidePanel } from "@/components/cockpit/MissionLinkedSidePanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

// ── Types ──────────────────────────────────────────────────────────────────

type LocalTranscriptRun = {
  id: string;
  provider: string;
  model?: string | null;
  ok: boolean;
  returnCode: number;
  timedOut: boolean;
  durationMs: number;
  prompt: string;
  stdout: string;
};

// ── Helpers ────────────────────────────────────────────────────────────────

/**
 * Accumulate stdout from local runs into a scrollable terminal-like buffer.
 * Displayed oldest-first so new output appends naturally at the bottom.
 *
 * WebSocket contract stub:
 *   When the backend mounts terminal_bridge.py on /ws/terminal/{session_id},
 *   replace this accumulated buffer with a live PTY stream:
 *     const ws = new WebSocket(`ws://backend/ws/terminal/${sessionId}`);
 *     ws.onmessage = (e) => appendToBuffer(e.data);
 *   Protocol: binary frames for PTY output, text JSON for control messages.
 *   See: apps/backend/src/terminal_bridge.py — TerminalBridge.connect()
 */
function buildOutputBuffer(runs: LocalTranscriptRun[], attachedSessionId: string): string {
  const lines: string[] = [];
  if (attachedSessionId) {
    lines.push(`◆ session: ${attachedSessionId}`);
    lines.push("─".repeat(48));
    lines.push("");
  }
  const ordered = [...runs].reverse(); // chronological (oldest first)
  for (const run of ordered) {
    const header = `$ [${run.provider}${run.model ? `/${run.model}` : ""}]  ${run.prompt}`;
    lines.push(header);
    if (run.stdout) {
      lines.push(run.stdout);
    } else {
      lines.push("(no output)");
    }
    const exitLine = run.ok
      ? `→ ok  (${run.durationMs}ms)`
      : `→ exit ${run.returnCode}${run.timedOut ? "  [timeout]" : ""}  (${run.durationMs}ms)`;
    lines.push(exitLine);
    lines.push("");
  }
  return lines.join("\n");
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function TerminalPage() {
  const terminal = useTerminalCockpit(40);
  const [provider, setProvider] = useState("gemini");
  const [model, setModel] = useState("");
  const [timeoutSeconds, setTimeoutSeconds] = useState(180);
  const [prompt, setPrompt] = useState("");
  const [sessionName, setSessionName] = useState("");
  const [missionId, setMissionId] = useState("");
  const [attachedSessionId, setAttachedSessionId] = useState("");
  const [localRuns, setLocalRuns] = useState<LocalTranscriptRun[]>([]);

  const outputPaneRef = useRef<HTMLPreElement>(null);

  // Read mission_id from query string on mount
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const fromQuery = new URLSearchParams(window.location.search).get("mission_id") ?? "";
    if (fromQuery.length > 0) {
      setMissionId(fromQuery);
    }
  }, []);

  // Auto-select provider from backend availability; prefer gemini, fall back to first
  useEffect(() => {
    const providers = terminal.providersQuery.data?.providers ?? {};
    const available = Object.entries(providers)
      .filter(([, value]) => value.available)
      .map(([key]) => key);
    if (available.length === 0) {
      return;
    }
    const preferred = available.includes("gemini") ? "gemini" : available[0];
    if (!available.includes(provider)) {
      setProvider(preferred);
    }
    const providerConfig = providers[preferred];
    if (providerConfig?.default_model && !model) {
      setModel(providerConfig.default_model);
    } else if (providerConfig?.allowed_models?.[0] && !model) {
      setModel(providerConfig.allowed_models[0]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [terminal.providersQuery.data?.providers]);

  // Auto-scroll the output pane to bottom when new content arrives
  useEffect(() => {
    const pane = outputPaneRef.current;
    if (pane) {
      pane.scrollTop = pane.scrollHeight;
    }
  }, [localRuns]);

  const providerOptions = useMemo(
    () => terminal.providersQuery.data?.providers ?? {},
    [terminal.providersQuery.data?.providers]
  );
  const allowedModels = providerOptions[provider]?.allowed_models ?? [];
  const sessionRows = terminal.sessionsQuery.data?.sessions ?? [];
  const tmuxContractPending = Boolean(terminal.sessionsQuery.data?.contract_pending);

  // Merge API log history with local in-session runs
  const transcriptRows = useMemo(() => {
    const apiLogs = (terminal.logsQuery.data?.logs ?? []).map((row, index) => ({
      id: `api-${row.ts ?? index}`,
      provider: row.provider ?? "unknown",
      model: row.model ?? null,
      ok: (row.return_code ?? 1) === 0 && !Boolean(row.timed_out),
      returnCode: row.return_code ?? 1,
      timedOut: Boolean(row.timed_out),
      durationMs: row.duration_ms ?? 0,
      prompt: row.prompt_preview ?? "",
      stdout: row.stdout_preview ?? ""
    }));
    return [...localRuns, ...apiLogs].slice(0, 40);
  }, [localRuns, terminal.logsQuery.data?.logs]);

  const artifactLinks = useMemo(() => {
    const direct = (terminal.logsQuery.data?.logs ?? [])
      .flatMap((row) => (Array.isArray(row.artifacts) ? row.artifacts : []))
      .filter((value): value is string => typeof value === "string" && value.length > 0);
    return direct.length > 0 ? direct : ["/artifacts/logs"];
  }, [terminal.logsQuery.data?.logs]);

  // Build the session output buffer from accumulated local runs
  const outputBuffer = useMemo(
    () => buildOutputBuffer(localRuns.slice(0, 12), attachedSessionId),
    [localRuns, attachedSessionId]
  );

  function onRunPrompt(event: FormEvent) {
    event.preventDefault();
    const trimmed = prompt.trim();
    if (!trimmed) {
      return;
    }
    terminal.executeMutation.mutate(
      {
        provider,
        prompt: trimmed,
        model: model || undefined,
        timeout_seconds: timeoutSeconds
      },
      {
        onSuccess: (response) => {
          setLocalRuns((prev) => [
            {
              id: `${Date.now()}-${Math.random()}`,
              provider: response.provider,
              model: response.model,
              ok: response.ok,
              returnCode: response.return_code,
              timedOut: response.timed_out,
              durationMs: response.duration_ms,
              prompt: trimmed,
              stdout: response.stdout
            },
            ...prev
          ]);
          setPrompt("");
        }
      }
    );
  }

  function onCreateSession(event: FormEvent) {
    event.preventDefault();
    const name = sessionName.trim();
    if (!name) {
      return;
    }
    terminal.createSessionMutation.mutate({
      name,
      mission_id: missionId || undefined,
      provider,
      model: model || undefined
    });
    setSessionName("");
  }

  function onAttachSession(sessionId: string) {
    setAttachedSessionId(sessionId);
    terminal.attachSessionMutation.mutate(sessionId);
  }

  function onDetachSession(sessionId: string) {
    if (attachedSessionId === sessionId) {
      setAttachedSessionId("");
    }
    terminal.detachSessionMutation.mutate(sessionId);
  }

  function onKillSession(sessionId: string) {
    if (attachedSessionId === sessionId) {
      setAttachedSessionId("");
    }
    terminal.killSessionMutation.mutate(sessionId);
  }

  return (
    <div className="operator-grid">
      <PageHeader
        title="Terminal"
        description="Provider-backed operator terminal with tmux session governance and mission context linkage."
      />

      <Alert className="border-review/40 bg-review/10 text-review">
        Safe-command notice: execute only scope-approved commands. Keep all actions mission-linked and auditable.
      </Alert>

      {/* ── Top row: Sessions + Mission context ───────────────────── */}
      <div className="grid gap-4 xl:grid-cols-[1.3fr_1fr]">
        {/* Session management */}
        <Card>
          <CardHeader>
            <CardTitle>tmux Sessions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={onCreateSession}>
              <Input
                value={sessionName}
                onChange={(event) => setSessionName(event.target.value)}
                placeholder="new session name"
              />
              <Button type="submit" variant="secondary" disabled={terminal.createSessionMutation.isPending}>
                Create Session
              </Button>
            </form>

            {tmuxContractPending ? (
              <Alert className="border-border bg-elevated text-muted">
                {terminal.sessionsQuery.data?.message ??
                  "tmux session API contract is pending — backend endpoint /terminal/sessions is not yet mounted. Provider execution remains available."}
              </Alert>
            ) : null}

            {sessionRows.length > 0 ? (
              <div className="space-y-2">
                {sessionRows.map((session) => {
                  const isAttached = attachedSessionId === session.session_id;
                  return (
                    <div
                      key={session.session_id}
                      className={`rounded-md border p-2 ${isAttached ? "border-active/50 bg-active/5" : "border-border bg-elevated"}`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="text-sm font-medium text-foreground">
                            {session.name}
                            {isAttached ? (
                              <span className="ml-2 text-xs text-active">● attached</span>
                            ) : null}
                          </p>
                          <p className="font-mono text-xs text-muted">{session.session_id}</p>
                          <div className="mt-0.5 flex flex-wrap gap-3 text-xs text-muted">
                            <span>status: {session.status}</span>
                            {session.windows != null ? (
                              <span>windows: {session.windows}</span>
                            ) : null}
                            {session.mission_id ? (
                              <span>mission: {session.mission_id}</span>
                            ) : null}
                            {session.last_activity_at ? (
                              <span>last: {session.last_activity_at}</span>
                            ) : null}
                          </div>
                        </div>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        <Button
                          size="sm"
                          variant={isAttached ? "secondary" : "outline"}
                          onClick={() => onAttachSession(session.session_id)}
                          disabled={isAttached}
                        >
                          {isAttached ? "Attached" : "Attach"}
                        </Button>
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => onDetachSession(session.session_id)}
                          disabled={!isAttached}
                        >
                          Detach
                        </Button>
                        <Button
                          size="sm"
                          variant="destructive"
                          onClick={() => onKillSession(session.session_id)}
                        >
                          Kill
                        </Button>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                title="No tmux sessions"
                description="Create a session above, or connect backend tmux APIs to populate this list."
              />
            )}
          </CardContent>
        </Card>

        <MissionLinkedSidePanel missionId={missionId || "unassigned"} missionStatus={undefined} />
      </div>

      {/* ── Provider console ───────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Provider Console</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {/* Provider / model / timeout / mission controls */}
          <div className="grid gap-2 md:grid-cols-4">
            {/* Provider selector — populated from backend; provider-agnostic */}
            {Object.keys(providerOptions).length > 0 ? (
              <Select value={provider} onChange={(event) => setProvider(event.target.value)}>
                {Object.entries(providerOptions).map(([key, config]) => (
                  <option key={key} value={key} disabled={!config.available}>
                    {key}
                    {!config.available ? " (offline)" : ""}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                value={provider}
                onChange={(event) => setProvider(event.target.value)}
                placeholder="provider (e.g. gemini, claude, codex)"
              />
            )}

            {/* Model selector — driven by provider config, falls back to free text */}
            {allowedModels.length > 0 ? (
              <Select value={model} onChange={(event) => setModel(event.target.value)}>
                {allowedModels.map((modelOption) => (
                  <option key={modelOption} value={modelOption}>
                    {modelOption}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                value={model}
                onChange={(event) => setModel(event.target.value)}
                placeholder="model (optional)"
              />
            )}

            <Input
              value={String(timeoutSeconds)}
              onChange={(event) => setTimeoutSeconds(Number(event.target.value) || 180)}
              placeholder="timeout (seconds)"
            />
            <Input
              value={missionId}
              onChange={(event) => setMissionId(event.target.value)}
              placeholder="mission id (optional)"
            />
          </div>

          {/* Prompt input */}
          <form className="space-y-2" onSubmit={onRunPrompt}>
            <Textarea
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Enter a prompt for the selected provider…"
              rows={3}
            />
            <Button
              type="submit"
              disabled={terminal.executeMutation.isPending || prompt.trim().length === 0}
            >
              {terminal.executeMutation.isPending ? "Running…" : "Run Prompt"}
            </Button>
          </form>

          {terminal.executeMutation.isError ? (
            <ErrorState error={terminal.executeMutation.error} title="Execution failed" />
          ) : null}

          {/* ── Session Output Buffer ──────────────────────────────── */}
          {/*
           * Streaming contract stub:
           *   This pane currently shows accumulated stdout from completed runs.
           *   Replace with live streaming once the backend mounts terminal_bridge.py:
           *     - Backend route: /ws/terminal/{session_id}  (WebSocket)
           *     - Frontend: connect xterm.js to ws:// and pipe binary PTY frames
           *     - Control messages: JSON text frames { "type": "resize", "cols": N, "rows": N }
           *   See: apps/backend/src/terminal_bridge.py — TerminalBridge.connect()
           */}
          <div className="space-y-1">
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">
                Session Output Buffer
                {attachedSessionId ? (
                  <span className="ml-2 font-normal text-active">● {attachedSessionId.slice(0, 8)}…</span>
                ) : null}
              </p>
              {localRuns.length > 0 ? (
                <button
                  type="button"
                  className="text-xs text-muted hover:text-foreground"
                  onClick={() => setLocalRuns([])}
                >
                  Clear
                </button>
              ) : null}
            </div>
            <div className="rounded-md border border-border bg-black">
              {localRuns.length === 0 && !attachedSessionId ? (
                <p className="p-3 text-xs text-muted">
                  No output yet. Run a provider command to populate this buffer.
                  Live PTY streaming requires the tmux WebSocket backend contract.
                </p>
              ) : (
                <pre
                  ref={outputPaneRef}
                  className="max-h-72 overflow-auto whitespace-pre-wrap p-3 text-xs text-success"
                >
                  {outputBuffer}
                </pre>
              )}
            </div>
            {attachedSessionId && localRuns.length === 0 ? (
              <p className="text-[11px] text-muted">
                Session attached. Live output requires WebSocket streaming — run a provider command
                to see buffered output here.
              </p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* ── Transcript + Artifacts row ─────────────────────────────── */}
      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Run Transcript</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {terminal.logsQuery.isError ? (
              <ErrorState error={terminal.logsQuery.error} title="Terminal logs unavailable" />
            ) : null}
            {transcriptRows.length > 0 ? (
              <div className="space-y-2">
                {transcriptRows.map((row) => (
                  <div key={row.id} className="rounded-md border border-border bg-elevated p-2">
                    <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
                      <p className="font-medium text-muted">
                        {row.provider}
                        {row.model ? ` / ${row.model}` : ""}
                      </p>
                      <p className={row.ok ? "text-success" : "text-danger"}>
                        {row.ok ? "ok" : `exit ${row.returnCode}`}
                        {row.timedOut ? "  (timeout)" : ""}
                        <span className="ml-2 text-muted">{row.durationMs}ms</span>
                      </p>
                    </div>
                    <p className="mt-1 break-all text-xs text-muted">↳ {row.prompt}</p>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-border bg-black p-2 text-xs text-foreground">
                      {row.stdout || "(no output)"}
                    </pre>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No transcript entries"
                description="Run a provider command to populate output history."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Generated Artifacts</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {artifactLinks.map((artifact) => (
                <li key={artifact}>
                  <a
                    href={artifact}
                    className="break-all text-sm text-active hover:underline"
                    target="_blank"
                    rel="noreferrer"
                  >
                    {artifact}
                  </a>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
