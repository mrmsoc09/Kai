"use client";

import { useQuery } from "@tanstack/react-query";

import { getCampaign, getCampaignDiagnostics } from "@/lib/api/campaigns";
import { queryKeys } from "@/lib/query-keys";

export function useCampaignDetails(campaignId: string, enabled = true) {
  const campaign = useQuery({
    queryKey: queryKeys.campaigns.detail(campaignId),
    queryFn: ({ signal }) => getCampaign(campaignId, signal),
    enabled
  });

  const diagnostics = useQuery({
    queryKey: queryKeys.campaigns.diagnostics(campaignId),
    queryFn: ({ signal }) => getCampaignDiagnostics(campaignId, signal),
    enabled
  });

  return { campaign, diagnostics };
}
