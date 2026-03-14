"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { deriveOverviewAlerts } from "@/lib/utils/soc";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

export function useAlerts(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);
  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.findings.queue(),
    queryFn: () => socApi.getFindingsReviewQueue({ limit: 500 })
  });

  const alerts = useMemo(
    () =>
      deriveOverviewAlerts({
        diagnostics: tracked.diagnostics,
        findings: findingsQueueQuery.data?.items ?? []
      }),
    [findingsQueueQuery.data?.items, tracked.diagnostics]
  );

  return {
    tracked,
    findingsQueueQuery,
    alerts
  };
}
