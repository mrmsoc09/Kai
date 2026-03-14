"use client";

import { useQuery } from "@tanstack/react-query";

import { getCampaign } from "@/lib/api/campaigns";
import { queryKeys } from "@/lib/query-keys";

export function useCampaign(campaignId: string, enabled = true) {
  return useQuery({
    queryKey: queryKeys.campaigns.detail(campaignId),
    queryFn: ({ signal }) => getCampaign(campaignId, signal),
    enabled
  });
}
