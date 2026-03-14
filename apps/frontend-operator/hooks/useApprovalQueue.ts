"use client";

import { useMemo } from "react";
import { useQueries } from "@tanstack/react-query";

import { inferApprovalGates } from "@/lib/approval-gates";
import { getCampaignDiagnostics } from "@/lib/api/campaigns";
import { queryKeys } from "@/lib/query-keys";

export function useApprovalQueue(campaignIds: string[]) {
  const diagnosticsQueries = useQueries({
    queries: campaignIds.map((campaignId) => ({
      queryKey: queryKeys.campaigns.diagnostics(campaignId),
      queryFn: ({ signal }: { signal: AbortSignal }) => getCampaignDiagnostics(campaignId, signal),
      retry: false
    }))
  });

  const approvalGates = useMemo(
    () =>
      diagnosticsQueries
        .filter((query) => query.isSuccess)
        .flatMap((query) => inferApprovalGates(query.data)),
    [diagnosticsQueries]
  );

  return { diagnosticsQueries, approvalGates };
}
