/**
 * Log Stream Viewer Component
 *
 * Real-time log streaming viewer with TMUX-style multi-view support.
 * Displays logs from active scans with filtering, search, and download capabilities.
 */
'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success' | 'debug';
  message: string;
  source?: string;
}

interface LogStreamViewerProps {
  scanId: string;
  fullScreen?: boolean;
}

const getLevelColor = (level: LogEntry['level']): string => {
  switch (level) {
    case 'error':
      return '#ef4444';
    case 'warning':
      return '#f97316';
    case 'success':
      return '#22c55e';
    case 'info':
      return '#3b82f6';
    case 'debug':
      return '#8b5cf6';
    default:
      return '#6b7280';
  }
};

const getLevelIcon = (level: LogEntry['level']): string => {
  switch (level) {
    case 'error':
      return '✗';
    case 'warning':
      return '⚠';
    case 'success':
      return '✓';
    case 'info':
      return 'ℹ';
    case 'debug':
      return '◆';
    default:
      return '•';
  }
};

export const LogStreamViewer: React.FC<LogStreamViewerProps> = ({ scanId, fullScreen = false }) => {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterLevel, setFilterLevel] = useState<LogEntry['level'] | 'all'>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'connecting'>('connecting');
  const logEndRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);

  // WebSocket for real-time log streaming
  const { connected } = useWebSocket(
    typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/logs/${scanId}`
      : null,
    (message) => {
      try {
        const data = JSON.parse(message);

        if (data.type === 'log_entry') {
          setLogs((prev) => [...prev, data.entry]);
        }

        if (data.type === 'log_batch') {
          setLogs((prev) => [...prev, ...data.entries]);
        }

        if (data.type === 'connection_status') {
          setConnectionStatus(data.status);
        }
      } catch (error) {
        console.error('Log stream parse error:', error);
      }
    }
  );

  useEffect(() => {
    setConnectionStatus(connected ? 'connected' : 'disconnected');
  }, [connected]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [logs, autoScroll]);

  const handleClearLogs = useCallback(() => {
    if (window.confirm('Clear all logs? This cannot be undone.')) {
      setLogs([]);
    }
  }, []);

  const handleDownloadLogs = useCallback(() => {
    const content = logs
      .map((log) => `[${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}`)
      .join('\n');

    const element = document.createElement('a');
    element.setAttribute('href', `data:text/plain;charset=utf-8,${encodeURIComponent(content)}`);
    element.setAttribute('download', `scan-${scanId}-logs-${Date.now()}.txt`);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  }, [logs, scanId]);

  const handleCopyLogs = useCallback(() => {
    const content = logs
      .map((log) => `[${log.timestamp}] ${log.level.toUpperCase()}: ${log.message}`)
      .join('\n');

    navigator.clipboard.writeText(content);
    alert('Logs copied to clipboard');
  }, [logs]);

  // Filter logs based on level and search term
  const filteredLogs = logs.filter((log) => {
    const levelMatch = filterLevel === 'all' || log.level === filterLevel;
    const searchMatch = !searchTerm || log.message.toLowerCase().includes(searchTerm.toLowerCase());
    return levelMatch && searchMatch;
  });

  const stats = {
    total: logs.length,
    errors: logs.filter((l) => l.level === 'error').length,
    warnings: logs.filter((l) => l.level === 'warning').length,
    success: logs.filter((l) => l.level === 'success').length,
  };

  return (
    <div className={`log-stream-viewer ${fullScreen ? 'full-screen' : ''}`}>
      {/* Toolbar */}
      <div className="log-toolbar">
        <div className="toolbar-left">
          <div className="connection-indicator">
            <span
              className={`indicator-dot ${connectionStatus}`}
              title={`Connection: ${connectionStatus}`}
            />
            <span className="indicator-text">{connectionStatus}</span>
          </div>

          <div className="log-stats">
            <span className="stat">
              <strong>{stats.total}</strong> logs
            </span>
            {stats.errors > 0 && (
              <span className="stat errors">
                <strong>{stats.errors}</strong> errors
              </span>
            )}
            {stats.warnings > 0 && (
              <span className="stat warnings">
                <strong>{stats.warnings}</strong> warnings
              </span>
            )}
            <span className="stat success">
              <strong>{stats.success}</strong> success
            </span>
          </div>
        </div>

        <div className="toolbar-center">
          {/* Filter Level */}
          <select
            className="filter-select"
            value={filterLevel}
            onChange={(e) => setFilterLevel(e.target.value as LogEntry['level'] | 'all')}
            aria-label="Filter by log level"
          >
            <option value="all">All Levels</option>
            <option value="error">Errors</option>
            <option value="warning">Warnings</option>
            <option value="success">Success</option>
            <option value="info">Info</option>
            <option value="debug">Debug</option>
          </select>

          {/* Search */}
          <input
            type="text"
            className="search-input"
            placeholder="Search logs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            aria-label="Search logs"
          />
        </div>

        <div className="toolbar-right">
          <label className="auto-scroll-toggle">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
            />
            <span>Auto Scroll</span>
          </label>

          <button
            className="btn btn-sm"
            onClick={handleCopyLogs}
            title="Copy logs to clipboard"
          >
            Copy
          </button>

          <button
            className="btn btn-sm"
            onClick={handleDownloadLogs}
            title="Download logs as text file"
          >
            Download
          </button>

          <button
            className="btn btn-sm btn-danger"
            onClick={handleClearLogs}
            title="Clear all logs"
          >
            Clear
          </button>
        </div>
      </div>

      {/* Log Output */}
      <div className="log-container" ref={logContainerRef}>
        {logs.length === 0 ? (
          <div className="log-placeholder">
            <p>Waiting for logs from scan {scanId}...</p>
            <span className="placeholder-hint">
              {connectionStatus === 'connected'
                ? 'Connected. Logs will appear here as the scan progresses.'
                : 'Connecting to log stream...'}
            </span>
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="log-placeholder">
            <p>No logs match your filter</p>
            <button className="btn btn-sm" onClick={() => setFilterLevel('all')}>
              Reset Filter
            </button>
          </div>
        ) : (
          <div className="log-output">
            {filteredLogs.map((log, idx) => (
              <div
                key={idx}
                className={`log-entry log-${log.level}`}
                style={{ borderLeftColor: getLevelColor(log.level) }}
              >
                <span className="log-icon" title={log.level}>
                  {getLevelIcon(log.level)}
                </span>
                <span className="log-timestamp">[{log.timestamp}]</span>
                <span className="log-level">{log.level.toUpperCase()}</span>
                {log.source && <span className="log-source">[{log.source}]</span>}
                <span className="log-message">{log.message}</span>
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="log-footer">
        <span className="footer-info">
          Showing {filteredLogs.length} of {logs.length} logs
        </span>
        <span className="footer-scan-id">Scan: {scanId}</span>
      </div>
    </div>
  );
};
