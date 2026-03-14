"use client";

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export function useAlertCenter(programId?: string, status?: string, severity?: string) {
  const queryClient = useQueryClient();
  const alertsQuery = useQuery({
    queryKey: queryKeys.bugBounty.alerts(programId, status, severity),
    queryFn: ({ signal }) =>
      bugBountyApi.listAlerts({
        programId,
        status,
        severity,
        limit: 500,
        signal
      })
  });
  const summaryQuery = useQuery({
    queryKey: queryKeys.bugBounty.alertsSummary(programId),
    queryFn: ({ signal }) => bugBountyApi.getAlertCaseSummary({ programId, signal })
  });

  const syncMutation = useMutation({
    mutationFn: () =>
      bugBountyApi.syncAlerts({
        actor: "operator.console.alerts",
        program_id: programId
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alerts(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary(programId) });
    }
  });
  const acknowledgeMutation = useMutation({
    mutationFn: (input: { alertId: string; note?: string }) =>
      bugBountyApi.acknowledgeAlert(input.alertId, {
        actor: "operator.console.alerts",
        note: input.note
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alerts(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary(programId) });
    }
  });
  const resolveMutation = useMutation({
    mutationFn: (input: { alertId: string; note?: string }) =>
      bugBountyApi.resolveAlert(input.alertId, {
        actor: "operator.console.alerts",
        note: input.note
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alerts(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary(programId) });
    }
  });
  const createCaseMutation = useMutation({
    mutationFn: (input: { alertId: string; owner?: string }) =>
      bugBountyApi.createCaseFromAlert(input.alertId, {
        actor: "operator.console.cases",
        owner: input.owner
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alerts(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.cases(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.alertsSummary(programId) });
    }
  });

  const rows = useMemo(
    () =>
      (alertsQuery.data ?? []).slice().sort((a, b) => {
        const severityRank = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1 };
        const left = severityRank[a.severity] ?? 0;
        const right = severityRank[b.severity] ?? 0;
        if (left !== right) {
          return right - left;
        }
        return new Date(b.last_seen_at).getTime() - new Date(a.last_seen_at).getTime();
      }),
    [alertsQuery.data]
  );

  return {
    rows,
    alertsQuery,
    summaryQuery,
    syncMutation,
    acknowledgeMutation,
    resolveMutation,
    createCaseMutation
  };
}
