"use client";

import { useCallback, useEffect, useState } from "react";

import type { OpportunityRankingRow } from "@/hooks/useOpportunityRankings";
import {
  addToScanQueue,
  loadScanQueue,
  reorderScanQueue,
  removeFromScanQueue,
  saveScanQueue,
  updateScanQueueItem,
  type ScanQueueItem
} from "@/lib/scan-queue";

export type { ScanQueueItem };

export function useScanQueue() {
  const [items, setItems] = useState<ScanQueueItem[]>([]);

  // Defer localStorage read to avoid SSR/hydration mismatch
  useEffect(() => {
    setItems(loadScanQueue());
  }, []);

  const persist = useCallback((next: ScanQueueItem[]) => {
    saveScanQueue(next);
    setItems(next);
  }, []);

  const addItem = useCallback(
    (opportunity: OpportunityRankingRow) => {
      setItems((current) => {
        const next = addToScanQueue(current, opportunity);
        saveScanQueue(next);
        return next;
      });
    },
    []
  );

  const removeItem = useCallback(
    (id: string) => {
      setItems((current) => {
        const next = removeFromScanQueue(current, id);
        saveScanQueue(next);
        return next;
      });
    },
    []
  );

  const reorder = useCallback(
    (fromIndex: number, toIndex: number) => {
      setItems((current) => {
        const next = reorderScanQueue(current, fromIndex, toIndex);
        saveScanQueue(next);
        return next;
      });
    },
    []
  );

  const updateItem = useCallback(
    (id: string, patch: Partial<ScanQueueItem>) => {
      setItems((current) => {
        const next = updateScanQueueItem(current, id, patch);
        saveScanQueue(next);
        return next;
      });
    },
    []
  );

  const clearCompleted = useCallback(() => {
    setItems((current) => {
      const next = current.filter(
        (item) => item.status !== "completed" && item.status !== "killed" && item.status !== "failed"
      );
      saveScanQueue(next);
      return next;
    });
  }, []);

  // Suppress persist in the initial no-op persist reference (not directly used externally,
  // but kept so derived callers can use persist if they need a direct setter)
  void persist;

  return { items, addItem, removeItem, reorder, updateItem, clearCompleted };
}
