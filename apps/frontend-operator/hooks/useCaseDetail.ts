"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";
import type { CasePriority, CaseStatus } from "@/lib/types";

export function useCaseDetail(caseId: string) {
  const queryClient = useQueryClient();
  const caseQuery = useQuery({
    queryKey: queryKeys.bugBounty.caseDetail(caseId),
    queryFn: ({ signal }) => bugBountyApi.getCase(caseId, signal),
    enabled: Boolean(caseId)
  });

  const updateCaseMutation = useMutation({
    mutationFn: (input: {
      status?: CaseStatus;
      priority?: CasePriority;
      summary?: string;
      reasoningSummary?: string;
      closureReason?: string;
    }) =>
      bugBountyApi.updateCase(caseId, {
        actor: "operator.console.cases",
        status: input.status,
        priority: input.priority,
        summary: input.summary,
        reasoning_summary: input.reasoningSummary,
        closure_reason: input.closureReason
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.caseDetail(caseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.cases() });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary() });
    }
  });

  const assignMutation = useMutation({
    mutationFn: (owner: string) =>
      bugBountyApi.assignCase(caseId, {
        owner,
        actor: "operator.console.cases"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.caseDetail(caseId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.cases() });
    }
  });

  const addNoteMutation = useMutation({
    mutationFn: (note: string) =>
      bugBountyApi.addCaseNote(caseId, {
        note,
        actor: "operator.console.cases"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.caseDetail(caseId) });
    }
  });

  return {
    caseQuery,
    updateCaseMutation,
    assignMutation,
    addNoteMutation
  };
}
