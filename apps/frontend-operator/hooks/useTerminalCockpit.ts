"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  attachTmuxSession,
  createTmuxSession,
  detachTmuxSession,
  executeTerminalPrompt,
  getTerminalLogs,
  getTerminalProviders,
  killTmuxSession,
  listTmuxSessions
} from "@/lib/api/terminal";
import { queryKeys } from "@/lib/query-keys";
import type { TerminalExecutionRequest, TmuxCreateSessionRequest } from "@/lib/types";

export function useTerminalCockpit(logLimit = 30) {
  const queryClient = useQueryClient();
  const providersQuery = useQuery({
    queryKey: queryKeys.terminal.providers(),
    queryFn: () => getTerminalProviders()
  });
  const logsQuery = useQuery({
    queryKey: queryKeys.terminal.logs(logLimit),
    queryFn: () => getTerminalLogs(logLimit)
  });
  const sessionsQuery = useQuery({
    queryKey: queryKeys.terminal.sessions(),
    queryFn: () => listTmuxSessions()
  });

  const executeMutation = useMutation({
    mutationFn: (payload: TerminalExecutionRequest) => executeTerminalPrompt(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.terminal.logs(logLimit) });
    }
  });

  const createSessionMutation = useMutation({
    mutationFn: (payload: TmuxCreateSessionRequest) => createTmuxSession(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.terminal.sessions() });
    }
  });

  const attachSessionMutation = useMutation({
    mutationFn: (sessionId: string) => attachTmuxSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.terminal.sessions() });
    }
  });

  const detachSessionMutation = useMutation({
    mutationFn: (sessionId: string) => detachTmuxSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.terminal.sessions() });
    }
  });

  const killSessionMutation = useMutation({
    mutationFn: (sessionId: string) => killTmuxSession(sessionId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.terminal.sessions() });
    }
  });

  return {
    providersQuery,
    logsQuery,
    sessionsQuery,
    executeMutation,
    createSessionMutation,
    attachSessionMutation,
    detachSessionMutation,
    killSessionMutation
  };
}
