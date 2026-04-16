export type TerminalProvidersEnvelope = {
  providers: Record<
    string,
    {
      available: boolean;
      allowed_models?: string[];
      default_model?: string;
    }
  >;
};

export type TerminalExecutionRequest = {
  provider: string;
  prompt: string;
  model?: string;
  timeout_seconds?: number;
};

export type TerminalExecutionResult = {
  provider: string;
  model?: string | null;
  return_code: number;
  timed_out: boolean;
  duration_ms: number;
  stdout: string;
  ok: boolean;
};

export type TerminalLogsEnvelope = {
  logs: Array<{
    ts?: number;
    provider?: string;
    model?: string | null;
    timeout_seconds?: number;
    duration_ms?: number;
    return_code?: number;
    timed_out?: boolean;
    prompt_preview?: string;
    stdout_preview?: string;
    stderr_preview?: string;
    mission_id?: string;
    artifacts?: string[];
  }>;
};

export type TmuxSession = {
  session_id: string;
  name: string;
  status: "ATTACHED" | "DETACHED" | "EXITED";
  windows: number;
  last_activity_at?: string;
  mission_id?: string;
};

export type TmuxSessionListResponse = {
  sessions: TmuxSession[];
  contract_pending?: boolean;
  message?: string;
};

export type TmuxCreateSessionRequest = {
  name: string;
  mission_id?: string;
  provider?: string;
  model?: string;
};
