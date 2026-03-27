/**
 * Hook for real-time agent and quota status updates via WebSocket.
 *
 * Connects to GeminiOrchestrator /api/v1/orchestration/ws/agents.
 * Each message includes agent nodes AND QuotaStatus for the dashboard
 * quota indicator.
 */

import { useState, useEffect } from 'react';

export interface AgentNode {
  id: string;
  name: string;
  objective: string;
  status: string;
  autonomy_level: number;
  performance?: {
    success_rate: number;
    success_count: number;
    failure_count: number;
  };
}

export interface TierQuota {
  rpm_remaining: number;
  rpd_remaining: number;
  rpm_limit: number;
  rpd_limit: number;
}

export interface QuotaStatus {
  flash: TierQuota;
  flash_lite: TierQuota;
  pro: TierQuota;
  active_tier: string;
  emergency_fallback_active: boolean;
  flash_lite_spillover_active: boolean;
  pro_restricted: boolean;
  last_reset_time: string;
}

export interface AgentStatusState {
  agents: AgentNode[];
  isConnected: boolean;
  activeModel: string | null;
  activeTier: string | null;
  quotaStatus: QuotaStatus | null;
  sessionState: 'idle' | 'connecting' | 'connected' | 'error';
}

export function useAgentStatus(
  apiUrl: string = `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/orchestration/ws/agents`,
): AgentStatusState {
  const [state, setState] = useState<AgentStatusState>({
    agents: [],
    isConnected: false,
    activeModel: null,
    activeTier: null,
    quotaStatus: null,
    sessionState: 'idle',
  });

  useEffect(() => {
    setState((s) => ({ ...s, sessionState: 'connecting' }));
    const ws = new WebSocket(apiUrl);

    ws.onopen = () => {
      setState((s) => ({ ...s, isConnected: true, sessionState: 'connected' }));
      ws.send('ping');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'pong') return;

        if (data.type === 'agent_update' && data.status) {
          const status = data.status;
          setState((s) => ({
            ...s,
            agents: status.agents ?? s.agents,
            activeModel: status.providers_registered?.[0] ?? s.activeModel,
            activeTier: status.active_tier ?? s.activeTier,
            quotaStatus: status.quota ?? s.quotaStatus,
          }));
        }
      } catch (error) {
        console.error('[useAgentStatus] parse error:', error);
      }
    };

    ws.onclose = () => {
      setState((s) => ({ ...s, isConnected: false, sessionState: 'idle' }));
    };

    ws.onerror = () => {
      setState((s) => ({ ...s, sessionState: 'error' }));
    };

    const interval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send('ping');
      }
    }, 5000);

    return () => {
      clearInterval(interval);
      ws.close();
    };
  }, [apiUrl]);

  return state;
}
