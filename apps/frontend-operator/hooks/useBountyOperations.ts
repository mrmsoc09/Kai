"use client";

import { useQuery } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { getHealth, getReadiness } from "@/lib/api/diagnostics";
import { queryKeys } from "@/lib/query-keys";

export function useBountyOperations(programId?: string) {
  const schedulerStatusQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedulerStatus(programId),
    queryFn: ({ signal }) => bugBountyApi.getSchedulerStatus({ programId, signal })
  });
  const schedulesQuery = useQuery({
    queryKey: queryKeys.bugBounty.schedules(programId),
    queryFn: ({ signal }) => bugBountyApi.listSchedules({ programId, signal })
  });
  const readinessRecordsQuery = useQuery({
    queryKey: queryKeys.bugBounty.readiness(programId),
    queryFn: ({ signal }) => bugBountyApi.listReadinessRecords({ programId, limit: 500, signal })
  });
  const adaptiveActionsQuery = useQuery({
    queryKey: queryKeys.bugBounty.adaptiveActions(programId),
    queryFn: ({ signal }) => bugBountyApi.listAdaptiveActions({ programId, limit: 200, signal })
  });
  const toolsHealthQuery = useQuery({
    queryKey: queryKeys.bugBounty.toolsHealth(),
    queryFn: ({ signal }) => bugBountyApi.getToolsHealth({ signal })
  });
  const healthQuery = useQuery({
    queryKey: queryKeys.diagnostics.health(),
    queryFn: ({ signal }) => getHealth(signal)
  });
  const readinessQuery = useQuery({
    queryKey: queryKeys.diagnostics.ready(),
    queryFn: ({ signal }) => getReadiness(signal)
  });

  return {
    schedulerStatusQuery,
    schedulesQuery,
    readinessRecordsQuery,
    adaptiveActionsQuery,
    toolsHealthQuery,
    healthQuery,
    readinessQuery
  };
}
