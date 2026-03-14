"use client";

import { useQuery } from "@tanstack/react-query";

import { getFindingDiagnostics } from "@/lib/api/findings";
import { queryKeys } from "@/lib/query-keys";

export function useFinding(findingId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.findings.detail(findingId),
    queryFn: ({ signal }) => getFindingDiagnostics(findingId, signal),
    enabled
  });
}
