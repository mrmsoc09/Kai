/**
 * Kaison K1 - Ollama Setup Component
 * Manage local AI models for RAG and Kaison Composer
 * Download, configure, and monitor Ollama models
 */

import React, { useState, useEffect } from 'react';
import { COLORS, UI, BRANDING } from '@/theme/branding';
import './OllamaSetup.css';

interface HardwareInfo {
  vram: number;
  cpu_threads: number;
  ram: number;
  gpu_type: string;
  gpu_name: string;
}

interface ModelInfo {
  name: string;
  size: number;
  modified_at: string;
  digest: string;
  details?: {
    family: string;
    parameter_size: string;
    quantization_level: string;
  };
}

interface ModelRecommendation {
  name: string;
  description: string;
  priority: number;
  size_gb: number;
  min_vram_gb: number;
  performance_tier: string;
}

interface InstallProgress {
  model: string;
  status: string;
  progress: number;
  total?: number;
  completed?: number;
}

const OllamaSetup: React.FC = () => {
  const [hardware, setHardware] = useState<HardwareInfo | null>(null);
  const [installedModels, setInstalledModels] = useState<ModelInfo[]>([]);
  const [recommendations, setRecommendations] = useState<ModelRecommendation[]>([]);
  const [installProgress, setInstallProgress] = useState<InstallProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [ollamaRunning, setOllamaRunning] = useState(false);

  useEffect(() => {
    fetchOllamaData();
    const interval = setInterval(fetchOllamaData, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchOllamaData = async () => {
    try {
      // Check Ollama status
      const statusRes = await fetch('/api/v1/ollama/status');
      const statusData = await statusRes.json();
      setOllamaRunning(statusData.success && statusData.data.running);

      if (!statusData.data.running) {
        setLoading(false);
        return;
      }

      // Fetch hardware info
      const hwRes = await fetch('/api/v1/ollama/hardware');
      const hwData = await hwRes.json();

      if (hwData.success) {
        setHardware(hwData.data);
      }

      // Fetch installed models
      const modelsRes = await fetch('/api/v1/ollama/models');
      const modelsData = await modelsRes.json();

      if (modelsData.success) {
        setInstalledModels(modelsData.data.models || []);
      }

      // Fetch recommendations
      const recRes = await fetch('/api/v1/ollama/recommendations');
      const recData = await recRes.json();

      if (recData.success) {
        setRecommendations(recData.data.recommendations || []);
      }

      setLoading(false);
    } catch (error) {
      console.error('Error fetching Ollama data:', error);
      setLoading(false);
    }
  };

  const installModel = async (modelName: string) => {
    try {
      setInstallProgress({ model: modelName, status: 'downloading', progress: 0 });

      const res = await fetch('/api/v1/ollama/install', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_name: modelName }),
      });

      const reader = res.body?.getReader();
      if (!reader) return;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const text = new TextDecoder().decode(value);
        const lines = text.split('\n').filter(l => l.trim());

        for (const line of lines) {
          try {
            const data = JSON.parse(line);
            if (data.status) {
              setInstallProgress({
                model: modelName,
                status: data.status,
                progress: data.completed || 0,
                total: data.total || 0,
                completed: data.completed || 0,
              });
            }
          } catch (e) {
            // Ignore parse errors
          }
        }
      }

      setInstallProgress(null);
      fetchOllamaData();
    } catch (error) {
      console.error('Install failed:', error);
      setInstallProgress(null);
    }
  };

  const deleteModel = async (modelName: string) => {
    if (!confirm(`Delete model ${modelName}?`)) return;

    try {
      const res = await fetch(`/api/v1/ollama/models/${encodeURIComponent(modelName)}`, {
        method: 'DELETE',
      });

      const data = await res.json();

      if (data.success) {
        fetchOllamaData();
      }
    } catch (error) {
      console.error('Delete failed:', error);
    }
  };

  const formatBytes = (bytes: number): string => {
    const gb = bytes / (1024 ** 3);
    return `${gb.toFixed(2)} GB`;
  };

  const getPerformanceTierColor = (tier: string): string => {
    switch (tier.toLowerCase()) {
      case 'high': return COLORS.status.success;
      case 'medium': return COLORS.status.info;
      case 'low': return COLORS.status.warning;
      default: return COLORS.textSecondary;
    }
  };

  if (loading) {
    return (
      <div className="ollama-loading">
        <div className="spinner"></div>
        <p>Checking Ollama status...</p>
      </div>
    );
  }

  if (!ollamaRunning) {
    return (
      <div className="ollama-not-running" style={{ backgroundColor: COLORS.background, color: COLORS.text }}>
        <div className="error-panel" style={{
          backgroundColor: COLORS.surface,
          borderLeft: `4px solid ${COLORS.status.error}`
        }}>
          <h2 style={{ color: COLORS.status.error }}>Ollama Not Running</h2>
          <p>Ollama service is not available. Please ensure Ollama is installed and running.</p>
          <div className="installation-steps">
            <h3>Installation Steps:</h3>
            <ol>
              <li>Download Ollama from <a href="https://ollama.ai" target="_blank" rel="noopener noreferrer">ollama.ai</a></li>
              <li>Install and start the Ollama service</li>
              <li>Verify it's running: <code>ollama list</code></li>
              <li>Refresh this page</li>
            </ol>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="ollama-setup" style={{
      backgroundColor: COLORS.background,
      color: COLORS.text
    }}>
      {/* Header */}
      <div className="setup-header">
        <div>
          <h1 style={{ color: COLORS.primary.main }}>Ollama Model Manager</h1>
          <p style={{ color: COLORS.textSecondary }}>
            Manage local AI models for RAG and Kaison Composer
          </p>
        </div>
        <div className="status-badge" style={{
          backgroundColor: COLORS.status.success + '20',
          color: COLORS.status.success
        }}>
          ✓ Ollama Running
        </div>
      </div>

      {/* Hardware Information */}
      {hardware && (
        <div className="hardware-panel" style={{ backgroundColor: COLORS.surface }}>
          <h2 style={{ color: COLORS.primary.main }}>Hardware Detection</h2>
          <div className="hardware-grid">
            <div className="hw-item">
              <span className="hw-label">GPU:</span>
              <span className="hw-value">{hardware.gpu_name || 'Not detected'}</span>
            </div>
            <div className="hw-item">
              <span className="hw-label">VRAM:</span>
              <span className="hw-value" style={{ color: COLORS.status.info }}>
                {hardware.vram} GB
              </span>
            </div>
            <div className="hw-item">
              <span className="hw-label">RAM:</span>
              <span className="hw-value">{hardware.ram} GB</span>
            </div>
            <div className="hw-item">
              <span className="hw-label">CPU Threads:</span>
              <span className="hw-value">{hardware.cpu_threads}</span>
            </div>
          </div>
        </div>
      )}

      {/* Installed Models */}
      <div className="installed-section">
        <h2 style={{ color: COLORS.primary.main }}>
          Installed Models ({installedModels.length})
        </h2>

        {installedModels.length === 0 ? (
          <div className="empty-state" style={{ backgroundColor: COLORS.surface }}>
            <p>No models installed yet. Install recommended models below.</p>
          </div>
        ) : (
          <div className="models-grid">
            {installedModels.map(model => (
              <div key={model.name} className="model-card" style={{
                backgroundColor: COLORS.surface,
                borderLeft: `4px solid ${COLORS.primary.main}`
              }}>
                <div className="model-header">
                  <h3 style={{ color: COLORS.text }}>{model.name}</h3>
                  <button
                    onClick={() => deleteModel(model.name)}
                    className="delete-btn"
                    style={{ color: COLORS.status.error }}
                  >
                    Delete
                  </button>
                </div>
                <div className="model-info">
                  <div className="info-item">
                    <span className="label">Size:</span>
                    <span className="value">{formatBytes(model.size)}</span>
                  </div>
                  {model.details && (
                    <>
                      <div className="info-item">
                        <span className="label">Family:</span>
                        <span className="value">{model.details.family}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">Parameters:</span>
                        <span className="value">{model.details.parameter_size}</span>
                      </div>
                      <div className="info-item">
                        <span className="label">Quantization:</span>
                        <span className="value">{model.details.quantization_level}</span>
                      </div>
                    </>
                  )}
                  <div className="info-item">
                    <span className="label">Modified:</span>
                    <span className="value">
                      {new Date(model.modified_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Installation Progress */}
      {installProgress && (
        <div className="install-progress" style={{ backgroundColor: COLORS.surface }}>
          <h3 style={{ color: COLORS.primary.main }}>
            Installing {installProgress.model}...
          </h3>
          <div className="progress-bar-container">
            <div
              className="progress-bar"
              style={{
                width: `${(installProgress.completed! / installProgress.total!) * 100}%`,
                backgroundColor: COLORS.primary.main
              }}
            />
          </div>
          <p style={{ color: COLORS.textSecondary }}>
            {installProgress.status} - {formatBytes(installProgress.completed || 0)} / {formatBytes(installProgress.total || 0)}
          </p>
        </div>
      )}

      {/* Recommended Models */}
      <div className="recommendations-section">
        <h2 style={{ color: COLORS.primary.main }}>Recommended Models</h2>
        <p style={{ color: COLORS.textSecondary, marginBottom: '1.5rem' }}>
          Based on your hardware: {hardware?.vram}GB VRAM
        </p>

        <div className="recommendations-grid">
          {recommendations.map(rec => {
            const isInstalled = installedModels.some(m => m.name.includes(rec.name.split(':')[0]));
            const canInstall = hardware && hardware.vram >= rec.min_vram_gb;

            return (
              <div key={rec.name} className="recommendation-card" style={{
                backgroundColor: COLORS.surface,
                borderLeft: `4px solid ${getPerformanceTierColor(rec.performance_tier)}`
              }}>
                <div className="rec-header">
                  <h3 style={{ color: COLORS.text }}>{rec.name}</h3>
                  <div className="rec-badges">
                    <span className="priority-badge" style={{
                      backgroundColor: COLORS.primary.main + '20',
                      color: COLORS.primary.main
                    }}>
                      Priority {rec.priority}
                    </span>
                    <span className="tier-badge" style={{
                      backgroundColor: getPerformanceTierColor(rec.performance_tier) + '20',
                      color: getPerformanceTierColor(rec.performance_tier)
                    }}>
                      {rec.performance_tier}
                    </span>
                  </div>
                </div>

                <p className="rec-description" style={{ color: COLORS.textSecondary }}>
                  {rec.description}
                </p>

                <div className="rec-specs">
                  <div className="spec-item">
                    <span className="spec-label">Size:</span>
                    <span className="spec-value">{rec.size_gb.toFixed(1)} GB</span>
                  </div>
                  <div className="spec-item">
                    <span className="spec-label">Min VRAM:</span>
                    <span className="spec-value">{rec.min_vram_gb} GB</span>
                  </div>
                </div>

                <div className="rec-actions">
                  {isInstalled ? (
                    <div className="installed-indicator" style={{ color: COLORS.status.success }}>
                      ✓ Installed
                    </div>
                  ) : canInstall ? (
                    <button
                      onClick={() => installModel(rec.name)}
                      disabled={!!installProgress}
                      className="install-btn"
                      style={{
                        backgroundColor: COLORS.primary.main,
                        color: COLORS.text
                      }}
                    >
                      Install
                    </button>
                  ) : (
                    <div className="insufficient-hw" style={{ color: COLORS.status.warning }}>
                      ⚠ Insufficient VRAM
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default OllamaSetup;
