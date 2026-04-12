/**
 * TypeScript Type Definitions for Vulnerability Research & Analytics Dashboard
 * Provides comprehensive type safety for V-RAD component ecosystem
 */

// ============================================================================
// TELEMETRY & METRICS
// ============================================================================

export interface TelemetryMetrics {
  /** CPU utilization percentage (0-100) */
  cpuLoad: number;

  /** Core temperature percentage (0-100) */
  coreTemp: number;

  /** VRAM utilization percentage (0-100) */
  vramUtilization: number;

  /** Network bandwidth throughput in MB/s */
  bandwidthThroughput: number;

  /** Number of active analysis threads */
  analysisThreads: number;

  /** Rate limiting throttle level (0-100) */
  rateLimitLevel: number;
}

export interface TelemetryUpdate {
  timestamp: string;
  metrics: TelemetryMetrics;
  source: 'local' | 'backend';
}

export interface PerformanceMetric {
  label: string;
  value: number;
  unit: string;
  threshold?: {
    warning: number;
    critical: number;
  };
}

// ============================================================================
// VULNERABILITY & THREAT DATA
// ============================================================================

export type SeverityLevel = 'critical' | 'high' | 'medium' | 'low' | 'info';

export interface Vulnerability {
  id: string;
  title: string;
  description?: string;
  cveId?: string;
  severity: SeverityLevel;
  affectedComponents: string[];
  affectedNodeCount: number;
  discoveredAt: string;
  resolvedAt?: string;
  status: 'open' | 'in-progress' | 'resolved' | 'false-positive';
}

export interface VulnerabilityEvent {
  id: string;
  timestamp: string;
  severity: SeverityLevel;
  title: string;
  affectedNodes: number;
  vulnerability?: Vulnerability;
  sourceNode?: string;
  context?: Record<string, unknown>;
}

export interface GlobalThreatIntelligence {
  totalVulnerabilities: number;
  criticalCount: number;
  highCount: number;
  mediumCount: number;
  lowCount: number;
  activeEvents: VulnerabilityEvent[];
  lastUpdated: string;
}

// ============================================================================
// RESEARCH NODES & INFRASTRUCTURE
// ============================================================================

export type NodeStatus = 'active' | 'idle' | 'warning' | 'offline';
export type RegionCode = 'NA' | 'EU' | 'APAC' | 'RU' | 'SA' | 'AF' | 'OC';

export interface ResearchNode {
  id: string;
  name: string;
  region: RegionCode;
  vulnerabilityCount: number;
  lastUpdate: string;
  status: NodeStatus;
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  capabilities?: string[];
  uptime?: number;
  latency?: number;
}

export interface NodeCluster {
  region: RegionCode;
  nodes: ResearchNode[];
  aggregatedMetrics: {
    totalVulnerabilities: number;
    avgLatency: number;
    uptime: number;
  };
}

export interface GlobalNodeTopology {
  nodes: ResearchNode[];
  clusters: NodeCluster[];
  connectionLines: Array<{
    from: string;
    to: string;
    latency: number;
  }>;
}

// ============================================================================
// SYSTEM & INFRASTRUCTURE STATUS
// ============================================================================

export interface SystemControlState {
  ollamaFallback: boolean;
  geminiIntegration: boolean;
  vaultAccess: boolean;
  researchValidator: boolean;
}

export interface SystemStatus {
  operational: boolean;
  lastHealthCheck: string;
  controls: SystemControlState;
  errors?: SystemError[];
  warnings?: SystemWarning[];
}

export interface SystemError {
  code: string;
  message: string;
  timestamp: string;
  severity: SeverityLevel;
}

export interface SystemWarning {
  code: string;
  message: string;
  timestamp: string;
  recoverable: boolean;
}

// ============================================================================
// VISUALIZATION & UI STATE
// ============================================================================

export type ZoomLevel = 'global' | 'region' | 'local';
export type ViewportMode = 'ultrawide' | 'widescreen' | 'standard' | 'mobile';

export interface DashboardViewState {
  zoomLevel: ZoomLevel;
  viewport: ViewportMode;
  selectedNode?: string;
  selectedVulnerability?: string;
  timeRange: TimeRange;
  filters: DashboardFilters;
}

export interface TimeRange {
  start: Date;
  end: Date;
  granularity: 'minute' | 'hour' | 'day' | 'week';
}

export interface DashboardFilters {
  severities: SeverityLevel[];
  regions: RegionCode[];
  nodeStatus: NodeStatus[];
  vulnerabilityStatus: Array<'open' | 'in-progress' | 'resolved'>;
}

export interface ViewportDimensions {
  width: number;
  height: number;
  aspectRatio: number;
  isMobile: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isUltrawide: boolean;
}

// ============================================================================
// ANALYTICS & REPORTING
// ============================================================================

export interface AnalyticsData {
  totalScans: number;
  totalVulnerabilities: number;
  avgResolutionTime: number;
  mttr: number; // Mean Time To Remediate
  trends: TrendData[];
}

export interface TrendData {
  timestamp: string;
  vulnerabilityCount: number;
  activeScans: number;
  resolvedCount: number;
}

export interface Dashboard Report {
  id: string;
  generatedAt: string;
  period: TimeRange;
  summary: {
    totalVulnerabilities: number;
    newFindings: number;
    resolvedFindings: number;
    avgSeverity: SeverityLevel;
  };
  byRegion: Record<RegionCode, number>;
  bySeverity: Record<SeverityLevel, number>;
  trends: TrendData[];
}

// ============================================================================
// COMPONENT PROPS
// ============================================================================

export interface GlobeVisualizationProps {
  nodes: ResearchNode[];
  selectedNode?: string;
  onNodeSelect?: (nodeId: string) => void;
  showConnections?: boolean;
  animationEnabled?: boolean;
}

export interface LEDBarProps {
  value: number;
  max: number;
  color: 'green' | 'amber' | 'red';
  label?: string;
  animated?: boolean;
}

export interface CircularGaugeProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  color: string;
  showNeedle?: boolean;
  threshold?: {
    warning: number;
    critical: number;
  };
}

export interface WaveformVisualizerProps {
  data?: number[];
  color?: string;
  frequency?: number;
  amplitude?: number;
  animated?: boolean;
}

export interface SystemButtonProps {
  label: string;
  active: boolean;
  onClick?: () => void;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface EventLogSidebarProps {
  events: VulnerabilityEvent[];
  maxVisible?: number;
  onEventSelect?: (eventId: string) => void;
  autoScroll?: boolean;
}

export interface VulnerabilityListProps {
  vulnerabilities: Vulnerability[];
  sortBy?: 'severity' | 'date' | 'affectedCount';
  filterBySeverity?: SeverityLevel[];
  maxVisible?: number;
  onSelect?: (vulnId: string) => void;
}

export interface NodeStatusListProps {
  nodes: ResearchNode[];
  sortBy?: 'name' | 'vulnerabilityCount' | 'status';
  filterByStatus?: NodeStatus[];
  filterByRegion?: RegionCode[];
  onSelect?: (nodeId: string) => void;
}

// ============================================================================
// API RESPONSE TYPES
// ============================================================================

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
  };
  timestamp: string;
}

export interface TelemetryApiResponse extends ApiResponse<TelemetryMetrics> {}

export interface VulnerabilitiesApiResponse extends ApiResponse<Vulnerability[]> {}

export interface NodesApiResponse extends ApiResponse<ResearchNode[]> {}

export interface EventsApiResponse extends ApiResponse<VulnerabilityEvent[]> {}

// ============================================================================
// CONTEXT & STATE MANAGEMENT
// ============================================================================

export interface DashboardContextType {
  // State
  telemetry: TelemetryMetrics;
  nodes: ResearchNode[];
  events: VulnerabilityEvent[];
  viewState: DashboardViewState;
  systemStatus: SystemStatus;

  // Actions
  updateTelemetry: (metrics: TelemetryMetrics) => void;
  selectNode: (nodeId: string) => void;
  selectVulnerability: (vulnId: string) => void;
  setZoomLevel: (level: ZoomLevel) => void;
  updateFilters: (filters: Partial<DashboardFilters>) => void;
  refresh: () => Promise<void>;
}

export interface DashboardProviderProps {
  children: React.ReactNode;
  initialState?: Partial<DashboardContextType>;
  enableAutoRefresh?: boolean;
  refreshInterval?: number;
}

// ============================================================================
// ANIMATION & VISUAL EFFECTS
// ============================================================================

export type AnimationDirection = 'up' | 'down' | 'left' | 'right';
export type GlowIntensity = 'subtle' | 'normal' | 'intense';

export interface AnimationConfig {
  enabled: boolean;
  duration: number;
  delay?: number;
  easing?: 'ease' | 'ease-in' | 'ease-out' | 'ease-in-out' | 'linear';
  direction?: AnimationDirection;
}

export interface GlowEffect {
  enabled: boolean;
  intensity: GlowIntensity;
  color: string;
  blur?: number;
}

// ============================================================================
// ERROR HANDLING
// ============================================================================

export class DashboardError extends Error {
  code: string;
  context?: Record<string, unknown>;

  constructor(message: string, code: string, context?: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.context = context;
    this.name = 'DashboardError';
  }
}

export enum DashboardErrorCode {
  NETWORK_ERROR = 'NETWORK_ERROR',
  CANVAS_ERROR = 'CANVAS_ERROR',
  DATA_INVALID = 'DATA_INVALID',
  RENDER_ERROR = 'RENDER_ERROR',
  API_ERROR = 'API_ERROR',
  TIMEOUT = 'TIMEOUT',
}

// ============================================================================
// UTILITY TYPES
// ============================================================================

export type Nullable<T> = T | null;
export type Optional<T> = T | undefined;
export type DeepPartial<T> = {
  [P in keyof T]?: T[P] extends object ? DeepPartial<T[P]> : T[P];
};

export interface PaginationOptions {
  page: number;
  pageSize: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  hasMore: boolean;
}
