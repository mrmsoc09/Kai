"use client";

import { useMemo } from "react";

import { derivePlaybooks } from "@/lib/utils/soc";
import { useTrackedCampaignData } from "@/hooks/useTrackedCampaignData";

export function usePlaybooks(campaignIds: string[]) {
  const tracked = useTrackedCampaignData(campaignIds);
  const playbooks = useMemo(() => derivePlaybooks(tracked.campaigns), [tracked.campaigns]);

  return {
    tracked,
    playbooks
  };
}
