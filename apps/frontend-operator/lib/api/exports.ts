import { postJsonAllow422, requestJson } from "@/lib/api/client";
import type { SubmissionExportResponse } from "@/lib/types";

export type ExportProvider = "hackerone" | "bugcrowd" | "intigriti";

export function previewExport(
  findingId: string,
  provider: ExportProvider,
  options?: { actor?: string; submissionDraftId?: string; intentionId?: string }
) {
  const search = new URLSearchParams();
  if (options?.actor) {
    search.set("actor", options.actor);
  }
  if (options?.submissionDraftId) {
    search.set("submission_draft_id", options.submissionDraftId);
  }
  if (options?.intentionId) {
    search.set("intention_id", options.intentionId);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return requestJson<SubmissionExportResponse>(`/api/v1/findings/${findingId}/export/${provider}/preview${suffix}`);
}

export async function stageExport(
  findingId: string,
  provider: ExportProvider,
  body?: { actor?: string; submission_draft_id?: string; intention_id?: string }
): Promise<SubmissionExportResponse> {
  const { data } = await postJsonAllow422<SubmissionExportResponse>(
    `/api/v1/findings/${findingId}/export/${provider}`,
    body
  );
  return data;
}
