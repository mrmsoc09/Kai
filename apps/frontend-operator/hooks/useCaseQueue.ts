"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";
import type { CasePriority, CaseStatus } from "@/lib/types";

export function useCaseQueue(
  programId?: string,
  status?: string,
  priority?: string,
  owner?: string
) {
  const queryClient = useQueryClient();
  const casesQuery = useQuery({
    queryKey: queryKeys.bugBounty.cases(programId, status, priority, owner),
    queryFn: ({ signal }) =>
      bugBountyApi.listCases({
        programId,
        status,
        priority,
        owner,
        limit: 500,
        signal
      })
  });

  const updateCaseMutation = useMutation({
    mutationFn: (input: {
      caseId: string;
      status?: CaseStatus;
      priority?: CasePriority;
      summary?: string;
      reasoningSummary?: string;
      closureReason?: string;
    }) =>
      bugBountyApi.updateCase(input.caseId, {
        actor: "operator.console.cases",
        status: input.status,
        priority: input.priority,
        summary: input.summary,
        reasoning_summary: input.reasoningSummary,
        closure_reason: input.closureReason
      }),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.cases(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.caseDetail(variables.caseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary(programId) });
    }
  });

  const assignCaseMutation = useMutation({
    mutationFn: (input: { caseId: string; owner: string }) =>
      bugBountyApi.assignCase(input.caseId, {
        owner: input.owner,
        actor: "operator.console.cases"
      }),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.cases(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.caseDetail(variables.caseId) });
    }
  });

  return {
    casesQuery,
    updateCaseMutation,
    assignCaseMutation
  };
}
