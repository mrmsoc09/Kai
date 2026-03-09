/**
 * Agent Status Panel - Sidebar showing agent details
 */

import React from 'react';
import { COLORS, UI } from '@/theme/branding';
import type { AgentNode } from './hooks/useAgentStatus';

export const AgentStatusPanel: React.FC<{ agents: AgentNode[] }> = ({ agents }) => {
  return (
    <div style={{ width: '300px', backgroundColor: COLORS.surface, borderRadius: UI.borderRadius.large, padding: UI.spacing.lg, border: `1px solid ${COLORS.neutral.gray_200}`, overflowY: 'auto' }}>
      <h3 style={{ margin: 0, marginBottom: UI.spacing.md }}>Active Agents ({agents.length})</h3>
      {agents.length === 0 ? (
        <div style={{ textAlign: 'center', color: COLORS.neutral.gray_500, padding: UI.spacing.lg }}>
          No agents active
        </div>
      ) : (
        agents.map(agent => (
          <div key={agent.id} style={{ marginBottom: UI.spacing.md, padding: UI.spacing.sm, backgroundColor: COLORS.neutral.gray_50, borderRadius: UI.borderRadius.medium, border: `1px solid ${COLORS.neutral.gray_200}` }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.xs, marginBottom: UI.spacing.xs }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: agent.status === 'active' ? COLORS.status.success : COLORS.neutral.gray_400 }} />
              <div style={{ fontWeight: 600, fontSize: UI.fonts.size_sm }}>{agent.name}</div>
            </div>
            <div style={{ fontSize: UI.fonts.size_xs, color: COLORS.neutral.gray_600 }}>
              <div>Objective: {agent.objective}</div>
              <div>Autonomy: Level {agent.autonomy_level}</div>
              {agent.performance && (
                <div>Success Rate: {(agent.performance.success_rate * 100).toFixed(0)}%</div>
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
};
