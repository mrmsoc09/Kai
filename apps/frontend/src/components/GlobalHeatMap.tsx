/**
 * GlobalHeatMap — D3-powered world map of opportunity markers
 *
 * Renders a Natural Earth SVG projection with per-opportunity
 * circle markers.  Marker color = status, size = findings count.
 * Hover tooltip, status filter, and three view modes (map /
 * heatmap / clusters) are all client-side.
 *
 * No Leaflet dependency — uses d3-geo (already in the bundle).
 * World country outlines are lazy-loaded from jsdelivr CDN;
 * if offline the graticule grid + markers still render.
 */

import React, {
  useRef,
  useEffect,
  useState,
  useCallback,
  useMemo,
} from 'react';
import * as d3 from 'd3';
import { useWebSocket } from '@/hooks/useWebSocket';

/* ── Types ─────────────────────────────────────────────────────────────── */
export interface OpportunityMarker {
  id: string;
  name: string;
  platform: 'h1' | 'intigriti' | 'bugcrowd' | 'synack' | string;
  latitude: number;
  longitude: number;
  status: 'scanning' | 'completed' | 'pending';
  findings: number;
  payout_received: number;
  payout_estimated: number;
  active_scans: number;
  last_scan: string;
}

type FilterStatus = 'all' | 'scanning' | 'completed' | 'pending';
type ViewMode = 'map' | 'heatmap' | 'clusters';

/* ── Constants ─────────────────────────────────────────────────────────── */
const STATUS_COLORS: Record<string, string> = {
  scanning:  '#ff6b6b',
  completed: '#51cf66',
  pending:   '#ffd43b',
};

const WORLD_GEOJSON_URL =
  'https://cdn.jsdelivr.net/npm/@geo-maps/countries-land-110m@0.6.0/pkg/index.geo.json';

/* ── Tooltip Component ─────────────────────────────────────────────────── */
interface TooltipState {
  visible: boolean;
  x: number;
  y: number;
  opp: OpportunityMarker | null;
}

const MapTooltip: React.FC<{ tip: TooltipState }> = ({ tip }) => {
  if (!tip.visible || !tip.opp) return null;
  const opp = tip.opp;
  const color = STATUS_COLORS[opp.status] ?? '#D4AF37';
  return (
    <div
      style={{
        position: 'absolute',
        left: tip.x + 14,
        top: tip.y - 8,
        pointerEvents: 'none',
        background: 'linear-gradient(135deg,#111 0%,#1a1a1a 100%)',
        border: '1px solid #D4AF37',
        borderRadius: 5,
        padding: '10px 14px',
        zIndex: 20,
        minWidth: 220,
        boxShadow: '0 4px 20px rgba(212,175,55,0.15)',
      }}
    >
      <div style={{ color: '#D4AF37', fontFamily: 'IBM Plex Mono, monospace', fontSize: 12, fontWeight: 700, marginBottom: 6 }}>
        {opp.name}
      </div>
      <div style={{ fontSize: 11, lineHeight: 1.7, fontFamily: 'IBM Plex Mono, monospace', color: '#a0a0a0' }}>
        <div>Platform: <span style={{ color: '#e0e0e0' }}>{opp.platform.toUpperCase()}</span></div>
        <div>Status: <span style={{ color, fontWeight: 700 }}>{opp.status.toUpperCase()}</span></div>
        <div>Findings: <span style={{ color: '#D4AF37', fontWeight: 700 }}>{opp.findings}</span></div>
        <div>Payout: <span style={{ color: '#51cf66' }}>${opp.payout_received.toLocaleString()}</span></div>
        <div>Est: <span style={{ color: '#4dabf7' }}>${opp.payout_estimated.toLocaleString()}</span></div>
        {opp.active_scans > 0 && (
          <div>Active scans: <span style={{ color: '#ff6b6b' }}>{opp.active_scans}</span></div>
        )}
      </div>
      <div style={{ fontSize: 9, color: '#555', fontFamily: 'IBM Plex Mono, monospace', marginTop: 5 }}>
        {new Date(opp.last_scan).toLocaleString()}
      </div>
    </div>
  );
};

/* ── Main Component ────────────────────────────────────────────────────── */
export const GlobalHeatMap: React.FC = () => {
  const svgRef       = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const geoPathRef   = useRef<d3.GeoPath | null>(null);
  const projRef      = useRef<d3.GeoProjection | null>(null);
  const worldRef     = useRef<any>(null);            /* cached GeoJSON */

  const [opportunities, setOpportunities] = useState<OpportunityMarker[]>([]);
  const [filterStatus, setFilterStatus]   = useState<FilterStatus>('all');
  const [viewMode, setViewMode]           = useState<ViewMode>('map');
  const [tooltip, setTooltip]             = useState<TooltipState>({ visible: false, x: 0, y: 0, opp: null });
  const [mapReady, setMapReady]           = useState(false);
  const [dims, setDims]                   = useState({ w: 900, h: 460 });

  /* ── Load opportunities ──────────────────────────────────────────────── */
  const loadOpportunities = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/analytics/opportunities-map', { signal: AbortSignal.timeout(5000) });
      if (res.ok) {
        const data = await res.json();
        setOpportunities(data.opportunities ?? []);
      }
    } catch { /* silent — stale data remains */ }
  }, []);

  useEffect(() => {
    loadOpportunities();
    const id = setInterval(loadOpportunities, 30_000);
    return () => clearInterval(id);
  }, [loadOpportunities]);

  /* ── WebSocket: refresh on scan completion ───────────────────────────── */
  useWebSocket('/ws/scans', useCallback((msg: string) => {
    try {
      const data = JSON.parse(msg);
      if (data.type === 'scan_completed' || data.type === 'scan_update') {
        loadOpportunities();
      }
    } catch { /* ignore */ }
  }, [loadOpportunities]));

  /* ── Resize observer ─────────────────────────────────────────────────── */
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver(entries => {
      const { width } = entries[0].contentRect;
      if (width > 0) setDims({ w: width, h: Math.round(width * 0.48) });
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  /* ── Build/rebuild SVG base ──────────────────────────────────────────── */
  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    svg.selectAll('*').remove();

    const { w, h } = dims;

    /* Projection */
    const proj = d3.geoNaturalEarth1()
      .scale(w / (2 * Math.PI) * 0.9)
      .translate([w / 2, h / 2]);
    projRef.current = proj;
    const path = d3.geoPath().projection(proj);
    geoPathRef.current = path;

    /* Sphere background */
    svg.append('path')
      .datum({ type: 'Sphere' } as any)
      .attr('d', path as any)
      .attr('fill', '#06080f')
      .attr('stroke', 'rgba(212,175,55,0.4)')
      .attr('stroke-width', 1);

    /* Graticule grid */
    const graticule = d3.geoGraticule()();
    svg.append('path')
      .datum(graticule)
      .attr('d', path as any)
      .attr('fill', 'none')
      .attr('stroke', 'rgba(212,175,55,0.07)')
      .attr('stroke-width', 0.5);

    /* Country outlines — lazy-load from CDN */
    const drawCountries = (geoJson: any) => {
      svg.insert('g', ':first-child')
        .attr('class', 'countries')
        .selectAll('path')
        .data(geoJson.features)
        .join('path')
        .attr('d', path as any)
        .attr('fill', '#0d1117')
        .attr('stroke', 'rgba(212,175,55,0.18)')
        .attr('stroke-width', 0.4);
    };

    if (worldRef.current) {
      drawCountries(worldRef.current);
      setMapReady(true);
    } else {
      d3.json(WORLD_GEOJSON_URL)
        .then((geo: any) => {
          worldRef.current = geo;
          drawCountries(geo);
          setMapReady(true);
        })
        .catch(() => setMapReady(true)); /* degrade gracefully */
    }
  }, [dims]);

  /* ── Filter + project opportunities ─────────────────────────────────── */
  const filtered = useMemo(() => {
    if (filterStatus === 'all') return opportunities;
    return opportunities.filter(o => o.status === filterStatus);
  }, [opportunities, filterStatus]);

  /* ── Render markers ──────────────────────────────────────────────────── */
  useEffect(() => {
    if (!mapReady || !projRef.current || !svgRef.current) return;
    const svg = d3.select(svgRef.current);
    svg.select('.markers').remove();
    const g = svg.append('g').attr('class', 'markers');

    if (viewMode === 'heatmap') {
      /* Heatmap: blurred colored glow circles */
      filtered.forEach(opp => {
        const coords = projRef.current!([opp.longitude, opp.latitude]);
        if (!coords) return;
        const r = Math.min(40, Math.max(12, 12 + opp.findings * 1.2));
        const color = STATUS_COLORS[opp.status] ?? '#D4AF37';
        g.append('circle')
          .attr('cx', coords[0]).attr('cy', coords[1])
          .attr('r', r)
          .attr('fill', color)
          .attr('fill-opacity', 0.18)
          .attr('stroke', color)
          .attr('stroke-width', 1)
          .attr('stroke-opacity', 0.5)
          .attr('filter', 'blur(4px)');
      });
      return;
    }

    if (viewMode === 'clusters') {
      /* Clusters: group by ~5° grid cells */
      const cells: Record<string, OpportunityMarker[]> = {};
      filtered.forEach(opp => {
        const key = `${Math.round(opp.latitude / 5) * 5},${Math.round(opp.longitude / 5) * 5}`;
        (cells[key] = cells[key] ?? []).push(opp);
      });
      Object.entries(cells).forEach(([key, opps]) => {
        const [lat, lng] = key.split(',').map(Number);
        const coords = projRef.current!([lng, lat]);
        if (!coords) return;
        const r = Math.min(28, Math.max(10, 8 + opps.length * 2));
        const hasActive = opps.some(o => o.status === 'scanning');
        const color = hasActive ? '#ff6b6b' : '#D4AF37';
        const clusterG = g.append('g')
          .attr('class', 'cluster')
          .style('cursor', 'pointer');
        clusterG.append('circle')
          .attr('cx', coords[0]).attr('cy', coords[1])
          .attr('r', r)
          .attr('fill', color).attr('fill-opacity', 0.22)
          .attr('stroke', color).attr('stroke-width', 1.5);
        clusterG.append('text')
          .attr('x', coords[0]).attr('y', coords[1])
          .attr('dy', '0.35em')
          .attr('text-anchor', 'middle')
          .attr('fill', color)
          .attr('font-size', Math.max(9, r * 0.65))
          .attr('font-family', 'IBM Plex Mono, monospace')
          .attr('font-weight', 700)
          .text(opps.length);
      });
      return;
    }

    /* Standard map mode — one circle per opportunity */
    filtered.forEach(opp => {
      const coords = projRef.current!([opp.longitude, opp.latitude]);
      if (!coords) return;
      const r     = Math.min(16, Math.max(5, 5 + opp.findings * 0.4));
      const color = STATUS_COLORS[opp.status] ?? '#D4AF37';

      const mk = g.append('g')
        .attr('class', 'opp-marker')
        .style('cursor', 'pointer');

      /* Outer ring (pulsing for active scans) */
      if (opp.status === 'scanning') {
        mk.append('circle')
          .attr('cx', coords[0]).attr('cy', coords[1])
          .attr('r', r + 4)
          .attr('fill', 'none')
          .attr('stroke', color).attr('stroke-width', 1)
          .attr('stroke-opacity', 0.4);
      }

      /* Main marker */
      mk.append('circle')
        .attr('cx', coords[0]).attr('cy', coords[1])
        .attr('r', r)
        .attr('fill', color).attr('fill-opacity', 0.75)
        .attr('stroke', '#D4AF37').attr('stroke-width', 1.2);

      /* Interaction */
      mk.on('mouseenter', (event: MouseEvent) => {
        d3.select(event.currentTarget as Element)
          .select('circle:last-child')
          .attr('fill-opacity', 1)
          .attr('stroke-width', 2);
        const rect = containerRef.current!.getBoundingClientRect();
        setTooltip({
          visible: true,
          x: event.clientX - rect.left,
          y: event.clientY - rect.top,
          opp,
        });
      });

      mk.on('mousemove', (event: MouseEvent) => {
        const rect = containerRef.current!.getBoundingClientRect();
        setTooltip(prev => ({ ...prev, x: event.clientX - rect.left, y: event.clientY - rect.top }));
      });

      mk.on('mouseleave', (event: MouseEvent) => {
        d3.select(event.currentTarget as Element)
          .select('circle:last-child')
          .attr('fill-opacity', 0.75)
          .attr('stroke-width', 1.2);
        setTooltip(prev => ({ ...prev, visible: false }));
      });
    });
  }, [filtered, mapReady, viewMode]);

  /* ── Stats ───────────────────────────────────────────────────────────── */
  const stats = useMemo(() => ({
    total:     opportunities.length,
    scanning:  opportunities.filter(o => o.status === 'scanning').length,
    completed: opportunities.filter(o => o.status === 'completed').length,
    pending:   opportunities.filter(o => o.status === 'pending').length,
    totalPayout: opportunities.reduce((s, o) => s + o.payout_received, 0),
  }), [opportunities]);

  /* ── Render ──────────────────────────────────────────────────────────── */
  return (
    <div className="k1-heatmap-container">

      {/* ── Controls bar ───────────────────────────────────────────────── */}
      <div className="k1-map-controls">
        <div className="k1-map-title">
          <span className="k1-title-icon" aria-hidden="true">◉</span>
          GLOBAL OPPORTUNITY HEAT MAP
          <span className="k1-map-subtitle">
            {stats.total} targets · ${stats.totalPayout.toLocaleString()} received
          </span>
        </div>

        <div className="k1-map-filters" role="group" aria-label="Status filter">
          {(['all', 'scanning', 'completed', 'pending'] as FilterStatus[]).map(s => (
            <button
              key={s}
              className={`k1-map-filter-btn${filterStatus === s ? ' active' : ''}`}
              onClick={() => setFilterStatus(s)}
              style={filterStatus !== s && s !== 'all'
                ? { '--status-color': STATUS_COLORS[s] } as React.CSSProperties
                : undefined}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
              {s !== 'all' && (
                <span className="k1-filter-count">
                  {s === 'scanning' ? stats.scanning : s === 'completed' ? stats.completed : stats.pending}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="k1-map-view-modes" role="group" aria-label="View mode">
          {(['map', 'heatmap', 'clusters'] as ViewMode[]).map(m => (
            <button
              key={m}
              className={`k1-map-view-btn${viewMode === m ? ' active' : ''}`}
              onClick={() => setViewMode(m)}
              aria-pressed={viewMode === m}
            >
              {m === 'map' ? '⊙ Map' : m === 'heatmap' ? '⬤ Heat' : '◎ Cluster'}
            </button>
          ))}
        </div>
      </div>

      {/* ── SVG Map ────────────────────────────────────────────────────── */}
      <div className="k1-map-svg-container" ref={containerRef}>
        <svg
          ref={svgRef}
          width={dims.w}
          height={dims.h}
          aria-label="World map with opportunity markers"
          role="img"
        />
        <MapTooltip tip={tooltip} />
        {!mapReady && (
          <div className="k1-map-loading">Loading world map…</div>
        )}
      </div>

      {/* ── Legend ─────────────────────────────────────────────────────── */}
      <div className="k1-map-legend" role="list" aria-label="Map legend">
        {Object.entries(STATUS_COLORS).map(([status, color]) => (
          <div key={status} className="k1-legend-item" role="listitem">
            <span className="k1-legend-dot" style={{ background: color }} aria-hidden="true" />
            <span className="k1-legend-label">
              {status.charAt(0).toUpperCase() + status.slice(1)}
            </span>
          </div>
        ))}
        <div className="k1-legend-item">
          <span className="k1-legend-note" aria-label="Circle size scales with findings count">
            Circle size = findings count
          </span>
        </div>
        <div className="k1-legend-item">
          <span className="k1-legend-note">Click marker for details</span>
        </div>
      </div>

    </div>
  );
};

export default GlobalHeatMap;
