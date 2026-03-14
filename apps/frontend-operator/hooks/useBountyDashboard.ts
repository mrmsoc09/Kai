"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { getHealth, getReadiness } from "@/lib/api/diagnostics";
import { queryKeys } from "@/lib/query-keys";

export function useBountyDashboard(programId?: string) {
  const programsQuery = useQuery({
    queryKey: queryKeys.bugBounty.programs(),
    queryFn: ({ signal }) => bugBountyApi.listBountyPrograms(signal)
  });
  const schedulesQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedules(programId),
    queryFn: ({ signal }) => bugBountyApi.listSchedules({ programId, signal })
  });
  const schedulerStatusQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedulerStatus(programId),
    queryFn: ({ signal }) => bugBountyApi.getSchedulerStatus({ programId, signal })
  });
  const candidatesQuery = useQuery({
    queryKey: queryKeys.bugBounty.candidates(programId),
    queryFn: ({ signal }) => bugBountyApi.listCandidateQueue({ programId, limit: 200, signal })
  });
  const deltasQuery = useQuery({
    queryKey: queryKeys.bugBounty.deltas(programId),
    queryFn: ({ signal }) => bugBountyApi.listDeltas({ programId, limit: 200, signal })
  });
  const readinessRecordsQuery = useQuery({
    queryKey: queryKeys.bugBounty.readiness(programId),
    queryFn: ({ signal }) => bugBountyApi.listReadinessRecords({ programId, limit: 200, signal })
  });
  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.recommendations(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Recommendations({ programId, limit: 200, signal })
  });
  const toolsHealthQuery = useQuery({
    queryKey: queryKeys.bugBounty.toolsHealth(),
    queryFn: ({ signal }) => bugBountyApi.getToolsHealth({ signal })
  });
  const alertSummaryQuery = useQuery({
    queryKey: queryKeys.bugBounty.alertsSummary(programId),
    queryFn: ({ signal }) => bugBountyApi.getAlertCaseSummary({ programId, signal })
  });
  const healthQuery = useQuery({
    queryKey: queryKeys.diagnostics.health(),
    queryFn: ({ signal }) => getHealth(signal)
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.diagnostics.ready(),
    queryFn: ({ signal }) => getReadiness(signal)
  });

  const metrics = useMemo(() => {
    const programs = programsQuery.data ?? [];
    const schedules = schedulesQuery.data ?? [];
    const candidates = candidatesQuery.data ?? [];
    const deltas = deltasQuery.data ?? [];
    const readinessRecords = readinessRecordsQuery.data ?? [];
    const recommendations = recommendationsQuery.data ?? [];
    const blockedReadiness = readinessRecords.filter((row) => row.decision_status !== "READY").length;
    const readyForReport = candidates.filter((row) => row.status === "ready_for_report").length;
    const pendingValidation = candidates.filter((row) => row.status === "needs_manual_validation").length;
    const blockedRecommendations = recommendations.filter(
      (row) => row.recommendation_status.toUpperCase() === "DEFERRED"
    ).length;
    const activeSchedules = schedules.filter((row) => row.status === "ACTIVE").length;
    const toolSummary = toolsHealthQuery.data?.summary;
    const alertSummary = alertSummaryQuery.data;

    return {
      programs: programs.length,
      activeSchedules,
      candidates: candidates.length,
      readyForReport,
      pendingValidation,
      recentDeltas: deltas.length,
      blockedReadiness,
      blockedRecommendations,
      healthyTools: toolSummary?.healthy_tools ?? 0,
      totalTools: toolSummary?.total_tools ?? 0,
      unresolvedAlerts: alertSummary?.unresolved_alert_count ?? 0,
      highSeverityAlerts: alertSummary?.high_severity_alert_count ?? 0,
      openCases: alertSummary?.open_case_count ?? 0,
      readyForReportCases: alertSummary?.ready_for_report_case_count ?? 0,
      staleUnownedCases: alertSummary?.stale_unowned_case_count ?? 0
    };
  }, [
    candidatesQuery.data,
    deltasQuery.data,
    programsQuery.data,
    readinessRecordsQuery.data,
    recommendationsQuery.data,
    schedulesQuery.data,
    alertSummaryQuery.data,
    toolsHealthQuery.data?.summary
  ]);

  return {
    programsQuery,
    schedulesQuery,
    schedulerStatusQuery,
    candidatesQuery,
    deltasQuery,
    readinessRecordsQuery,
    recommendationsQuery,
    toolsHealthQuery,
    alertSummaryQuery,
    healthQuery,
    readinessQuery,
    metrics
  };
}
