/**
 * Kaison K1 - Attack Surface Graph Visualization
 * Interactive graph showing hosts, services, vulnerabilities, and relationships
 * Uses Neo4j data to visualize the attack surface
 */

import React, { useState, useEffect, useRef } from 'react';
import { COLORS, UI, BRANDING } from '@/theme/branding';
import './AttackSurfaceGraph.css';

interface GraphNode {
  id: string;
  label: string;
  type: 'host' | 'service' | 'vulnerability' | 'asset';
  properties: Record<string, any>;
}

interface GraphEdge {
  source: string;
  target: string;
  type: string;
  properties?: Record<string, any>;
}

interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

interface GraphStats {
  total_hosts: number;
  total_services: number;
  total_vulnerabilities: number;
  critical_vulns: number;
  high_vulns: number;
}

const AttackSurfaceGraph: React.FC = () => {
  const [graphData, setGraphData] = useState<GraphData>({ nodes: [], edges: [] });
  const [stats, setStats] = useState<GraphStats>({
    total_hosts: 0,
    total_services: 0,
    total_vulnerabilities: 0,
    critical_vulns: 0,
    high_vulns: 0,
  });
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    fetchGraphData();
  }, []);

  useEffect(() => {
    if (graphData.nodes.length > 0) {
      renderGraph();
    }
  }, [graphData, filterType]);

  const fetchGraphData = async () => {
    try {
      // Fetch full graph
      const graphRes = await fetch('/api/v1/graph/attack-surface');
      const graphDataRes = await graphRes.json();

      if (graphDataRes.success) {
        setGraphData(graphDataRes.data.graph || { nodes: [], edges: [] });
      }

      // Fetch stats
      const statsRes = await fetch('/api/v1/graph/stats');
      const statsData = await statsRes.json();

      if (statsData.success) {
        setStats(statsData.data || stats);
      }

      setLoading(false);
    } catch (error) {
      console.error('Error fetching graph data:', error);
      setLoading(false);
    }
  };

  const renderGraph = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    canvas.width = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Filter nodes
    const filteredNodes = graphData.nodes.filter(node => {
      if (filterType !== 'all' && node.type !== filterType) return false;
      if (searchQuery && !node.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    });

    // Simple force-directed layout simulation
    const nodePositions = new Map<string, { x: number; y: number }>();
    const centerX = canvas.width / 2;
    const centerY = canvas.height / 2;
    const radius = Math.min(canvas.width, canvas.height) * 0.35;

    filteredNodes.forEach((node, idx) => {
      const angle = (idx / filteredNodes.length) * 2 * Math.PI;
      nodePositions.set(node.id, {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle),
      });
    });

    // Draw edges
    ctx.strokeStyle = COLORS.border;
    ctx.lineWidth = 1;
    graphData.edges.forEach(edge => {
      const sourcePos = nodePositions.get(edge.source);
      const targetPos = nodePositions.get(edge.target);

      if (sourcePos && targetPos) {
        ctx.beginPath();
        ctx.moveTo(sourcePos.x, sourcePos.y);
        ctx.lineTo(targetPos.x, targetPos.y);
        ctx.stroke();
      }
    });

    // Draw nodes
    filteredNodes.forEach(node => {
      const pos = nodePositions.get(node.id);
      if (!pos) return;

      // Node color based on type
      let color = COLORS.primary.main;
      switch (node.type) {
        case 'host':
          color = COLORS.status.info;
          break;
        case 'service':
          color = COLORS.status.success;
          break;
        case 'vulnerability':
          color = COLORS.status.critical;
          break;
        case 'asset':
          color = COLORS.primary.main;
          break;
      }

      // Draw node circle
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(pos.x, pos.y, 8, 0, 2 * Math.PI);
      ctx.fill();

      // Draw node label
      ctx.fillStyle = COLORS.text;
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(node.label.substring(0, 20), pos.x, pos.y + 20);
    });
  };

  const getNodeTypeColor = (type: string): string => {
    switch (type) {
      case 'host': return COLORS.status.info;
      case 'service': return COLORS.status.success;
      case 'vulnerability': return COLORS.status.critical;
      case 'asset': return COLORS.primary.main;
      default: return COLORS.textSecondary;
    }
  };

  if (loading) {
    return (
      <div className="graph-loading">
        <div className="spinner"></div>
        <p>Loading attack surface graph...</p>
      </div>
    );
  }

  return (
    <div className="attack-surface-graph" style={{
      backgroundColor: COLORS.background,
      color: COLORS.text
    }}>
      {/* Header */}
      <div className="graph-header">
        <div>
          <h1 style={{ color: COLORS.primary.main }}>Attack Surface Visualization</h1>
          <p style={{ color: COLORS.textSecondary }}>
            Interactive graph of hosts, services, and vulnerabilities
          </p>
        </div>
        <button
          onClick={fetchGraphData}
          className="refresh-btn"
          style={{
            backgroundColor: COLORS.primary.main,
            color: COLORS.text
          }}
        >
          Refresh
        </button>
      </div>

      {/* Statistics */}
      <div className="stats-grid">
        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.info }}>🖥️</div>
          <div className="stat-content">
            <h3>{stats.total_hosts}</h3>
            <p>Hosts</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.success }}>⚙️</div>
          <div className="stat-content">
            <h3>{stats.total_services}</h3>
            <p>Services</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.critical }}>🔓</div>
          <div className="stat-content">
            <h3>{stats.total_vulnerabilities}</h3>
            <p>Vulnerabilities</p>
          </div>
        </div>

        <div className="stat-card" style={{ backgroundColor: COLORS.surface }}>
          <div className="stat-icon" style={{ color: COLORS.status.error }}>⚠️</div>
          <div className="stat-content">
            <h3>{stats.critical_vulns + stats.high_vulns}</h3>
            <p>Critical/High</p>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="graph-controls" style={{ backgroundColor: COLORS.surface }}>
        <div className="control-group">
          <label style={{ color: COLORS.text }}>Filter:</label>
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          >
            <option value="all">All Nodes</option>
            <option value="host">Hosts Only</option>
            <option value="service">Services Only</option>
            <option value="vulnerability">Vulnerabilities Only</option>
            <option value="asset">Assets Only</option>
          </select>
        </div>

        <div className="control-group">
          <input
            type="text"
            placeholder="Search nodes..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ backgroundColor: COLORS.elevated, color: COLORS.text }}
          />
        </div>

        <div className="legend">
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: COLORS.status.info }}></span>
            <span>Hosts</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: COLORS.status.success }}></span>
            <span>Services</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: COLORS.status.critical }}></span>
            <span>Vulnerabilities</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot" style={{ backgroundColor: COLORS.primary.main }}></span>
            <span>Assets</span>
          </div>
        </div>
      </div>

      {/* Graph Canvas */}
      <div className="graph-container">
        <canvas
          ref={canvasRef}
          className="graph-canvas"
          style={{ backgroundColor: COLORS.elevated }}
        />
      </div>

      {/* Node List */}
      <div className="nodes-panel" style={{ backgroundColor: COLORS.surface }}>
        <h2 style={{ color: COLORS.primary.main }}>Nodes ({graphData.nodes.length})</h2>
        <div className="nodes-list">
          {graphData.nodes
            .filter(node => {
              if (filterType !== 'all' && node.type !== filterType) return false;
              if (searchQuery && !node.label.toLowerCase().includes(searchQuery.toLowerCase())) return false;
              return true;
            })
            .slice(0, 50)
            .map(node => (
              <div
                key={node.id}
                className="node-item"
                style={{
                  backgroundColor: COLORS.elevated,
                  borderLeft: `3px solid ${getNodeTypeColor(node.type)}`
                }}
                onClick={() => setSelectedNode(node)}
              >
                <div className="node-header">
                  <span className="node-type" style={{ color: getNodeTypeColor(node.type) }}>
                    {node.type.toUpperCase()}
                  </span>
                  <h4 style={{ color: COLORS.text }}>{node.label}</h4>
                </div>
                {node.properties.ip && (
                  <p style={{ color: COLORS.textSecondary }}>IP: {node.properties.ip}</p>
                )}
                {node.properties.port && (
                  <p style={{ color: COLORS.textSecondary }}>Port: {node.properties.port}</p>
                )}
                {node.properties.cvss_score && (
                  <p style={{ color: COLORS.status.critical }}>
                    CVSS: {node.properties.cvss_score}
                  </p>
                )}
              </div>
            ))}
        </div>
      </div>

      {/* Selected Node Details */}
      {selectedNode && (
        <div className="node-details-modal" onClick={() => setSelectedNode(null)}>
          <div
            className="node-details"
            style={{ backgroundColor: COLORS.surface }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="details-header">
              <h2 style={{ color: COLORS.primary.main }}>{selectedNode.label}</h2>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ color: COLORS.text }}
              >
                ✕
              </button>
            </div>

            <div className="details-content">
              <div className="detail-item">
                <span className="detail-label">Type:</span>
                <span className="detail-value" style={{ color: getNodeTypeColor(selectedNode.type) }}>
                  {selectedNode.type.toUpperCase()}
                </span>
              </div>

              <div className="detail-item">
                <span className="detail-label">ID:</span>
                <span className="detail-value">{selectedNode.id}</span>
              </div>

              <h3 style={{ color: COLORS.primary.main, marginTop: '1.5rem' }}>Properties</h3>
              <div className="properties-list">
                {Object.entries(selectedNode.properties).map(([key, value]) => (
                  <div key={key} className="property-item">
                    <span className="property-key">{key}:</span>
                    <span className="property-value">{JSON.stringify(value)}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AttackSurfaceGraph;
