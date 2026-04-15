/**
 * Scan Control Panel Component
 *
 * Manages active scans with start/pause/kill controls, real-time status updates,
 * progress tracking, and findings display. Uses WebSocket for real-time updates.
 */
'use client';

import React, { useState, useCallback, useEffect } from 'react';
import { useWebSocket } from '@/hooks/useWebSocket';

export interface ActiveScan {
  scan_id: string;
  program_id: string;
  program_name: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  current_phase: number;
  total_phases: number;
  findings_count: number;
  duration_seconds: number;
  playbooks_completed: string[];
  current_playbook: string;
  rate_limit_hits: number;
  last_update: Date;
  vulnerability_breakdown: Record<string, number>;
}

interface ScanControlPanelProps {
  selectedScanId: string | null;
  onSelectScan: (scanId: string) => void;
}

const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = seconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${secs}s`;
  return `${secs}s`;
};

const formatTime = (date: Date): string => {
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
};

export const ScanControlPanel: React.FC<ScanControlPanelProps> = ({
  selectedScanId,
  onSelectScan,
}) => {
  const [scans, setScans] = useState<ActiveScan[]>([]);
  const [feedback, setFeedback] = useState<string>('');
  const [feedbackType, setFeedbackType] = useState<'info' | 'success' | 'error'>('info');
  const [isStarting, setIsStarting] = useState(false);
  const [activeActionScanId, setActiveActionScanId] = useState<string | null>(null);

  // WebSocket for real-time scan updates
  useWebSocket(
    typeof window !== 'undefined'
      ? `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws/scans`
      : null,
    (message) => {
      try {
        const data = JSON.parse(message);

        if (data.type === 'scan_update') {
          setScans((prev) => {
            const updated = prev.map((scan) =>
              scan.scan_id === data.scan.scan_id ? { ...data.scan, last_update: new Date() } : scan
            );
            return updated;
          });
          setFeedback(`Updated: Scan ${data.scan.program_name} - Phase ${data.scan.current_phase}/${data.scan.total_phases}`);
          setFeedbackType('info');
        }

        if (data.type === 'scan_completed') {
          setScans((prev) =>
            prev.map((scan) =>
              scan.scan_id === data.scan_id ? { ...scan, status: 'completed' } : scan
            )
          );
          setFeedback(`✓ Scan completed with ${data.findings_count} findings`);
          setFeedbackType('success');
        }

        if (data.type === 'scan_error') {
          setScans((prev) =>
            prev.map((scan) =>
              scan.scan_id === data.scan_id ? { ...scan, status: 'failed' } : scan
            )
          );
          setFeedback(`✗ Error on scan: ${data.error}`);
          setFeedbackType('error');
        }
      } catch (error) {
        console.error('WebSocket message parse error:', error);
      }
    }
  );

  const showFeedback = useCallback((message: string, type: 'info' | 'success' | 'error' = 'info') => {
    setFeedback(message);
    setFeedbackType(type);
  }, []);

  const handleStartScan = useCallback(async () => {
    setIsStarting(true);
    showFeedback('Starting scan...', 'info');

    try {
      const response = await fetch('/api/v1/scans/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ program_id: 'h1-example-com' }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to start scan');
      }

      const result = await response.json();

      const newScan: ActiveScan = {
        scan_id: result.scan_id,
        program_id: result.program_id,
        program_name: result.program_name,
        status: 'pending',
        current_phase: 0,
        total_phases: 9,
        findings_count: 0,
        duration_seconds: 0,
        playbooks_completed: [],
        current_playbook: 'Initialization',
        rate_limit_hits: 0,
        last_update: new Date(),
        vulnerability_breakdown: {},
      };

      setScans((prev) => [...prev, newScan]);
      onSelectScan(result.scan_id);
      showFeedback(`✓ Scan started: ${result.scan_id}`, 'success');
    } catch (error) {
      showFeedback(`✗ Failed to start scan: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
    } finally {
      setIsStarting(false);
    }
  }, [showFeedback, onSelectScan]);

  const handleKillScan = useCallback(
    async (scanId: string) => {
      if (!window.confirm('Are you sure? This will stop the scan immediately.')) {
        return;
      }

      setActiveActionScanId(scanId);
      showFeedback('Killing scan...', 'info');

      try {
        const response = await fetch(`/api/v1/scans/${scanId}/kill`, {
          method: 'POST',
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to kill scan');
        }

        setScans((prev) =>
          prev.map((scan) =>
            scan.scan_id === scanId ? { ...scan, status: 'cancelled' } : scan
          )
        );
        showFeedback(`✓ Scan ${scanId} aborted`, 'success');
      } catch (error) {
        showFeedback(`✗ Failed to kill scan: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
      } finally {
        setActiveActionScanId(null);
      }
    },
    [showFeedback]
  );

  const handlePauseScan = useCallback(
    async (scanId: string) => {
      setActiveActionScanId(scanId);
      showFeedback('Pausing scan...', 'info');

      try {
        const response = await fetch(`/api/v1/scans/${scanId}/pause`, {
          method: 'POST',
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to pause scan');
        }

        setScans((prev) =>
          prev.map((scan) =>
            scan.scan_id === scanId ? { ...scan, status: 'paused' } : scan
          )
        );
        showFeedback(`✓ Scan ${scanId} paused`, 'success');
      } catch (error) {
        showFeedback(`✗ Failed to pause scan: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
      } finally {
        setActiveActionScanId(null);
      }
    },
    [showFeedback]
  );

  const handleResumeScan = useCallback(
    async (scanId: string) => {
      setActiveActionScanId(scanId);
      showFeedback('Resuming scan...', 'info');

      try {
        const response = await fetch(`/api/v1/scans/${scanId}/resume`, {
          method: 'POST',
        });

        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.detail || 'Failed to resume scan');
        }

        setScans((prev) =>
          prev.map((scan) =>
            scan.scan_id === scanId ? { ...scan, status: 'running' } : scan
          )
        );
        showFeedback(`✓ Scan ${scanId} resumed`, 'success');
      } catch (error) {
        showFeedback(`✗ Failed to resume scan: ${error instanceof Error ? error.message : 'Unknown error'}`, 'error');
      } finally {
        setActiveActionScanId(null);
      }
    },
    [showFeedback]
  );

  const selectedScan = scans.find((s) => s.scan_id === selectedScanId);
  const activeScanCount = scans.filter((s) => s.status === 'running' || s.status === 'pending').length;

  return (
    <div className="scan-control-panel">
      {/* Panel Header */}
      <div className="panel-header">
        <div className="header-info">
          <h2>Active Scans Monitor</h2>
          <span className="scan-count">
            {activeScanCount} active
          </span>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleStartScan}
          disabled={isStarting}
        >
          {isStarting ? 'Starting...' : '+ Start New Scan'}
        </button>
      </div>

      {/* Feedback Message */}
      {feedback && (
        <div className={`feedback-message feedback-${feedbackType}`}>
          <span>{feedback}</span>
          <button
            className="feedback-close"
            onClick={() => setFeedback('')}
          >
            ✕
          </button>
        </div>
      )}

      {/* Scans Grid */}
      <div className="scans-container">
        {scans.length === 0 ? (
          <div className="empty-state">
            <p>No active scans. Start a new scan to begin.</p>
          </div>
        ) : (
          <div className="scans-grid">
            {scans.map((scan) => (
              <div
                key={scan.scan_id}
                className={`scan-card ${scan.status} ${selectedScanId === scan.scan_id ? 'selected' : ''}`}
                onClick={() => onSelectScan(scan.scan_id)}
                role="button"
                tabIndex={0}
              >
                {/* Card Header */}
                <div className="card-header">
                  <div className="header-title">
                    <h3>{scan.program_name}</h3>
                    <span className={`status-badge status-${scan.status}`}>
                      {scan.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="header-meta">
                    <span className="phase-indicator">
                      Phase {scan.current_phase}/{scan.total_phases}
                    </span>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="progress-section">
                  <div className="progress-bar">
                    <div
                      className="progress-fill"
                      style={{ width: `${(scan.current_phase / scan.total_phases) * 100}%` }}
                    ></div>
                  </div>
                  <span className="progress-percentage">
                    {Math.round((scan.current_phase / scan.total_phases) * 100)}%
                  </span>
                </div>

                {/* Scan Stats */}
                <div className="stats-section">
                  <div className="stat">
                    <span className="stat-label">Findings:</span>
                    <span className="stat-value">{scan.findings_count}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Duration:</span>
                    <span className="stat-value">{formatDuration(scan.duration_seconds)}</span>
                  </div>
                  <div className="stat">
                    <span className="stat-label">Rate Limits:</span>
                    <span className="stat-value">{scan.rate_limit_hits}</span>
                  </div>
                </div>

                {/* Playbook Info */}
                <div className="playbook-section">
                  <span className="playbook-label">Current:</span>
                  <span className="playbook-name">{scan.current_playbook}</span>
                </div>

                {/* Action Buttons */}
                {(scan.status === 'running' || scan.status === 'paused') && (
                  <div className="action-buttons">
                    {scan.status === 'running' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handlePauseScan(scan.scan_id);
                        }}
                        disabled={activeActionScanId === scan.scan_id}
                      >
                        Pause
                      </button>
                    )}
                    {scan.status === 'paused' && (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleResumeScan(scan.scan_id);
                        }}
                        disabled={activeActionScanId === scan.scan_id}
                      >
                        Resume
                      </button>
                    )}
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleKillScan(scan.scan_id);
                      }}
                      disabled={activeActionScanId === scan.scan_id}
                    >
                      Kill
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Selected Scan Details Panel */}
      {selectedScan && (
        <div className="details-panel">
          <h3>Scan Details: {selectedScan.program_name}</h3>
          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Scan ID:</span>
              <span className="detail-value">{selectedScan.scan_id}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Status:</span>
              <span className={`detail-value status-${selectedScan.status}`}>
                {selectedScan.status.toUpperCase()}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Phase Progress:</span>
              <span className="detail-value">
                {selectedScan.current_phase}/{selectedScan.total_phases}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Duration:</span>
              <span className="detail-value">{formatDuration(selectedScan.duration_seconds)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Total Findings:</span>
              <span className="detail-value">{selectedScan.findings_count}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Rate Limit Hits:</span>
              <span className="detail-value">{selectedScan.rate_limit_hits}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Last Update:</span>
              <span className="detail-value">{formatTime(selectedScan.last_update)}</span>
            </div>
          </div>

          {/* Vulnerability Breakdown */}
          {Object.keys(selectedScan.vulnerability_breakdown).length > 0 && (
            <div className="vuln-breakdown">
              <h4>Vulnerabilities Found</h4>
              <ul className="vuln-list">
                {Object.entries(selectedScan.vulnerability_breakdown)
                  .sort((a, b) => b[1] - a[1])
                  .map(([type, count]) => (
                    <li key={type}>
                      <span className="vuln-type">{type}:</span>
                      <span className="vuln-count">{count}</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {/* Completed Playbooks */}
          {selectedScan.playbooks_completed.length > 0 && (
            <div className="playbooks-completed">
              <h4>Completed Playbooks</h4>
              <ul className="playbook-list">
                {selectedScan.playbooks_completed.map((pb) => (
                  <li key={pb}>✓ {pb}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
