"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { deriveAttackSurfaceRows } from "@/lib/utils/soc";

const FINDING_DIAGNOSTICS_LIMIT = 40;

export function useAttackSurface(campaignId?: string) {
  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.soc.attackSurface(campaignId),
    queryFn: () => socApi.getFindingsReviewQueue({ campaignId, limit: 500 })
  });

  const findingIds = (findingsQueueQuery.data?.items ?? [])
    .map((item) => item.finding_id)
    .slice(0, FINDING_DIAGNOSTICS_LIMIT);

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

  const assetRows = useMemo(
    () => deriveAttackSurfaceRows(findingsQueueQuery.data?.items ?? [], findingDiagnostics),
    [findingDiagnostics, findingsQueueQuery.data?.items]
  );

  const isLoading = findingsQueueQuery.isLoading || findingQueries.some((query) => query.isLoading);
  const errors = [
    ...(findingsQueueQuery.isError ? [findingsQueueQuery.error] : []),
    ...findingQueries.filter((query) => query.isError).map((query) => query.error)
  ];

  return {
    findingsQueueQuery,
    findingQueries,
    findingDiagnostics,
    assetRows,
    isLoading,
    errors
  };
}
