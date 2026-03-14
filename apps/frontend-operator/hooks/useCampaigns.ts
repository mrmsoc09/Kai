"use client";

import { useQueries } from "@tanstack/react-query";

import { getCampaign } from "@/lib/api/campaigns";
import { queryKeys } from "@/lib/query-keys";

export function useCampaigns(campaignIds: string[]) {
  return useQueries({
    queries: campaignIds.map((campaignId) => ({
      queryKey: queryKeys.campaigns.detail(campaignId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getCampaign(campaignId, signal),
      retry: false
    }))
  });
}
