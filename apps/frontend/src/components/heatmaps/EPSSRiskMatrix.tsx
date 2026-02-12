/**
 * EPSS Risk Matrix - Exploit Probability Heat Map
 */

import React, { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { COLORS, UI } from '@/theme/branding';

export const EPSSRiskMatrix: React.FC<{ height?: number }> = ({ height = 400 }) => {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    fetch('/api/v1/epss/heatmap-data?limit=50')
      .then(res => res.json())
      .then(result => {
        if (result.success) {
          setData(result.data_points);
        }
      });
  }, []);

  const getRiskColor = (riskLevel: string) => {
    const colors = { critical: COLORS.severity.critical, high: COLORS.severity.high, medium: COLORS.severity.medium, low: COLORS.severity.low };
    return colors[riskLevel as keyof typeof colors] || COLORS.neutral.gray_400;
  };

  return (
    <div style={{ backgroundColor: COLORS.neutral.white, borderRadius: UI.borderRadius.large, padding: UI.spacing.lg, border: `1px solid ${COLORS.neutral.gray_200}` }}>
      <h3 style={{ margin: 0, marginBottom: UI.spacing.md }}>EPSS Exploit Probability Matrix</h3>
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <XAxis type="number" dataKey="x" name="EPSS Score" domain={[0, 1]} label={{ value: 'Exploitation Probability', position: 'insideBottom', offset: -10 }} />
          <YAxis type="number" dataKey="y" name="Percentile" domain={[0, 1]} label={{ value: 'Percentile Rank', angle: -90, position: 'insideLeft' }} />
          <Tooltip content={({ active, payload }: any) => {
            if (!active || !payload?.[0]) return null;
            const d = payload[0].payload;
            return (
              <div style={{ backgroundColor: COLORS.neutral.white, padding: UI.spacing.sm, border: `1px solid ${COLORS.neutral.gray_200}`, borderRadius: UI.borderRadius.small, boxShadow: UI.shadow.md }}>
                <div style={{ fontWeight: 600 }}>{d.label}</div>
                <div style={{ fontSize: UI.fonts.size_sm }}>EPSS: {(d.x * 100).toFixed(1)}%</div>
                <div style={{ fontSize: UI.fonts.size_sm }}>Percentile: {(d.y * 100).toFixed(1)}%</div>
                <div style={{ fontSize: UI.fonts.size_sm, color: getRiskColor(d.risk_level), fontWeight: 600 }}>{d.risk_level.toUpperCase()}</div>
              </div>
            );
          }} />
          <Scatter name="CVEs" data={data}>
            {data.map((entry, idx) => <Cell key={idx} fill={getRiskColor(entry.risk_level)} />)}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
};

export default EPSSRiskMatrix;
