"use client";

import { useQuery } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";
import { isUuid } from "@/lib/utils";

export function useSystemDiagnostics(params: { campaignId?: string; findingId?: string }) {
  const campaignId = params.campaignId?.trim();
  const findingId = params.findingId?.trim();

  const summaryQuery = useQuery({
    queryKey: queryKeys.diagnostics.summary(),
    queryFn: ({ signal }) => socApi.getDiagnosticsSummary(signal)
  });
  const healthQuery = useQuery({
    queryKey: queryKeys.diagnostics.health(),
    queryFn: ({ signal }) => socApi.getHealth(signal)
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.diagnostics.ready(),
    queryFn: ({ signal }) => socApi.getReadiness(signal)
  });
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

  return {
    summaryQuery,
    healthQuery,
    readinessQuery,
    campaignDiagnosticsQuery,
    findingDiagnosticsQuery
  };
}
