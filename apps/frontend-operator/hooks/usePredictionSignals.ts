"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export function usePredictionSignals(programId?: string) {
  const queryClient = useQueryClient();
  const predictionsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.predictions(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Predictions({ programId, limit: 500, signal })
  });
  const signalsQuery = useQuery({
    queryKey: queryKeys.bugBounty.signals(programId),
    queryFn: ({ signal }) => bugBountyApi.listSignals({ programId, limit: 500, signal })
  });
  const deltasQuery = useQuery({
    queryKey: queryKeys.bugBounty.deltas(programId),
    queryFn: ({ signal }) => bugBountyApi.listDeltas({ programId, limit: 500, signal })
  });
  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.recommendations(programId),
    queryFn: ({ signal }) => bugBountyApi.listPhase7Recommendations({ programId, limit: 500, signal })
  });
  const analystSupportQuery = useQuery({
    queryKey: queryKeys.bugBounty.phase7.analystSupport(programId),
    queryFn: ({ signal }) => bugBountyApi.getPhase7AnalystSupport({ programId, limit: 20, signal })
  });
  const runMutation = useMutation({
    mutationFn: () => bugBountyApi.runPhase7({ actor: "operator.console.phase7", program_id: programId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.phase7.predictions(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.phase7.rankings(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.phase7.recommendations(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.phase7.analystSupport(programId) });
    }
  });

  return {
    predictionsQuery,
    signalsQuery,
    deltasQuery,
    recommendationsQuery,
    analystSupportQuery,
    runMutation
  };
}
