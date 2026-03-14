"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { extractTechnologyHints } from "@/lib/utils/soc";

const MAX_FINDINGS = 30;

export function useThreatIntel(campaignId?: string) {
  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.soc.threatIntel(campaignId),
    queryFn: () => socApi.getFindingsReviewQueue({ campaignId, limit: 300 })
  });

  const findingIds = (findingsQueueQuery.data?.items ?? [])
    .map((item) => item.finding_id)
    .slice(0, MAX_FINDINGS);

  const findingQueries = useQueries({
    queries: findingIds.map((findingId) => ({
      queryKey: queryKeys.findings.detail(findingId),
      queryFn: ({ signal }: { signal: AbortSignal }) => socApi.getFindingDiagnostics(findingId, signal),
      retry: false
    }))
  });

  const findingDiagnostics = useMemo(
    () => findingQueries.filter((query) => query.isSuccess).map((query) => query.data),
    [findingQueries]
  );

  const technologyCounts = useMemo(() => {
    const counter = new Map<string, number>();
    for (const finding of findingDiagnostics) {
      for (const observation of finding.recent_observations) {
        const text = `${observation.title ?? ""} ${observation.summary ?? ""}`;
        for (const tech of extractTechnologyHints(text)) {
          counter.set(tech, (counter.get(tech) ?? 0) + 1);
        }
      }
    }
    return Array.from(counter.entries())
      .map(([technology, count]) => ({ technology, count }))
      .sort((a, b) => b.count - a.count);
  }, [findingDiagnostics]);

  return {
    findingsQueueQuery,
    findingDiagnostics,
    findingQueries,
    technologyCounts
  };
}
