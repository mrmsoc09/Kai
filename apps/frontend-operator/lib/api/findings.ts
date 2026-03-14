import { requestJson } from "@/lib/api/client";
import type {
  FindingDiagnosticsResponse,
  FindingReviewActionRequest,
  FindingReviewActionResponse,
  FindingReviewQueueResponse,
  PrepareSubmissionResponse
} from "@/lib/types";

export function getFindingsReviewQueue(params?: { campaignId?: string; limit?: number }) {
  const search = new URLSearchParams();
  if (params?.campaignId) {
    search.set("campaign_id", params.campaignId);
  }
  if (params?.limit) {
    search.set("limit", String(params.limit));
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<FindingReviewQueueResponse>(`/api/v1/findings/review-queue${suffix}`);
}

export function getFindingDiagnostics(findingId: string, signal?: AbortSignal) {
  return requestJson<FindingDiagnosticsResponse>(`/api/v1/findings/${findingId}/diagnostics`, { signal });
}

export function reviewFinding(findingId: string, body: FindingReviewActionRequest) {
  return requestJson<FindingReviewActionResponse>(`/api/v1/findings/${findingId}/review`, {
    method: "POST",
    body
  });
}

export function prepareSubmission(findingId: string, reviewerId: string) {
  return requestJson<PrepareSubmissionResponse>(`/api/v1/findings/${findingId}/prepare-submission`, {
    method: "POST",
    body: { reviewer_id: reviewerId }
  });
}
