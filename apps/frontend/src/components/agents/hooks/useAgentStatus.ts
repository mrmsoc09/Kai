/**
 * Hook for real-time agent status updates via WebSocket
 */

import { useState, useEffect, useCallback } from 'react';

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

export function useAgentStatus(apiUrl: string = `ws://${window.location.hostname}:8000/api/v1/agent-zero/ws/agents`) {
  const [agents, setAgents] = useState<AgentNode[]>([]);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(apiUrl);

    ws.onopen = () => {
      setIsConnected(true);
      ws.send('ping');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'agent_update' && data.status?.agents) {
          setAgents(data.status.agents);
        }
      } catch (error) {
        console.error('Error parsing agent update:', error);
      }
    };

    ws.onclose = () => setIsConnected(false);

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

  return { agents, isConnected };
}
