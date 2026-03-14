"use client";

import { useEffect, useState } from "react";

import {
  addTrackedCampaignId,
  loadTrackedCampaignIds,
  removeTrackedCampaignId,
  saveTrackedCampaignIds
} from "@/lib/tracked-campaigns";

export function useTrackedCampaignIds() {
  const [trackedCampaignIds, setTrackedCampaignIds] = useState<string[]>([]);

  useEffect(() => {
    setTrackedCampaignIds(loadTrackedCampaignIds());
  }, []);

  useEffect(() => {
    saveTrackedCampaignIds(trackedCampaignIds);
  }, [trackedCampaignIds]);

  return {
    trackedCampaignIds,
    setTrackedCampaignIds,
    addCampaignId: (campaignId: string) =>
      setTrackedCampaignIds((prev) => addTrackedCampaignId(prev, campaignId)),
    removeCampaignId: (campaignId: string) =>
      setTrackedCampaignIds((prev) => removeTrackedCampaignId(prev, campaignId))
  };
}
