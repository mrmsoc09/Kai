const TRACKED_CAMPAIGN_IDS_KEY = "k1.operator.tracked_campaign_ids";

export function loadTrackedCampaignIds(): string[] {
  if (typeof window === "undefined") {
    return [];
  }
  const raw = window.localStorage.getItem(TRACKED_CAMPAIGN_IDS_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((item): item is string => typeof item === "string");
  } catch {
    return [];
  }
}

export function saveTrackedCampaignIds(ids: string[]): void {
  if (typeof window === "undefined") {
    return;
  }
  const deduped = Array.from(new Set(ids));
  window.localStorage.setItem(TRACKED_CAMPAIGN_IDS_KEY, JSON.stringify(deduped));
}

export function addTrackedCampaignId(ids: string[], campaignId: string): string[] {
  if (ids.includes(campaignId)) {
    return ids;
  }
  return [...ids, campaignId];
}

export function removeTrackedCampaignId(ids: string[], campaignId: string): string[] {
  return ids.filter((id) => id !== campaignId);
}
