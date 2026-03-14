"use client";

import { useQuery } from "@tanstack/react-query";

import { previewExport, type ExportProvider } from "@/lib/api/exports";
import { queryKeys } from "@/lib/query-keys";

export function useExportPreview(
  findingId: string,
  provider: ExportProvider,
  draftId?: string,
  actor?: string,
  enabled = true
) {
  return useQuery({
    queryKey: queryKeys.findings.exportPreview(findingId, provider, draftId),
    queryFn: () => previewExport(findingId, provider, { submissionDraftId: draftId, actor }),
    enabled
  });
}
