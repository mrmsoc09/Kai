"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { extractIocs } from "@/lib/utils/soc";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

const FINDING_DIAGNOSTICS_LIMIT = 40;

export function useIoc(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);

  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.findings.queue(),
    queryFn: () => socApi.getFindingsReviewQueue({ limit: 400 })
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

  const iocs = useMemo(
    () =>
      extractIocs({
        campaignDiagnostics: tracked.diagnostics,
        findingDiagnostics,
        findings: findingsQueueQuery.data?.items ?? []
      }),
    [findingDiagnostics, findingsQueueQuery.data?.items, tracked.diagnostics]
  );

  return {
    tracked,
    findingsQueueQuery,
    findingDiagnostics,
    iocs
  };
}
