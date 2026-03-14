"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

type ProgramRow = {
  programId: string;
  name: string;
  platform: string | null;
  status: string;
  monitoredTargets: number;
  activeSchedules: number;
  candidateFindings: number;
  yieldScore: number | null;
  opportunityScore: number | null;
};

export function useBountyPrograms() {
  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal)
  });
  const schedulesQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedules(),
    queryFn: ({ signal }) => bugBountyApi.listSchedules({ signal })
  });
  const candidatesQuery = useQuery({
    queryKey: queryKeys.bugBounty.candidates(),
    queryFn: ({ signal }) => bugBountyApi.listCandidateQueue({ limit: 500, signal })
  });
  const yieldsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.yields(),
    queryFn: ({ signal }) => bugBountyApi.listPhase7TargetYields({ limit: 500, signal })
  });
  const rankingsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.rankings(undefined, "PROGRAM"),
    queryFn: ({ signal }) =>
      bugBountyApi.listPhase7OpportunityRankings({
        subjectType: "PROGRAM",
        limit: 500,
        signal
      })
  });

  const targetQueries = useQueries({
    queries: (programsQuery.data ?? []).map((program) => ({
      queryKey: queryKeys.bugBounty.targets(program.id),
      queryFn: ({ signal }: { signal: AbortSignal }) => bugBountyApi.listMonitoredTargets(program.id, signal)
    }))
  });

  const rows = useMemo<ProgramRow[]>(() => {
    const schedules = schedulesQuery.data ?? [];
    const candidates = candidatesQuery.data ?? [];
    const yields = yieldsQuery.data ?? [];
    const rankings = rankingsQuery.data ?? [];
    const targetMap = new Map<string, number>();

    for (const query of targetQueries) {
      const entries = query.data ?? [];
      if (entries.length === 0) {
        continue;
      }
      const programId = entries[0]?.program_id;
      if (programId) {
        targetMap.set(programId, entries.length);
      }
    }

    return (programsQuery.data ?? [])
      .map((program) => {
        const programId = program.id;
        const activeSchedules = schedules.filter(
          (schedule) => schedule.program_id === programId && schedule.status === "ACTIVE"
        ).length;
        const candidateFindings = candidates.filter((item) => item.program_id === programId).length;
        const mostRecentYield = yields.find((item) => item.program_id === programId);
        const ranking = rankings.find((item) => item.program_id === programId);
        return {
          programId,
          name: program.name,
          platform: program.platform,
          status: program.status,
          monitoredTargets: targetMap.get(programId) ?? 0,
          activeSchedules,
          candidateFindings,
          yieldScore: mostRecentYield?.yield_score ?? null,
          opportunityScore: ranking?.selection_score ?? null
        };
      })
      .sort((a, b) => {
        const opportunityDelta = (b.opportunityScore ?? -1) - (a.opportunityScore ?? -1);
        if (opportunityDelta !== 0) {
          return opportunityDelta;
        }
        return b.candidateFindings - a.candidateFindings;
      });
  }, [
    candidatesQuery.data,
    programsQuery.data,
    rankingsQuery.data,
    schedulesQuery.data,
    targetQueries,
    yieldsQuery.data
  ]);

  const isLoading =
    programsQuery.isLoading ||
    schedulesQuery.isLoading ||
    candidatesQuery.isLoading ||
    yieldsQuery.isLoading ||
    rankingsQuery.isLoading ||
    targetQueries.some((query) => query.isLoading);

  const errors = [
    programsQuery.error,
    schedulesQuery.error,
    candidatesQuery.error,
    yieldsQuery.error,
    rankingsQuery.error,
    ...targetQueries.map((query) => query.error)
  ].filter(Boolean);

  return {
    rows,
    isLoading,
    errors,
    programsQuery,
    schedulesQuery,
    candidatesQuery,
    yieldsQuery,
    rankingsQuery
  };
}
