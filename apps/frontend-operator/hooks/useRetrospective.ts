"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";

export function useRetrospective(programId?: string, windowDays = 30) {
  const queryClient = useQueryClient();

  const summaryQuery = useQuery({
    queryKey: queryKeys.bugBounty.retrospective.summary(programId, windowDays),
    queryFn: ({ signal }) =>
      bugBountyApi.getRetrospectiveSummary({
        programId,
        windowDays,
        signal
      })
  });

  const workflowsQuery = useQuery({
    queryKey: queryKeys.bugBounty.retrospective.workflows(programId),
    queryFn: ({ signal }) =>
      bugBountyApi.listRetrospectiveWorkflows({
        programId,
        limit: 200,
        signal
      })
  });

  const targetsQuery = useQuery({
    queryKey: queryKeys.bugBounty.retrospective.targets(programId),
    queryFn: ({ signal }) =>
      bugBountyApi.listRetrospectiveTargets({
        programId,
        limit: 200,
        signal
      })
  });

  const recommendationsQuery = useQuery({
    queryKey: queryKeys.bugBounty.retrospective.recommendations(programId),
    queryFn: ({ signal }) =>
      bugBountyApi.listRetrospectiveRecommendations({
        programId,
        limit: 200,
        signal
      })
  });

  const alertsQuery = useQuery({
    queryKey: queryKeys.bugBounty.retrospective.alerts(programId),
    queryFn: ({ signal }) =>
      bugBountyApi.listRetrospectiveAlerts({
        programId,
        limit: 200,
        signal
      })
  });

  const runMutation = useMutation({
    mutationFn: () =>
      bugBountyApi.runRetrospective({
        actor: "operator.console.phase10",
        program_id: programId,
        window_days: windowDays
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.retrospective.summary(programId, windowDays)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.retrospective.workflows(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.retrospective.targets(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.retrospective.recommendations(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.retrospective.alerts(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.phase7.predictions(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.phase7.rankings(programId)
      });
      queryClient.invalidateQueries({
        queryKey: queryKeys.bugBounty.phase7.recommendations(programId)
      });
    }
  });

  return {
    summaryQuery,
    workflowsQuery,
    targetsQuery,
    recommendationsQuery,
    alertsQuery,
    runMutation
  };
}
