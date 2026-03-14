"use client";

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";
import type { CandidateQueueStatus } from "@/lib/types";

export function useCandidateQueue(programId?: string, status?: string) {
  const queryClient = useQueryClient();

  const queueQuery = useQuery({
    queryKey: queryKeys.bugBounty.candidates(programId, status),
    queryFn: ({ signal }) =>
      bugBountyApi.listCandidateQueue({
        programId,
        status,
        limit: 500,
        signal
      })
  });
  const duplicateRiskQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.duplicateRisk(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7DuplicateRisk({ programId, limit: 500, signal })
  });
  const evidenceQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.evidenceCompleteness(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7EvidenceCompleteness({ programId, limit: 500, signal })
  });
  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.recommendations(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Recommendations({ programId, limit: 500, signal })
  });

  const rows = useMemo(() => {
    const duplicateRisk = duplicateRiskQuery.data ?? [];
    const evidence = evidenceQuery.data ?? [];
    const recommendations = recommendationsQuery.data ?? [];

    return (queueQuery.data ?? [])
      .map((item) => {
        const duplicate = duplicateRisk.find((row) => row.analyst_queue_item_id === item.id);
        const evidenceRecord = evidence.find((row) => row.analyst_queue_item_id === item.id);
        const recommendation = recommendations.find((row) => row.analyst_queue_item_id === item.id);
        return {
          ...item,
          duplicate_risk_score: duplicate?.duplicate_risk_score ?? null,
          duplicate_risk_band: duplicate?.risk_band ?? item.duplicate_risk_hint ?? null,
          duplicate_reasoning: duplicate?.reasoning_summary ?? null,
          evidence_completeness_score: evidenceRecord?.evidence_completeness_score ?? null,
          evidence_readiness_state: evidenceRecord?.readiness_state ?? null,
          missing_evidence_fields: evidenceRecord?.missing_fields_json ?? [],
          recommended_workflow: recommendation?.recommended_workflow ?? null,
          recommended_action: recommendation?.recommended_action ?? null,
          ready_for_report:
            item.status === "ready_for_report" ||
            (evidenceRecord?.readiness_state ?? "").toUpperCase() === "READY_FOR_REVIEW"
        };
      })
      .sort((a, b) => {
        const reportabilityDelta = (b.reportability_score ?? -1) - (a.reportability_score ?? -1);
        if (reportabilityDelta !== 0) {
          return reportabilityDelta;
        }
        const confidenceDelta = (b.confidence_score ?? -1) - (a.confidence_score ?? -1);
        if (confidenceDelta !== 0) {
          return confidenceDelta;
        }
        return (a.duplicate_risk_score ?? 1) - (b.duplicate_risk_score ?? 1);
      });
  }, [duplicateRiskQuery.data, evidenceQuery.data, queueQuery.data, recommendationsQuery.data]);

  const updateStatusMutation = useMutation({
    mutationFn: (input: { queueItemId: string; status: CandidateQueueStatus; analystNotes?: string; assignedTo?: string }) =>
      bugBountyApi.updateCandidateQueueItem(input.queueItemId, {
        status: input.status,
        assigned_to: input.assignedTo,
        analyst_notes: input.analystNotes,
        actor: "operator.console.triage"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.candidates(programId) });
    }
  });

  const generateDraftMutation = useMutation({
    mutationFn: (input: { queueItemId: string; notes?: string }) =>
      bugBountyApi.generateCandidateReportDraft(input.queueItemId, {
        actor: "operator.console.report_draft",
        analyst_notes: input.notes
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.candidates(programId) });
    }
  });

  return {
    rows,
    queueQuery,
    duplicateRiskQuery,
    evidenceQuery,
    recommendationsQuery,
    updateStatusMutation,
    generateDraftMutation
  };
}
