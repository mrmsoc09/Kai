export type ApiErrorPayload = {
  detail?: string;
  message?: string;
  [key: string]: unknown;
};

export type HealthResponse = {
  status: string;
  services?: Record<string, unknown>;
  worker?: Record<string, unknown>;
  dependencies?: Record<string, unknown>;
};

export type AuditEvent = {
  id: string;
  event_type: string;
  actor: string | null;
  happened_at: string | null;
  phase_job_id?: string | null;
  tool_execution_id?: string | null;
  approval_gate_id?: string | null;
  message: string | null;
  payload: Record<string, unknown>;
};
