import React, { useState, useEffect } from 'react';
import { Globe, AlertCircle, Zap, Thermometer, Wifi } from 'lucide-react';

// ============================================================================
// VULNERABILITY RESEARCH & ANALYTICS DASHBOARD (V-RAD)
// Optimized for: LG 29WP60G-B (2560x1080 | 21:9 Aspect Ratio)
// ============================================================================

interface TelemetryMetrics {
  cpuLoad: number;
  coreTemp: number;
  vramUtilization: number;
  bandwidthThroughput: number;
  analysisThreads: number;
  rateLimitLevel: number;
}

interface ResearchNode {
  id: string;
  name: string;
  region: string;
  vulnerabilityCount: number;
  lastUpdate: string;
  status: 'active' | 'idle' | 'warning';
}

interface VulnerabilityEvent {
  id: string;
  timestamp: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  title: string;
  affectedNodes: number;
}

const ResearchDashboard: React.FC = () => {
  const [telemetry, setTelemetry] = useState<TelemetryMetrics>({
    cpuLoad: 68,
    coreTemp: 85,
    vramUtilization: 72,
    bandwidthThroughput: 3500,
    analysisThreads: 147,
    rateLimitLevel: 35,
  });

  const [globalEvents, setGlobalEvents] = useState<VulnerabilityEvent[]>([
    {
      id: 'vuln-001',
      timestamp: '2024-04-11T14:32:00Z',
      severity: 'critical',
      title: 'Remote Code Execution in Struts2',
      affectedNodes: 47,
    },
    {
      id: 'vuln-002',
      timestamp: '2024-04-11T13:45:00Z',
      severity: 'high',
      title: 'SQL Injection in Django ORM',
      affectedNodes: 23,
    },
    {
      id: 'vuln-003',
      timestamp: '2024-04-11T12:10:00Z',
      severity: 'high',
      title: 'XXE in Apache Commons',
      affectedNodes: 15,
    },
    {
      id: 'vuln-004',
      timestamp: '2024-04-11T11:22:00Z',
      severity: 'medium',
      title: 'CSRF Token Bypass',
      affectedNodes: 8,
    },
  ]);

  const [researchNodes] = useState<ResearchNode[]>([
    { id: 'ny-01', name: 'New York Hub', region: 'NA', vulnerabilityCount: 147, lastUpdate: '2024-04-11T14:30:00Z', status: 'active' },
    { id: 'lon-01', name: 'London Ops', region: 'EU', vulnerabilityCount: 89, lastUpdate: '2024-04-11T14:28:00Z', status: 'active' },
    { id: 'bej-01', name: 'Beijing Analysis', region: 'APAC', vulnerabilityCount: 156, lastUpdate: '2024-04-11T14:25:00Z', status: 'active' },
    { id: 'msk-01', name: 'Moscow Lab', region: 'RU', vulnerabilityCount: 62, lastUpdate: '2024-04-11T14:20:00Z', status: 'idle' },
    { id: 'syd-01', name: 'Sydney Research', region: 'APAC', vulnerabilityCount: 34, lastUpdate: '2024-04-11T14:15:00Z', status: 'active' },
  ]);

  const [systemStatus] = useState({
    ollamaFallback: true,
    geminiIntegration: true,
    vaultAccess: true,
    researchValidator: true,
  });

  // Simulate telemetry updates (STRICTLY CLAMPED TO PREVENT OVERFLOW)
  useEffect(() => {
    const interval = setInterval(() => {
      setTelemetry(prev => {
        const updateTelemetry = {
          cpuLoad: Math.max(0, Math.min(100, prev.cpuLoad + (Math.random() - 0.5) * 10)),
          coreTemp: Math.max(0, Math.min(100, prev.coreTemp + (Math.random() - 0.5) * 5)),
          vramUtilization: Math.max(0, Math.min(100, prev.vramUtilization + (Math.random() - 0.5) * 8)),
          bandwidthThroughput: Math.max(0, Math.min(5000, prev.bandwidthThroughput + (Math.random() - 0.5) * 500)),
          analysisThreads: Math.max(0, Math.min(200, prev.analysisThreads + Math.floor((Math.random() - 0.5) * 20))),
          rateLimitLevel: Math.max(0, Math.min(100, prev.rateLimitLevel + (Math.random() - 0.5) * 15)),
        };

        // VERIFY ALL VALUES ARE WITHIN BOUNDS
        Object.entries(updateTelemetry).forEach(([key, value]) => {
          if (typeof value === 'number' && (value < 0 || isNaN(value))) {
            console.warn(`[TELEMETRY] Invalid value for ${key}:`, value);
          }
        });

        return updateTelemetry;
      });
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="w-screen h-screen bg-black text-white overflow-hidden" style={{ backgroundColor: '#050505' }}>
      {/* ===== PRIMARY HEADER ===== */}
      <header className="h-20 border-b border-yellow-600 flex items-center justify-between px-8 z-50" style={{ borderColor: '#D4AF37' }}>
        <div className="flex items-center gap-4">
          {/* KaisonOne Medallion Logo - with rotational gold shimmer */}
          <div className="w-12 h-12 rounded-full border-2 flex items-center justify-center animate-coin-glow" style={{ borderColor: '#D4AF37' }}>
            <div className="w-10 h-10 rounded-full bg-gradient-to-b from-yellow-600 to-yellow-800 flex items-center justify-center text-xs font-bold">
              K1
            </div>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-wider" style={{ color: '#D4AF37' }}>
              KAISONONE SECURITY RESEARCH & ANALYTICS
            </h1>
            <p className="text-xs text-gray-400 mt-0.5">SYSTEMATIC VERIFICATION • GLOBAL VULNERABILITY MANAGEMENT</p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
          OPERATIONAL • UNIT: KAISON_01
        </div>
      </header>

      {/* ===== MAIN CONTENT GRID (21:9 Distribution - STRICT 40/35/25) ===== */}
      <div className="h-[calc(100vh-80px)] gap-4 p-4 relative" style={{ display: 'grid', gridTemplateColumns: '40% 35% 25%', columnGap: '1rem' }}>
        {/* ===== LEFT SECTION: Global Threat Intelligence (40%) ===== */}
        <div className="flex flex-col gap-4 relative z-10">
          {/* Holographic Globe & World Map */}
          <div className="flex-1 rounded p-4 relative overflow-hidden glassmorphic-panel">
            <GlobeVisualization nodes={researchNodes} />
          </div>

          {/* Event Logs Sidebar */}
          <div className="h-48 p-4 overflow-y-auto glassmorphic-panel" style={{ borderColor: '#D4AF37' }}>
            <h3 className="text-sm font-bold mb-3" style={{ color: '#D4AF37' }}>GLOBAL EVENT LOG</h3>
            <div className="space-y-2">
              {globalEvents.map((event, idx) => (
                <div key={event.id} className="text-xs border-l-2 pl-2 animate-data-jitter" style={{ borderColor: getSeverityColor(event.severity), animationDelay: `${idx * 0.05}s` }}>
                  <div className="flex justify-between items-start">
                    <span className="font-mono">{event.title}</span>
                    <span className="text-gray-500 text-[10px]">{new Date(event.timestamp).toLocaleTimeString()}</span>
                  </div>
                  <div className="text-gray-500 mt-1">{event.affectedNodes} nodes affected</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ===== CENTER SECTION: Research Nodes & Details (35%) ===== */}
        <div className="flex flex-col gap-4 relative z-10">
          {/* Top 10 High-Risk Vulnerabilities */}
          <div className="flex-1 p-4 overflow-y-auto min-h-0 glassmorphic-panel">
            <h3 className="text-sm font-bold mb-3 sticky top-0" style={{ color: '#D4AF37', backgroundColor: 'rgba(26, 26, 26, 0.7)' }}>TOP 10 VULNERABILITIES</h3>
            <div className="space-y-2">
              {researchNodes.map((node, idx) => (
                <div key={node.id} className="flex justify-between items-center text-xs border-b border-gray-700 pb-2 animate-data-jitter" style={{ animationDelay: `${idx * 0.06}s` }}>
                  <span className="font-mono">#{idx + 1} {node.name}</span>
                  <span className="text-red-400 font-bold">{node.vulnerabilityCount}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Research Nodes Status */}
          <div className="flex-1 p-4 overflow-y-auto glassmorphic-panel">
            <h3 className="text-sm font-bold mb-3 sticky top-0" style={{ color: '#D4AF37', backgroundColor: 'rgba(26, 26, 26, 0.7)' }}>VERIFIED RESEARCH NODES</h3>
            <div className="space-y-2">
              {researchNodes.map(node => (
                <div key={node.id} className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${node.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></div>
                    <span className="font-mono">{node.region}</span>
                  </div>
                  <span className="text-gray-400">{node.vulnerabilityCount} findings</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ===== RIGHT SECTION: Hardware Telemetry (25%) ===== */}
        <div className="flex flex-col gap-4 relative z-10">
          {/* Left Vertical LED Bar - Analysis Intensity */}
          <div className="h-32 p-3 flex flex-col justify-between glassmorphic-panel">
            <div className="text-xs font-bold" style={{ color: '#D4AF37' }}>ANALYSIS INTENSITY</div>
            <div className="flex-1 flex flex-col justify-center gap-1">
              <LEDBar value={telemetry.analysisThreads} max={200} color="green" />
            </div>
            <div className="text-xs text-gray-400 text-center animate-telemetry-pulse">{telemetry.analysisThreads} THREADS</div>
          </div>

          {/* Right Vertical LED Bar - Rate Limiter */}
          <div className="h-32 p-3 flex flex-col justify-between glassmorphic-panel">
            <div className="text-xs font-bold" style={{ color: '#D4AF37' }}>RATE LIMITER</div>
            <div className="flex-1 flex flex-col justify-center gap-1">
              <LEDBar value={telemetry.rateLimitLevel} max={100} color="amber" />
            </div>
            <div className="text-xs text-gray-400 text-center animate-telemetry-pulse">{telemetry.rateLimitLevel}% THROTTLE</div>
          </div>

          {/* Circular Gauge - CPU Load */}
          <CircularGauge label="CPU LOAD" value={telemetry.cpuLoad} max={100} unit="%" color="blue" />

          {/* Circular Gauge - Core Temp & VRAM */}
          <div className="p-3 glassmorphic-panel">
            <div className="text-xs font-bold mb-2" style={{ color: '#D4AF37' }}>CORE METRICS</div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="border-l-2 border-orange-500 pl-2">
                <div className="text-gray-400">CORE TEMP</div>
                <div className="font-bold text-orange-500">{telemetry.coreTemp.toFixed(0)}%</div>
              </div>
              <div className="border-l-2 border-purple-500 pl-2">
                <div className="text-gray-400">VRAM</div>
                <div className="font-bold text-purple-500">{telemetry.vramUtilization.toFixed(0)}%</div>
              </div>
            </div>
          </div>

          {/* Circular Gauge - Bandwidth Throughput */}
          <div className="p-3 glassmorphic-panel">
            <div className="text-xs font-bold mb-2" style={{ color: '#D4AF37' }}>BANDWIDTH</div>
            <div className="flex items-center justify-between">
              <div className="text-xs text-gray-400">THROUGHPUT</div>
              <div className="font-bold text-blue-400 animate-telemetry-pulse">{(telemetry.bandwidthThroughput / 1000).toFixed(1)} GB/s</div>
            </div>
            <div className="mt-2 h-12 rounded bg-gray-800 p-1 overflow-hidden">
              <WaveformVisualizer />
            </div>
          </div>

          {/* System Status Controls */}
          <div className="p-3 glassmorphic-panel">
            <div className="text-xs font-bold mb-2" style={{ color: '#D4AF37' }}>SYSTEM CONTROLS</div>
            <div className="grid grid-cols-2 gap-2">
              <SystemButton label="OLLAMA" active={systemStatus.ollamaFallback} />
              <SystemButton label="GEMINI" active={systemStatus.geminiIntegration} />
              <SystemButton label="VAULT" active={systemStatus.vaultAccess} />
              <SystemButton label="VALIDATOR" active={systemStatus.researchValidator} />
            </div>
          </div>

          {/* Platform Metadata */}
          <div className="text-center text-xs text-gray-500 py-2 glassmorphic-panel">
            <div className="animate-telemetry-pulse">UNIT: KAISON_01 | DEV: 2026</div>
          </div>
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// COMPONENT: Holographic Globe & World Map
// ============================================================================
const GlobeVisualization: React.FC<{ nodes: any[] }> = ({ nodes }) => {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Clear canvas
    ctx.fillStyle = '#050505';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.25;

    // Draw globe
    ctx.strokeStyle = '#D4AF37';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
    ctx.stroke();

    // Draw grid
    ctx.strokeStyle = '#444444';
    ctx.lineWidth = 0.5;
    for (let i = 0; i < 4; i++) {
      const r = (radius / 4) * (i + 1);
      ctx.beginPath();
      ctx.arc(centerX, centerY, r, 0, Math.PI * 2);
      ctx.stroke();
    }

    // Draw nodes and connection lines
    nodes.forEach((node, idx) => {
      const angle = (idx / nodes.length) * Math.PI * 2;
      const x = centerX + Math.cos(angle) * radius * 0.8;
      const y = centerY + Math.sin(angle) * radius * 0.8;

      // Connection line
      ctx.strokeStyle = node.status === 'active' ? '#10b98100' : '#6b7280';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.lineTo(x, y);
      ctx.stroke();

      // Node dot
      ctx.fillStyle = node.status === 'active' ? '#10b981' : '#6b7280';
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, Math.PI * 2);
      ctx.fill();

      // Label
      ctx.fillStyle = '#D4AF37';
      ctx.font = 'bold 10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(node.region, x, y - 12);
    });

    // Draw pulsing center
    const pulse = Math.sin(Date.now() / 500) * 0.5 + 0.5;
    ctx.fillStyle = `rgba(212, 175, 55, ${pulse})`;
    ctx.beginPath();
    ctx.arc(centerX, centerY, 6, 0, Math.PI * 2);
    ctx.fill();
  }, [nodes]);

  return (
    <div className="w-full h-full flex flex-col items-center justify-center relative">
      <canvas ref={canvasRef} className="w-full h-full absolute inset-0 z-0" />
      {/* CRT Scanline Overlay - very faint hardware-monitor aesthetic */}
      <div className="scanline-overlay z-5" />
      <div className="absolute bottom-4 left-4 text-xs text-gray-400 flex gap-4 z-20">
        <button className="px-3 py-1 border border-yellow-600 rounded hover:bg-yellow-900 transition-colors" style={{ borderColor: '#D4AF37' }}>
          GLOBAL
        </button>
        <button className="px-3 py-1 border border-gray-600 rounded hover:bg-gray-700 transition-colors">REGION</button>
        <button className="px-3 py-1 border border-gray-600 rounded hover:bg-gray-700 transition-colors">LOCAL</button>
      </div>
    </div>
  );
};

// ============================================================================
// COMPONENT: LED Bar (with clamping and critical state)
// ============================================================================
const LEDBar: React.FC<{ value: number; max: number; color: string }> = ({ value, max, color }) => {
  // CLAMP VALUE TO [0, max] TO PREVENT OVERFLOW
  const clampedValue = Math.max(0, Math.min(max, value));
  const percentage = (clampedValue / max) * 100;
  const segments = 7;
  const activeSegments = Math.ceil((percentage / 100) * segments);

  // Determine if in critical state (>90%) for visual feedback
  const isCritical = percentage > 90;
  const isWarning = percentage > 70 && percentage <= 90;

  const colorMap = {
    green: isCritical ? 'bg-red-600' : isWarning ? 'bg-amber-500' : 'bg-green-500',
    amber: isCritical ? 'bg-red-600' : isWarning ? 'bg-amber-600' : 'bg-amber-500',
    red: 'bg-red-500',
  };

  const glowColor = isCritical ? '#ef4444' : color === 'green' ? '#10b981' : color === 'amber' ? '#f59e0b' : '#ef4444';

  return (
    <div className={`flex gap-1 h-16 ${isCritical ? 'animate-telemetry-pulse' : ''}`}>
      {Array.from({ length: segments }).map((_, i) => (
        <div
          key={i}
          className={`flex-1 rounded transition-all ${i < activeSegments ? colorMap[color as keyof typeof colorMap] : 'bg-gray-700'} ${
            i < activeSegments ? 'shadow-lg' : ''
          }`}
          style={
            i < activeSegments
              ? {
                  boxShadow: `0 0 ${isCritical ? '15px' : '10px'} ${glowColor}`,
                  filter: isCritical ? 'brightness(1.2)' : 'brightness(1)',
                }
              : {}
          }
        />
      ))}
    </div>
  );
};

// ============================================================================
// COMPONENT: Circular Gauge (with clamping and critical state)
// ============================================================================
const CircularGauge: React.FC<{ label: string; value: number; max: number; unit: string; color: string }> = ({
  label,
  value,
  max,
  unit,
  color,
}) => {
  // CLAMP VALUE TO [0, max] TO PREVENT ARC OVERFLOW
  const clampedValue = Math.max(0, Math.min(max, value));
  const percentage = (clampedValue / max) * 100;

  // Determine critical/warning states
  const isCritical = percentage > 90;
  const isWarning = percentage > 70 && percentage <= 90;

  // Color determination with state-based styling
  let arcColor = color === 'blue' ? '#3b82f6' : color === 'red' ? '#ef4444' : '#10b981';
  let textColor = arcColor;
  let borderColor = '#D4AF37';

  if (isCritical) {
    arcColor = '#ef4444';
    textColor = '#ef4444';
    borderColor = '#dc2626';
  } else if (isWarning) {
    arcColor = '#f59e0b';
    textColor = '#f59e0b';
    borderColor = '#d97706';
  }

  return (
    <div
      className={`p-4 flex flex-col items-center transition-all glassmorphic-panel ${isCritical ? 'animate-pulse shadow-lg' : ''}`}
      style={{ borderColor: borderColor, boxShadow: isCritical ? `0 0 20px ${borderColor}` : '' }}
    >
      <div className="text-xs font-bold mb-3" style={{ color: '#D4AF37' }}>
        {label}
      </div>
      <svg width="80" height="80" viewBox="0 0 80 80" className="mb-2">
        {/* Outer circle background */}
        <circle cx="40" cy="40" r="35" fill="none" stroke="#333333" strokeWidth="2" />

        {/* Progress arc */}
        <circle
          cx="40"
          cy="40"
          r="35"
          fill="none"
          stroke={arcColor}
          strokeWidth={isCritical ? 4 : 3}
          strokeDasharray={`${2 * Math.PI * 35 * (percentage / 100)} ${2 * Math.PI * 35}`}
          strokeLinecap="round"
          transform="rotate(-90 40 40)"
          style={{ filter: isCritical ? 'drop-shadow(0 0 8px ' + arcColor + ')' : '' }}
        />

        {/* Center text */}
        <text x="40" y="45" textAnchor="middle" fontSize="20" fontWeight="bold" fill={textColor}>
          {clampedValue.toFixed(0)}
        </text>
      </svg>
      <div className="text-xs text-gray-400">{unit}</div>
      {/* Show warning/critical indicator */}
      {isCritical && <div className="text-xs text-red-500 mt-1 font-bold">⚠ CRITICAL</div>}
      {isWarning && <div className="text-xs text-amber-500 mt-1 font-bold">⚡ WARNING</div>}
    </div>
  );
};

// ============================================================================
// COMPONENT: Waveform Visualizer
// ============================================================================
const WaveformVisualizer: React.FC = () => {
  const canvasRef = React.useRef<HTMLCanvasElement>(null);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let time = 0;
    const animate = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;

      ctx.fillStyle = '#111111';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.strokeStyle = '#3b82f6';
      ctx.lineWidth = 2;
      ctx.beginPath();

      for (let x = 0; x < canvas.width; x += 5) {
        const y = canvas.height / 2 + Math.sin((x + time) / 10) * (canvas.height / 4);
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }

      ctx.stroke();

      time += 2;
      requestAnimationFrame(animate);
    };

    animate();
  }, []);

  return <canvas ref={canvasRef} className="w-full h-full" />;
};

// ============================================================================
// COMPONENT: System Button
// ============================================================================
const SystemButton: React.FC<{ label: string; active: boolean }> = ({ label, active }) => {
  return (
    <button
      className={`px-2 py-1 rounded text-xs font-bold transition-all ${
        active ? 'border-green-500 bg-green-900 text-green-300' : 'border-gray-600 bg-gray-800 text-gray-400'
      }`}
      style={active ? { borderColor: '#22c55e', boxShadow: '0 0 8px #22c55e' } : {}}
    >
      {label}
    </button>
  );
};

// ============================================================================
// UTILITIES
// ============================================================================
const getSeverityColor = (severity: string): string => {
  switch (severity) {
    case 'critical':
      return '#ef4444';
    case 'high':
      return '#f97316';
    case 'medium':
      return '#eab308';
    case 'low':
      return '#3b82f6';
    default:
      return '#6b7280';
  }
};

export default ResearchDashboard;
