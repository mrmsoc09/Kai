/**
 * Deep Agents Visualization - Force-directed agent graph
 */

import React from 'react';
import { COLORS, UI } from '@/theme/branding';
import { AgentForceGraph } from './AgentForceGraph';
import { AgentStatusPanel } from './AgentStatusPanel';
import { useAgentStatus } from './hooks/useAgentStatus';

export const DeepAgentsViz: React.FC = () => {
  const { agents, isConnected } = useAgentStatus();

  return (
    <div style={{ display: 'flex', gap: UI.spacing.lg, height: '100%' }}>
      <div style={{ flex: 1, backgroundColor: COLORS.surface, borderRadius: UI.borderRadius.large, padding: UI.spacing.lg, border: `1px solid ${COLORS.neutral.gray_200}` }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'between', marginBottom: UI.spacing.md }}>
          <h3 style={{ margin: 0 }}>Agent Network</h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.xs, fontSize: UI.fonts.size_sm }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: isConnected ? COLORS.status.success : COLORS.status.error }} />
            <span>{isConnected ? 'Live' : 'Disconnected'}</span>
          </div>
        </div>
        <AgentForceGraph agents={agents} />
      </div>
      <AgentStatusPanel agents={agents} />
    </div>
  );
};

export default DeepAgentsViz;
