import { requestJson } from "@/lib/api/client";
import type { DiagnosticsSummaryResponse, HealthResponse } from "@/lib/types";

export function getDiagnosticsSummary(signal?: AbortSignal) {
  return requestJson<DiagnosticsSummaryResponse>("/api/v1/diagnostics/summary", { signal });
}

export function getHealth(signal?: AbortSignal) {
  return requestJson<HealthResponse>("/health", { signal });
}

export function getReadiness(signal?: AbortSignal) {
  return requestJson<HealthResponse>("/readyz", { signal });
}
