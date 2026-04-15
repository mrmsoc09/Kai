/**
 * System Health Indicator Component
 *
 * Displays real-time system health status including active scans,
 * system resources, and operational status.
 */
'use client';

import React, { useState, useEffect } from 'react';

interface SystemHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  active_scans: number;
  cpu_usage: number;
  memory_usage: number;
  websocket_connections: number;
  uptime_seconds: number;
  timestamp: string;
}

interface SystemHealthIndicatorProps {
  autoRefresh?: boolean;
}

const formatUptime = (seconds: number): string => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
};

export const SystemHealthIndicator: React.FC<SystemHealthIndicatorProps> = ({ autoRefresh = true }) => {
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const response = await fetch('/api/v1/system/health');
        if (response.ok) {
          const data = await response.json();
          setHealth(data);
        }
      } catch (error) {
        console.error('Failed to fetch system health:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchHealth();

    if (!autoRefresh) return;

    const interval = setInterval(fetchHealth, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [autoRefresh]);

  if (!health) {
    return (
      <div className="system-health-indicator loading">
        <span>Loading health status...</span>
      </div>
    );
  }

  const getStatusColor = (status: SystemHealth['status']): string => {
    switch (status) {
      case 'healthy':
        return '#22c55e';
      case 'degraded':
        return '#f97316';
      case 'unhealthy':
        return '#ef4444';
      default:
        return '#6b7280';
    }
  };

  return (
    <div className="system-health-indicator" onClick={() => setExpanded(!expanded)}>
      <div className="health-display">
        <span
          className={`health-dot ${health.status}`}
          style={{ backgroundColor: getStatusColor(health.status) }}
          title={`System Health: ${health.status.toUpperCase()}`}
        />
        <span className="health-text">
          {health.status.charAt(0).toUpperCase() + health.status.slice(1)}
        </span>
      </div>

      {expanded && (
        <div className="health-details">
          <h4>System Health</h4>
          <div className="health-metrics">
            <div className="metric">
              <span className="metric-label">Active Scans:</span>
              <span className="metric-value">{health.active_scans}</span>
            </div>
            <div className="metric">
              <span className="metric-label">CPU Usage:</span>
              <span className="metric-value">
                {health.cpu_usage.toFixed(1)}%
              </span>
              <div className="metric-bar">
                <div
                  className="metric-fill"
                  style={{ width: `${Math.min(health.cpu_usage, 100)}%` }}
                />
              </div>
            </div>
            <div className="metric">
              <span className="metric-label">Memory Usage:</span>
              <span className="metric-value">
                {health.memory_usage.toFixed(1)}%
              </span>
              <div className="metric-bar">
                <div
                  className="metric-fill"
                  style={{ width: `${Math.min(health.memory_usage, 100)}%` }}
                />
              </div>
            </div>
            <div className="metric">
              <span className="metric-label">WebSocket Connections:</span>
              <span className="metric-value">{health.websocket_connections}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Uptime:</span>
              <span className="metric-value">{formatUptime(health.uptime_seconds)}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Last Updated:</span>
              <span className="metric-value text-xs">
                {new Date(health.timestamp).toLocaleTimeString()}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
