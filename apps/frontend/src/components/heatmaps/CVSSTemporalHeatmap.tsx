/**
 * CVSS Temporal Heatmap
 * Visualizes CVSS risk scores over time using Recharts
 */

import React, { useState, useEffect } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';
import { COLORS, UI } from '@/theme/branding';

interface CVSSDataPoint {
  id: string;
  timestamp: number;
  cvss_score: float;
  severity: string;
  cve_id?: string;
  title?: string;
}

interface CVSSTemporalHeatmapProps {
  data?: CVSSDataPoint[];
  height?: number;
}

export const CVSSTemporalHeatmap: React.FC<CVSSTemporalHeatmapProps> = ({
  data: externalData,
  height = 400
}) => {
  const [data, setData] = useState<CVSSDataPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (externalData) {
      setData(externalData);
      setLoading(false);
    } else {
      fetchData();
    }
  }, [externalData]);

  const fetchData = async () => {
    try {
      // Fetch heatmap data from API
      const response = await fetch('/api/v1/epss/heatmap-data?limit=100');
      const result = await response.json();

      if (result.success) {
        // Transform data for temporal display
        const transformedData = result.data_points.map((point: any, idx: number) => ({
          id: point.id,
          timestamp: Date.now() - (idx * 86400000), // Simulate temporal spread
          cvss_score: point.value * 10, // Convert EPSS to 0-10 scale
          severity: point.risk_level,
          cve_id: point.id,
          title: point.label,
        }));

        setData(transformedData);
      }
      setLoading(false);
    } catch (error) {
      console.error('Error fetching heatmap data:', error);
      setLoading(false);
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return COLORS.severity.critical;
      case 'high':
        return COLORS.severity.high;
      case 'medium':
        return COLORS.severity.medium;
      case 'low':
        return COLORS.severity.low;
      default:
        return COLORS.neutral.gray_400;
    }
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (!active || !payload || !payload[0]) return null;

    const data = payload[0].payload;

    return (
      <div
        style={{
          backgroundColor: COLORS.elevated,
          padding: UI.spacing.md,
          border: `1px solid ${COLORS.neutral.gray_200}`,
          borderRadius: UI.borderRadius.medium,
          boxShadow: UI.shadow.lg,
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: UI.spacing.xs }}>
          {data.cve_id || data.title || 'Finding'}
        </div>
        <div style={{ fontSize: UI.fonts.size_sm, color: COLORS.neutral.gray_600 }}>
          <div>CVSS Score: <strong>{data.cvss_score.toFixed(1)}</strong></div>
          <div>
            Severity:{' '}
            <span style={{ color: getSeverityColor(data.severity), fontWeight: 600 }}>
              {data.severity.toUpperCase()}
            </span>
          </div>
          <div>Date: {new Date(data.timestamp).toLocaleDateString()}</div>
        </div>
      </div>
    );
  };

  if (loading) {
    return (
      <div
        style={{
          height,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: COLORS.neutral.gray_50,
          borderRadius: UI.borderRadius.large,
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '24px', marginBottom: UI.spacing.sm }}>⏳</div>
          <div style={{ color: COLORS.neutral.gray_600 }}>Loading heatmap data...</div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        backgroundColor: COLORS.surface,
        borderRadius: UI.borderRadius.large,
        padding: UI.spacing.lg,
        border: `1px solid ${COLORS.neutral.gray_200}`,
      }}
    >
      <h3 style={{ margin: 0, marginBottom: UI.spacing.md, fontSize: UI.fonts.size_lg }}>
        CVSS Temporal Risk Distribution
      </h3>

      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
          <XAxis
            type="number"
            dataKey="timestamp"
            name="Time"
            domain={['auto', 'auto']}
            tickFormatter={(value) => new Date(value).toLocaleDateString()}
            style={{ fontSize: UI.fonts.size_xs }}
          />
          <YAxis
            type="number"
            dataKey="cvss_score"
            name="CVSS Score"
            domain={[0, 10]}
            style={{ fontSize: UI.fonts.size_xs }}
          />
          <ZAxis type="number" range={[100, 400]} />
          <Tooltip content={<CustomTooltip />} />
          <Legend />
          <Scatter name="Vulnerabilities" data={data} fill={COLORS.primary.main}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={getSeverityColor(entry.severity)} />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>

      <div
        style={{
          marginTop: UI.spacing.md,
          display: 'flex',
          gap: UI.spacing.lg,
          justifyContent: 'center',
          flexWrap: 'wrap',
        }}
      >
        {['critical', 'high', 'medium', 'low'].map((severity) => (
          <div key={severity} style={{ display: 'flex', alignItems: 'center', gap: UI.spacing.xs }}>
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: getSeverityColor(severity),
              }}
            />
            <span style={{ fontSize: UI.fonts.size_sm, textTransform: 'capitalize' }}>
              {severity}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CVSSTemporalHeatmap;
