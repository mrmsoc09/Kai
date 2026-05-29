/**
 * Scan dispatch API — wraps the /api/v1/scan-pool/queue-batch endpoint.
 *
 * This is the Model A execution path: items flow through HuntScheduleJob →
 * WorkflowExecutor → real tool pipeline (subfinder → httpx → nuclei by
 * default, or whatever workflow_passive_triage resolves to).
 */
import { requestJson } from "@/lib/api/client";

export type QueueBatchItem = {
  program_id: string;
  scope_target_id?: string | null;
  subject_key: string;
  subject_type?: string;
  recommended_workflow?: string | null;
  program_name?: string | null;
  platform?: string | null;
};

export type QueueBatchRequest = {
  items: QueueBatchItem[];
  force?: boolean;
  safe_mode?: boolean;
  dry_run?: boolean;
  workflow_override?: string | null;
};

export type QueueBatchQueued = {
  item_index: number;
  schedule_job_id: string;
  celery_task_id: string;
  status: string;
};

export type QueueBatchError = {
  index: number;
  error: string;
  schedule_job_id?: string;
};

export type QueueBatchResponse = {
  queued: QueueBatchQueued[];
  errors: QueueBatchError[];
  total: number;
};

/**
 * Queue one or more items for scanning via the backend scan-pool pipeline.
 * Returns immediately — scans run asynchronously in Celery workers.
 */
export function queueBatch(body: QueueBatchRequest): Promise<QueueBatchResponse> {
  return requestJson<QueueBatchResponse>("/api/v1/scan-pool/queue-batch", {
    method: "POST",
    body,
  });
}
