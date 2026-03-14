"use client";

import { useQuery } from "@tanstack/react-query";

import { getFindingsReviewQueue } from "@/lib/api/findings";
import { queryKeys } from "@/lib/query-keys";

export function useFindingsQueue(campaignId?: string) {
  return useQuery({
    queryKey: queryKeys.findings.queue(campaignId),
    queryFn: () => getFindingsReviewQueue({ campaignId })
  });
}
