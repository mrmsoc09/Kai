/**
 * Agent Force Graph - D3-based force-directed graph
 */

import React, { useEffect, useRef } from 'react';
import * as d3 from 'd3';
import { COLORS, UI } from '@/theme/branding';
import type { AgentNode } from './hooks/useAgentStatus';

export const AgentForceGraph: React.FC<{ agents: AgentNode[] }> = ({ agents }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || agents.length === 0) return;

    const width = svgRef.current.clientWidth;
    const height = 400;

    // Clear previous
    d3.select(svgRef.current).selectAll('*').remove();

    // Create nodes and links
    const nodes = agents.map(a => ({ ...a, x: width / 2, y: height / 2 }));
    const links = agents.slice(1).map((a, i) => ({ source: agents[0].id, target: a.id }));

    // Create simulation
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink(links).id((d: any) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2));

    const svg = d3.select(svgRef.current);

    // Draw links
    const link = svg.append('g').selectAll('line').data(links)
      .enter().append('line')
      .attr('stroke', COLORS.neutral.gray_300)
      .attr('stroke-width', 2);

    // Draw nodes
    const node = svg.append('g').selectAll('circle').data(nodes)
      .enter().append('circle')
      .attr('r', 20)
      .attr('fill', (d: any) => d.status === 'active' ? COLORS.status.success : COLORS.neutral.gray_400);

    // Labels
    const label = svg.append('g').selectAll('text').data(nodes)
      .enter().append('text')
      .text((d: any) => d.name)
      .attr('font-size', 10)
      .attr('text-anchor', 'middle');

    simulation.on('tick', () => {
      link.attr('x1', (d: any) => d.source.x).attr('y1', (d: any) => d.source.y)
          .attr('x2', (d: any) => d.target.x).attr('y2', (d: any) => d.target.y);
      node.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y);
      label.attr('x', (d: any) => d.x).attr('y', (d: any) => d.y + 35);
    });

    return () => { simulation.stop(); };
  }, [agents]);

  return <svg ref={svgRef} style={{ width: '100%', height: '400px' }} />;
};
