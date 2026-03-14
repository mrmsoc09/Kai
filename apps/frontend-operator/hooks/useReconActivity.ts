"use client";

import { useMemo } from "react";

import { deriveReconPhaseRows, flattenRecentAuditEvents } from "@/lib/utils/soc";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

export function useReconActivity(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);

  const reconPhaseRows = useMemo(() => deriveReconPhaseRows(tracked.campaigns), [tracked.campaigns]);
  const reconAuditEvents = useMemo(() => {
    const rows = flattenRecentAuditEvents({ campaignDiagnostics: tracked.diagnostics });
    return rows.filter((event) => {
      const loweredType = event.event_type.toLowerCase();
      return (
        loweredType.includes("phase") ||
        loweredType.includes("tool_execution") ||
        loweredType.includes("campaign")
      );
    });
  }, [tracked.diagnostics]);

  return {
    trackedCampaigns: tracked.campaigns,
    trackedDiagnostics: tracked.diagnostics,
    trackedErrors: tracked.errors,
    reconPhaseRows,
    reconAuditEvents,
    isLoading: tracked.isLoading
  };
}
