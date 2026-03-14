"use client";

import { useQuery } from "@tanstack/react-query";

import { getDiagnosticsSummary } from "@/lib/api/diagnostics";
import { queryKeys } from "@/lib/query-keys";

export function useDiagnosticsSummary() {
  return useQuery({
    queryKey: queryKeys.diagnostics.summary(),
    queryFn: ({ signal }) => getDiagnosticsSummary(signal)
  });
}
