export interface Agent {
  id: string
  name: string
  status: 'active' | 'idle' | 'error' | 'offline'
  type: 'recon' | 'exploit' | 'analysis' | 'reporting'
  currentTask?: string
  progress: number
  lastSeen: Date
  metadata: Record<string, unknown>
}

export interface ScanResult {
  id: string
  target: string
  scanType: string
  status: 'running' | 'completed' | 'failed'
  startTime: Date
  endTime?: Date
  findings: Finding[]
  severityCounts: {
    critical: number
    high: number
    medium: number
    low: number
    info: number
  }
}

export interface Finding {
  id: string
  title: string
  description: string
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info'
  category: string
  evidence?: string
  remediation?: string
  timestamp: Date
}

export interface Wordlist {
  id: string
  name: string
  description: string
  entries: number
  size: number
  category: string
  lastModified: Date
  tags: string[]
}

export interface MindmapNode {
  id: string
  type: 'target' | 'subdomain' | 'service' | 'vulnerability' | 'note'
  label: string
  data: {
    description?: string
    severity?: string
    status?: string
    [key: string]: unknown
  }
  position: { x: number; y: number }
}

export interface MindmapEdge {
  id: string
  source: string
  target: string
  label?: string
  type?: 'default' | 'straight' | 'step' | 'smoothstep'
}

export interface ApiResponse<T> {
  data: T
  status: number
  message?: string
}

export interface WebSocketMessage {
  type: 'agent_update' | 'scan_progress' | 'new_finding' | 'system_alert'
  payload: unknown
  timestamp: Date
}
