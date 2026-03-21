export type WebSocketConnectionState = 'idle' | 'connecting' | 'connected' | 'disconnected' | 'error';

export interface SystemStatus {
  status: string;
  active_missions: number;
  completed_missions: number;
  worker_ok: boolean;
  queue_depth: number;
  memory_usage_mb: number;
  cpu_percent: number;
}
