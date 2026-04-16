import { ApiError, requestJson } from "@/lib/api/client";
import type {
  TerminalExecutionRequest,
  TerminalExecutionResult,
  TerminalLogsEnvelope,
  TerminalProvidersEnvelope,
  TmuxCreateSessionRequest,
  TmuxSessionListResponse
} from "@/lib/types";

const TMUX_CONTRACT_PENDING: TmuxSessionListResponse = {
  sessions: [],
  contract_pending: true,
  message: "tmux session API is not available yet. Terminal provider execution remains available."
};

function toPendingResponse(error: unknown): TmuxSessionListResponse {
  if (error instanceof ApiError && (error.status === 404 || error.status === 405 || error.status === 501)) {
    return TMUX_CONTRACT_PENDING;
  }
  throw error;
}

export function getTerminalProviders() {
  return requestJson<TerminalProvidersEnvelope>("/terminal/providers");
}

export function executeTerminalPrompt(payload: TerminalExecutionRequest) {
  return requestJson<TerminalExecutionResult>("/terminal/execute", {
    method: "POST",
    body: payload
  });
}

export function getTerminalLogs(limit = 50) {
  return requestJson<TerminalLogsEnvelope>(`/terminal/logs?limit=${encodeURIComponent(String(limit))}`);
}

export async function listTmuxSessions(): Promise<TmuxSessionListResponse> {
  try {
    return await requestJson<TmuxSessionListResponse>("/terminal/sessions");
  } catch (error) {
    return toPendingResponse(error);
  }
}

export async function createTmuxSession(body: TmuxCreateSessionRequest): Promise<TmuxSessionListResponse> {
  try {
    return await requestJson<TmuxSessionListResponse>("/terminal/sessions", {
      method: "POST",
      body
    });
  } catch (error) {
    return toPendingResponse(error);
  }
}

export async function attachTmuxSession(sessionId: string): Promise<TmuxSessionListResponse> {
  try {
    return await requestJson<TmuxSessionListResponse>(`/terminal/sessions/${sessionId}/attach`, {
      method: "POST"
    });
  } catch (error) {
    return toPendingResponse(error);
  }
}

export async function detachTmuxSession(sessionId: string): Promise<TmuxSessionListResponse> {
  try {
    return await requestJson<TmuxSessionListResponse>(`/terminal/sessions/${sessionId}/detach`, {
      method: "POST"
    });
  } catch (error) {
    return toPendingResponse(error);
  }
}

export async function killTmuxSession(sessionId: string): Promise<TmuxSessionListResponse> {
  try {
    return await requestJson<TmuxSessionListResponse>(`/terminal/sessions/${sessionId}/kill`, {
      method: "POST"
    });
  } catch (error) {
    return toPendingResponse(error);
  }
}
