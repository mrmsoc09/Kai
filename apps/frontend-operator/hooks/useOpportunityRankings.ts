"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export type OpportunityRankingRow = {
  id: string;
  programId: string;
  scopeTargetId: string | null;
  subjectType: string;
  subjectKey: string;
  selectionScore: number;
  priorityRank: number | null;
  confidenceScore: number | null;
  duplicateRiskScore: number | null;
  evidenceCompletenessScore: number | null;
  recommendedWorkflow: string | null;
  recommendedAction: string | null;
  reasoningSummary: string;
};

export function useOpportunityRankings(programId?: string) {
  const rankingsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.rankings(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7OpportunityRankings({ programId, limit: 500, signal })
  });
  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.recommendations(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Recommendations({ programId, limit: 500, signal })
  });
  const predictionsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.predictions(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Predictions({ programId, limit: 500, signal })
  });
  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal)
  });

  const rows = useMemo<OpportunityRankingRow[]>(() => {
    const recommendations = recommendationsQuery.data ?? [];
    const predictions = predictionsQuery.data ?? [];
    const rankedRows = (rankingsQuery.data ?? [])
      .map((ranking) => {
        const linkedRecommendation =
          recommendations.find((item) => item.selection_record_id === ranking.id) ??
          recommendations.find((item) => item.scope_target_id && item.scope_target_id === ranking.scope_target_id) ??
          null;
        const linkedPrediction =
          predictions.find((item) => item.scope_target_id && item.scope_target_id === ranking.scope_target_id) ??
          predictions.find(
            (item) => item.analyst_queue_item_id && item.analyst_queue_item_id === ranking.analyst_queue_item_id
          ) ??
          null;

        return {
          id: ranking.id,
          programId: ranking.program_id,
          scopeTargetId: ranking.scope_target_id,
          subjectType: ranking.subject_type,
          subjectKey: ranking.subject_key,
          selectionScore: ranking.selection_score,
          priorityRank: ranking.priority_rank,
          confidenceScore: ranking.confidence_score ?? linkedPrediction?.confidence_score ?? null,
          duplicateRiskScore: ranking.duplicate_risk_score ?? linkedPrediction?.duplicate_risk_score ?? null,
          evidenceCompletenessScore:
            ranking.evidence_completeness_score ?? linkedPrediction?.evidence_completeness_score ?? null,
          recommendedWorkflow:
            linkedRecommendation?.recommended_workflow ?? linkedPrediction?.recommended_next_workflow ?? null,
          recommendedAction:
            linkedRecommendation?.recommended_action ?? linkedPrediction?.recommended_follow_up_action ?? null,
          reasoningSummary: ranking.reasoning_summary
        };
      })
      .sort((a, b) => {
        if (a.priorityRank !== null && b.priorityRank !== null && a.priorityRank !== b.priorityRank) {
          return a.priorityRank - b.priorityRank;
        }
        if (a.priorityRank === null && b.priorityRank !== null) {
          return 1;
        }
        if (a.priorityRank !== null && b.priorityRank === null) {
          return -1;
        }
        return b.selectionScore - a.selectionScore;
      });
    if (rankedRows.length > 0) {
      return rankedRows;
    }

    return (programsQuery.data ?? [])
      .filter((program) => {
        if (!programId) {
          return true;
        }
        return program.id === programId || program.program_key === programId;
      })
      .map((program) => {
        const platform = (program.platform ?? "unknown").toUpperCase();
        const handle = program.handle ?? program.program_key ?? program.id;
        return {
          id: `program-${program.id}`,
          programId: program.id,
          scopeTargetId: null,
          subjectType: "PROGRAM",
          subjectKey: handle,
          selectionScore: 0,
          priorityRank: null,
          confidenceScore: null,
          duplicateRiskScore: null,
          evidenceCompletenessScore: null,
          recommendedWorkflow: "phase7_prediction",
          recommendedAction: "run_prediction_cycle",
          reasoningSummary: `Program available (${platform}). Phase 7 ranking not generated yet.`
        };
      });
  }, [predictionsQuery.data, rankingsQuery.data, recommendationsQuery.data, programsQuery.data, programId]);

  return {
    rows,
    rankingsQuery,
    recommendationsQuery,
    predictionsQuery,
    programsQuery
  };
}
