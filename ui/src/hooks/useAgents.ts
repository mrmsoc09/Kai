import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { Agent } from '@/types'

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: api.getAgents,
    refetchInterval: 5000,
  })
}

export function useAgent(id: string) {
  return useQuery({
    queryKey: ['agents', id],
    queryFn: () => api.getAgent(id),
    enabled: !!id,
  })
}

export function useSendCommand() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ agentId, command, params }: { agentId: string; command: string; params?: Record<string, unknown> }) =>
      api.sendAgentCommand(agentId, command, params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}

export function useStopAgent() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: api.stopAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
    },
  })
}
