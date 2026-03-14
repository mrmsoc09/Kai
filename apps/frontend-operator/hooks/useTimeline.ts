"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { deriveTimelineItems } from "@/lib/utils/soc";
import { isUuid } from "@/lib/utils";

export function useTimeline(params: { campaignId?: string; findingId?: string }) {
  const campaignId = params.campaignId?.trim();
  const findingId = params.findingId?.trim();

  const campaignDiagnosticsQuery = useQuery({
    queryKey: queryKeys.campaigns.diagnostics(campaignId ?? "none"),
    queryFn: ({ signal }) => socApi.getCampaignDiagnostics(campaignId!, signal),
    enabled: Boolean(campaignId && isUuid(campaignId))
  });

  const findingDiagnosticsQuery = useQuery({
    queryKey: queryKeys.findings.detail(findingId ?? "none"),
    queryFn: ({ signal }) => socApi.getFindingDiagnostics(findingId!, signal),
    enabled: Boolean(findingId && isUuid(findingId))
  });

  const timeline = useMemo(
    () =>
      deriveTimelineItems({
        campaignId,
        findingId,
        campaignDiagnostics: campaignDiagnosticsQuery.data ?? null,
        findingDiagnostics: findingDiagnosticsQuery.data ?? null
      }),
    [campaignDiagnosticsQuery.data, campaignId, findingDiagnosticsQuery.data, findingId]
  );

  return {
    campaignDiagnosticsQuery,
    findingDiagnosticsQuery,
    timeline
  };
}
