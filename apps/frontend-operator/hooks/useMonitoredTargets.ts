"use client";

import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

type MonitoredTargetRow = {
  targetId: string;
  programId: string;
  target: string;
  targetType: string;
  monitoringStatus: string;
  monitoringEnabled: boolean;
  safeModeRequired: boolean;
  priorityTier: number;
  readinessStatus: string;
  targetYieldScore: number | null;
  nextAction: string | null;
  lastRunAt: string | null;
  nextRunAt: string | null;
  recentDeltaCount: number;
};

export function useMonitoredTargets(programId?: string) {
  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal)
  });

  const targetQueries = useQueries({
    queries:
      programId && programId.length > 0
        ? [
            {
              queryKey: queryKeys.bugBounty.targets(programId),
              queryFn: ({ signal }: { signal: AbortSignal }) => bugBountyApi.listMonitoredTargets(programId, signal)
            }
          ]
        : (programsQuery.data ?? []).map((program) => ({
            queryKey: queryKeys.bugBounty.targets(program.id),
            queryFn: ({ signal }: { signal: AbortSignal }) => bugBountyApi.listMonitoredTargets(program.id, signal)
          }))
  });

  const schedulesQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedules(programId),
    queryFn: ({ signal }) => bugBountyApi.listSchedules({ programId, signal })
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.bugBounty.readiness(programId),
    queryFn: ({ signal }) => bugBountyApi.listReadinessRecords({ programId, limit: 500, signal })
  });
  const yieldsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.yields(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7TargetYields({ programId, limit: 500, signal })
  });
  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.recommendations(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Recommendations({ programId, limit: 500, signal })
  });
  const deltasQuery = useQuery({
    queryKey: queryKeys.bugBounty.deltas(programId),
    queryFn: ({ signal }) => bugBountyApi.listDeltas({ programId, limit: 1000, signal })
  });

  const rows = useMemo<MonitoredTargetRow[]>(() => {
    const targets = targetQueries.flatMap((query) => query.data ?? []);
    const schedules = schedulesQuery.data ?? [];
    const readiness = readinessQuery.data ?? [];
    const yields = yieldsQuery.data ?? [];
    const recommendations = recommendationsQuery.data ?? [];
    const deltas = deltasQuery.data ?? [];

    return targets.map((target) => {
      const schedule = schedules.find((item) => item.scope_target_id === target.id);
      const targetReadiness = readiness.find((item) => {
        const scheduleHint = item.details.schedule_id;
        if (schedule && typeof scheduleHint === "string" && scheduleHint === schedule.id) {
          return true;
        }
        const targetHint = item.details.target;
        return typeof targetHint === "string" && targetHint === target.target;
      });
      const targetYield = yields.find((item) => item.scope_target_id === target.id);
      const recommendation = recommendations.find((item) => item.scope_target_id === target.id);
      const targetDeltas = deltas.filter((item) => item.scope_target_id === target.id).length;
      return {
        targetId: target.id,
        programId: target.program_id,
        target: target.target,
        targetType: target.target_type,
        monitoringStatus: target.monitoring_status,
        monitoringEnabled: target.monitoring_enabled,
        safeModeRequired: target.safe_mode_required,
        priorityTier: target.monitoring_priority_tier,
        readinessStatus: targetReadiness?.decision_status ?? "UNKNOWN",
        targetYieldScore: targetYield?.yield_score ?? null,
        nextAction: recommendation?.recommended_action ?? null,
        lastRunAt: schedule?.last_run_finished_at ?? target.last_success_at ?? target.last_failure_at,
        nextRunAt: schedule?.next_scheduled_run_at ?? target.next_scheduled_run_at,
        recentDeltaCount: targetDeltas
      };
    });
  }, [deltasQuery.data, readinessQuery.data, recommendationsQuery.data, schedulesQuery.data, targetQueries, yieldsQuery.data]);

  const isLoading =
    programsQuery.isLoading ||
    schedulesQuery.isLoading ||
    readinessQuery.isLoading ||
    yieldsQuery.isLoading ||
    recommendationsQuery.isLoading ||
    deltasQuery.isLoading ||
    targetQueries.some((query) => query.isLoading);

  const errors = [
    programsQuery.error,
    schedulesQuery.error,
    readinessQuery.error,
    yieldsQuery.error,
    recommendationsQuery.error,
    deltasQuery.error,
    ...targetQueries.map((query) => query.error)
  ].filter(Boolean);

  return {
    rows,
    isLoading,
    errors,
    programs: programsQuery.data ?? []
  };
}
