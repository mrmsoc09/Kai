"use client";

import { useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export function useAnalystBriefing(programId?: string) {
  const briefingQuery = useQuery({
    queryKey: queryKeys.bugBounty.analystBriefing(programId),
    queryFn: ({ signal }) => bugBountyApi.getAnalystBriefing({ programId, limit: 25, signal })
  });

  const analystSupportQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.analystSupport(programId),
    queryFn: ({ signal }) => bugBountyApi.getPhase7AnalystSupport({ programId, limit: 25, signal })
  });

  const queueQuery = useQuery({
    queryKey: queryKeys.bugBounty.candidates(programId),
    queryFn: ({ signal }) => bugBountyApi.listCandidateQueue({ programId, limit: 200, signal })
  });

  return {
    briefingQuery,
    analystSupportQuery,
    queueQuery
  };
}
