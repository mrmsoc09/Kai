"use client";

import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

import { socApi } from "@/lib/api/soc";
import { queryKeys } from "@/lib/query-keys";

export function useTrackedCampaignData(campaignIds: string[]) {
  const campaignQueries = useQueries({
    queries: campaignIds.map((campaignId) => ({
      queryKey: queryKeys.campaigns.detail(campaignId),
      queryFn: ({ signal }: { signal: AbortSignal }) => socApi.getCampaign(campaignId, signal),
      retry: false
    }))
  });

  const diagnosticsQueries = useQueries({
    queries: campaignIds.map((campaignId) => ({
      queryKey: queryKeys.campaigns.diagnostics(campaignId),
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        socApi.getCampaignDiagnostics(campaignId, signal),
      retry: false
    }))
  });

  const campaigns = useMemo(
    () => campaignQueries.filter((query) => query.isSuccess).map((query) => query.data),
    [campaignQueries]
  );

  const diagnostics = useMemo(
    () => diagnosticsQueries.filter((query) => query.isSuccess).map((query) => query.data),
    [diagnosticsQueries]
  );

  const errors = useMemo(
    () => [
      ...campaignQueries
        .map((query, index) => ({ query, campaignId: campaignIds[index] ?? "unknown" }))
        .filter((entry) => entry.query.isError)
        .map((entry) => ({ scope: "campaign" as const, campaignId: entry.campaignId, error: entry.query.error })),
      ...diagnosticsQueries
        .map((query, index) => ({ query, campaignId: campaignIds[index] ?? "unknown" }))
        .filter((entry) => entry.query.isError)
        .map((entry) => ({
          scope: "diagnostics" as const,
          campaignId: entry.campaignId,
          error: entry.query.error
        }))
    ],
    [campaignIds, campaignQueries, diagnosticsQueries]
  );

  const isLoading =
    campaignQueries.some((query) => query.isLoading) || diagnosticsQueries.some((query) => query.isLoading);

  return {
    campaigns,
    diagnostics,
    campaignQueries,
    diagnosticsQueries,
    errors,
    isLoading
  };
}
