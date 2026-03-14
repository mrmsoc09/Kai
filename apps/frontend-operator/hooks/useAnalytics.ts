"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

export function useAnalytics(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);
  const summaryQuery = useQuery({
    queryKey: queryKeys.soc.analytics(campaignIds),
    queryFn: ({ signal }) => socApi.getDiagnosticsSummary(signal)
  });
  const findingsQueueQuery = useQuery({
    queryKey: queryKeys.findings.queue(),
    queryFn: () => socApi.getFindingsReviewQueue({ limit: 500 })
  });

  const campaignStatusRows = useMemo(
    () => tracked.campaigns.map((item) => ({ id: item.campaign.id, status: item.campaign.status })),
    [tracked.campaigns]
  );

  return {
    tracked,
    summaryQuery,
    findingsQueueQuery,
    campaignStatusRows
  };
}
