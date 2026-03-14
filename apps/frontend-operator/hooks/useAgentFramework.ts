"use client";

import { useMemo } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export function useAgentFramework(programId?: string) {
  const queryClient = useQueryClient();

  const agentsQuery = useQuery({
    queryKey: queryKeys.bugBounty.agents.registry(true),
    queryFn: ({ signal }) =>
      bugBountyApi.listAgents({
        enabledOnly: true,
        limit: 500,
        signal
      })
  });

  const executionsQuery = useQuery({
    queryKey: queryKeys.bugBounty.agents.executions(programId),
    queryFn: ({ signal }) =>
      bugBountyApi.listAgentExecutions({
        programId,
        limit: 500,
        signal
      })
  });

  const evaluationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.agents.evaluations(),
    queryFn: ({ signal }) =>
      bugBountyApi.listAgentEvaluations({
        limit: 500,
        signal
      })
  });

  const syncMutation = useMutation({
    mutationFn: () => bugBountyApi.syncAgentRegistry(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.agents.registry(true) });
    }
  });

  const runMutation = useMutation({
    mutationFn: ({
      agentId,
      inputPayload
    }: {
      agentId: string;
      inputPayload: Record<string, unknown>;
    }) =>
      bugBountyApi.runAgent(agentId, {
        actor: "operator.console.phase10_5",
        input_payload: inputPayload,
        program_id: programId
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.agents.executions(programId)
      });
    }
  });

  const evaluateMutation = useMutation({
    mutationFn: ({ agentId }: { agentId: string }) =>
      bugBountyApi.evaluateAgent(agentId, {
        actor: "operator.console.phase10_5",
        benchmark_name: "default"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.agents.evaluations() });
    }
  });

  const summary = useMemo(() => {
    const agents = agentsQuery.data ?? [];
    const executions = executionsQuery.data ?? [];
    const evaluations = evaluationsQuery.data ?? [];
    const succeeded = executions.filter((item) => item.execution_status === "SUCCEEDED").length;
    const escalated = executions.filter((item) => item.execution_status === "ESCALATED").length;
    const failed = executions.filter((item) => item.execution_status === "FAILED").length;
    const passingEvaluations = evaluations.filter((item) => item.status === "PASSED").length;
    return {
      agents: agents.length,
      executions: executions.length,
      succeeded,
      escalated,
      failed,
      passingEvaluations,
      averageSuccessRate:
        evaluations.length > 0
          ? evaluations.reduce((sum, item) => sum + Number(item.success_rate || 0), 0) / evaluations.length
          : 0
    };
  }, [agentsQuery.data, evaluationsQuery.data, executionsQuery.data]);

  return {
    agentsQuery,
    executionsQuery,
    evaluationsQuery,
    syncMutation,
    runMutation,
    evaluateMutation,
    summary
  };
}
