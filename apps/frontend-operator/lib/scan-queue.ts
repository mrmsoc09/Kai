import type { OpportunityRankingRow } from "@/hooks/useOpportunityRankings";

export type ScanQueueItem = {
  id: string;
  opportunityId: string;
  programId: string;
  subjectType: string;
  subjectKey: string;
  recommendedWorkflow: string | null;
  selectionScore: number;
  addedAt: string;
  campaignId: string | null;
  status: "queued" | "running" | "approved" | "killed" | "completed" | "failed";
  priority: number;
};

export const SCAN_QUEUE_KEY = "kai.scan_queue_items_v1";

export function loadScanQueue(): ScanQueueItem[] {
  if (typeof window === "undefined") {
    return [];
  }
  const raw = window.localStorage.getItem(SCAN_QUEUE_KEY);
  if (!raw) {
    return [];
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter(
      (item): item is ScanQueueItem =>
        item !== null &&
        typeof item === "object" &&
        typeof item.id === "string" &&
        typeof item.opportunityId === "string" &&
        typeof item.status === "string"
    );
  } catch {
    return [];
  }
}

export function saveScanQueue(items: ScanQueueItem[]): void {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(SCAN_QUEUE_KEY, JSON.stringify(items));
}

export function addToScanQueue(
  items: ScanQueueItem[],
  opportunity: OpportunityRankingRow
): ScanQueueItem[] {
  const alreadyExists = items.some((item) => item.opportunityId === opportunity.id);
  if (alreadyExists) {
    return items;
  }
  const maxPriority = items.reduce((max, item) => Math.max(max, item.priority), 0);
  const newItem: ScanQueueItem = {
    id: crypto.randomUUID(),
    opportunityId: opportunity.id,
    programId: opportunity.programId,
    subjectType: opportunity.subjectType,
    subjectKey: opportunity.subjectKey,
    recommendedWorkflow: opportunity.recommendedWorkflow,
    selectionScore: opportunity.selectionScore,
    addedAt: new Date().toISOString(),
    campaignId: null,
    status: "queued",
    priority: maxPriority + 1
  };
  return [...items, newItem];
}

export function removeFromScanQueue(items: ScanQueueItem[], id: string): ScanQueueItem[] {
  return items.filter((item) => item.id !== id);
}

export function reorderScanQueue(
  items: ScanQueueItem[],
  fromIndex: number,
  toIndex: number
): ScanQueueItem[] {
  if (fromIndex === toIndex) {
    return items;
  }
  const clampedFrom = Math.max(0, Math.min(fromIndex, items.length - 1));
  const clampedTo = Math.max(0, Math.min(toIndex, items.length - 1));
  if (clampedFrom === clampedTo) {
    return items;
  }
  const next = [...items];
  const [moved] = next.splice(clampedFrom, 1);
  next.splice(clampedTo, 0, moved);
  return next.map((item, index) => ({ ...item, priority: index + 1 }));
}

export function updateScanQueueItem(
  items: ScanQueueItem[],
  id: string,
  patch: Partial<ScanQueueItem>
): ScanQueueItem[] {
  return items.map((item) => (item.id === id ? { ...item, ...patch } : item));
}
