/**
 * Unified Kaison Orchestration Dashboard Hub
 * K1 Orchestration Frontend
 * Primary user communication interface
 *
 * Orchestration is handled by Gemini CLI. See orchestration/gemini_orchestrator.py.
 *
 * Features:
 * - Real-time agent activity visualization
 * - Natural language command input
 * - Findings stream
 * - Workflow progress tracking
 * - Orchestration integration status
 */

import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'

interface Agent {
  agent_id: string
  role: string
  name: string
  status: 'idle' | 'working' | 'waiting' | 'error'
  current_task_id?: string
}

interface Finding {
  finding_id: string
  title: string
  severity: string
  confidence: number | string
  validated?: boolean
  source_tool?: string
  timestamp: string
}

interface WorkflowStep {
  step_id: string
  name: string
  status: 'pending' | 'in_progress' | 'complete'
  result?: any
}

interface Workflow {
  id: string
  target: string
  status: 'pending' | 'in_progress' | 'complete' | 'error'
  steps: WorkflowStep[]
  created_at: string
}

const ORCHESTRATION_API_BASE = '/api/v1/orchestration'
const http = axios.create({ withCredentials: true })

// ---------------------------------------------------------------------------
// Quota types and indicator
// ---------------------------------------------------------------------------

interface TierQuota {
  rpm_remaining: number
  rpd_remaining: number
  rpm_limit: number
  rpd_limit: number
}

interface QuotaData {
  flash: TierQuota
  flash_lite: TierQuota
  pro: TierQuota
  active_tier: string
  emergency_fallback_active: boolean
  flash_lite_spillover_active: boolean
  pro_restricted: boolean
}

/**
 * Color-coded quota indicator per the 5-tier spec:
 *   Flash > 100 RPD remaining : green
 *   Flash 50-100              : yellow
 *   Flash < 50                : orange  (spillover to Flash-Lite active)
 *   Pro   < 20                : red     (buffer zone — dispatch restricted)
 */
const QuotaIndicator: React.FC<{ quota?: QuotaData; onRefresh?: () => void }> = ({ quota, onRefresh }) => {
  if (!quota) {
    return (
      <div style={{ fontSize: '11px', color: '#8a95a7' }}>
        quota data unavailable
        {onRefresh && (
          <button
            onClick={onRefresh}
            style={{
              marginLeft: '8px', background: 'none', border: '1px solid #355E3B',
              borderRadius: '3px', color: '#355E3B', fontSize: '10px', cursor: 'pointer',
              padding: '1px 6px',
            }}
          >
            Retry
          </button>
        )}
      </div>
    )
  }

  const flashRpd = quota.flash?.rpd_remaining ?? 0
  const flashRpdLimit = quota.flash?.rpd_limit ?? 250
  const flashColor =
    flashRpd > 100 ? '#22c55e' :
    flashRpd > 50  ? '#fbbf24' :
                     '#f97316'  // orange — spillover active

  const liteRpd = quota.flash_lite?.rpd_remaining ?? 0
  const liteRpdLimit = quota.flash_lite?.rpd_limit ?? 1000

  const proRpd = quota.pro?.rpd_remaining ?? 0
  const proRpdLimit = quota.pro?.rpd_limit ?? 100
  const proColor = proRpd < 20 ? '#ef4444' : '#22c55e'

  const barStyle = (color: string, pct: number): React.CSSProperties => ({
    height: '4px',
    borderRadius: '2px',
    backgroundColor: '#2a3445',
    marginTop: '3px',
    overflow: 'hidden',
    position: 'relative',
  })

  const fillStyle = (color: string, pct: number): React.CSSProperties => ({
    height: '100%',
    width: `${Math.max(0, Math.min(100, pct))}%`,
    backgroundColor: color,
    transition: 'width 0.4s ease',
  })

  const row = (
    label: string,
    rpd: number,
    limit: number,
    color: string,
    note?: string,
  ) => (
    <div style={{ marginBottom: '8px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px' }}>
        <span style={{ color: '#8a95a7' }}>{label}</span>
        <span style={{ color }}>{rpd}/{limit} RPD{note ? ` · ${note}` : ''}</span>
      </div>
      <div style={barStyle(color, (rpd / limit) * 100)}>
        <div style={fillStyle(color, (rpd / limit) * 100)} />
      </div>
    </div>
  )

  return (
    <div style={{ fontSize: '11px' }}>
      {quota.emergency_fallback_active && (
        <div style={{
          padding: '4px 8px', borderRadius: '4px',
          backgroundColor: 'rgba(239,68,68,0.15)', color: '#ef4444',
          marginBottom: '8px', fontWeight: 600,
        }}>
          ⚠ EMERGENCY: local Tier 5 active
        </div>
      )}
      {row(
        'Flash (T1)',
        flashRpd,
        flashRpdLimit,
        flashColor,
        quota.flash_lite_spillover_active ? 'spillover →T2' : undefined,
      )}
      {row('Flash-Lite (T2)', liteRpd, liteRpdLimit, '#60a5fa')}
      {row(
        'Pro (T3)',
        proRpd,
        proRpdLimit,
        proColor,
        quota.pro_restricted ? 'restricted' : undefined,
      )}
      <div style={{ color: '#8a95a7', marginTop: '4px' }}>
        Active tier: <strong style={{ color: '#c7d2e0' }}>{quota.active_tier}</strong>
      </div>
    </div>
  )
}

export const UnifiedOrchestrationDashboard: React.FC = () => {
  // State
  const [command, setCommand] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [currentWorkflow, setCurrentWorkflow] = useState<Workflow | null>(null)
  const [orchestrationConnected, setOrchestrationConnected] = useState(false)
  const [isHunting, setIsHunting] = useState(false)
  const [target, setTarget] = useState('')
  const [llmStats, setLLMStats] = useState<any>(null)
  const [quota, setQuota] = useState<QuotaData | undefined>(undefined)
  const [mcpServers, setMCPServers] = useState<any[]>([])
  // Q6: Live system health state (polled every 10s)
  const [systemHealth, setSystemHealth] = useState<Record<string, boolean>>({
    llm: true, mcp: true, a2a: true, orchestration: false,
  })

  const wsRef = useRef<WebSocket | null>(null)
  const API_URL = `http://localhost:8000${ORCHESTRATION_API_BASE}`

  // Q1: Standalone quota fetch — callable on demand (retry button) or on interval.
  const fetchQuota = React.useCallback(async () => {
    try {
      const r = await http.get(`${API_URL}/quota`)
      setQuota(r.data as QuotaData)
    } catch {
      // Leave existing quota data in place; null means never loaded.
    }
  }, [API_URL])

  // Q6: Poll health endpoint every 10 seconds.
  useEffect(() => {
    const pollHealth = async () => {
      try {
        const r = await http.get(`${API_URL}/health`)
        const sys = r.data.systems ?? {}
        setOrchestrationConnected(sys.orchestration?.status === 'operational')
        setSystemHealth({
          llm: sys.llm?.status === 'operational',
          mcp: sys.mcp?.status === 'operational',
          a2a: sys.a2a?.status === 'operational',
          orchestration: sys.orchestration?.status === 'operational',
        })
      } catch {
        setOrchestrationConnected(false)
        setSystemHealth({ llm: false, mcp: false, a2a: false, orchestration: false })
      }
    }
    pollHealth()
    const healthInterval = setInterval(pollHealth, 10_000)
    return () => clearInterval(healthInterval)
  }, [API_URL])

  // Initialize dashboard
  useEffect(() => {
    const initializeDashboard = async () => {
      try {
        // Get agent status
        const agentsResponse = await http.get(`${API_URL}/agents`)
        setAgents(agentsResponse.data.agents || [])

        // Get MCP servers
        const mcpResponse = await http.get(`${API_URL}/mcp/registry`)
        setMCPServers(mcpResponse.data.servers || [])

        // Get LLM stats
        const llmResponse = await http.get(`${API_URL}/llm/providers`)
        setLLMStats(llmResponse.data)

        // Quota fetched separately so it can be retried independently (Q1).
        await fetchQuota()

      } catch (error) {
        console.error('[Orchestration] Failed to initialize dashboard:', error)
      }
    }

    initializeDashboard()

    // Setup WebSocket for real-time updates
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${wsProtocol}://${window.location.host}${ORCHESTRATION_API_BASE}/ws/agents`
    const ws = new WebSocket(wsUrl)

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'agent_update') {
        setAgents(data.status.agents || [])
      }
    }

    wsRef.current = ws

    return () => {
      ws.close()
    }
  }, [])

  // Handle natural language command
  const handleCommand = async () => {
    if (!command.trim()) return

    try {
      const response = await http.post(
        `${API_URL}/commands/natural-language`,
        {
          query: command,
          context: { user_id: 'current_user', timestamp: new Date().toISOString() }
        }
      )

      console.log('[Orchestration] Command executed:', response.data)
      setCommand('')

      // Refresh workflows
      await refreshWorkflows()

    } catch (error) {
      console.error('[Orchestration] Command execution failed:', error)
    }
  }

  // Start quick hunt
  const handleQuickHunt = async () => {
    if (!target.trim()) return

    try {
      setIsHunting(true)

      const response = await http.post(`${API_URL}/workflows/hunt?target=${target}`, {})

      const workflowId = response.data.workflow_id
      setCurrentWorkflow(response.data)

      // Connect to workflow WebSocket
      const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const wsUrl = `${wsProtocol}://${window.location.host}${ORCHESTRATION_API_BASE}/ws/workflows/${workflowId}`
      const ws = new WebSocket(wsUrl)

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        if (data.type === 'status_update') {
          console.log('[Orchestration] Workflow status:', data)
        } else if (data.type === 'finding_discovered') {
          setFindings((prev) => [...prev, data.finding])
        }
      }

      // Auto-refresh workflow status
      const interval = setInterval(async () => {
        try {
          const statusResponse = await http.get(`${API_URL}/workflows/${workflowId}`)

          setCurrentWorkflow(statusResponse.data)

          if (statusResponse.data.status === 'complete') {
            clearInterval(interval)
            setIsHunting(false)
          }

        } catch (error) {
          console.error('[Orchestration] Failed to fetch workflow status:', error)
        }
      }, 2000)

    } catch (error) {
      console.error('[Orchestration] Hunt workflow creation failed:', error)
      setIsHunting(false)
    }
  }

  // Refresh workflows
  const refreshWorkflows = async () => {
    try {
      const response = await http.get(`${API_URL}/workflows`)

      setWorkflows(response.data.workflows || [])

    } catch (error) {
      console.error('[Orchestration] Failed to fetch workflows:', error)
    }
  }

  // Render agent status indicator
  const renderAgentLane = (agent: Agent) => {
    // Q2: Proper hex values — named CSS colors like '#gray' do not render.
    const statusColor: Record<string, string> = {
      idle: '#4B5563',
      working: '#22c55e',
      waiting: '#fbbf24',
      error: '#ef4444',
    }

    return (
      <div key={agent.agent_id} className="agent-lane" style={{ marginBottom: '12px' }}>
        <div className="agent-header" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            className="status-dot"
            style={{
              width: '12px',
              height: '12px',
              borderRadius: '50%',
              backgroundColor: statusColor[agent.status] || '#gray'
            }}
          />
          <span className="agent-role" style={{ fontWeight: 600 }}>
            {agent.name}
          </span>
          <span className="agent-status" style={{ fontSize: '12px', color: '#8a95a7' }}>
            ({agent.status})
          </span>
        </div>
        {agent.current_task_id && (
          <div
            className="current-task"
            style={{ fontSize: '12px', marginTop: '4px', color: '#0066CC' }}
          >
            Working on: {agent.current_task_id}
          </div>
        )}
      </div>
    )
  }

  // Render workflow progress
  const renderWorkflowProgress = (workflow: Workflow) => {
    const completedSteps = workflow.steps.filter((s) => s.status === 'complete').length

    return (
      <div
        className="workflow-progress"
        style={{
          padding: '12px',
          backgroundColor: '#0f141b',
          borderRadius: '4px',
          marginBottom: '12px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontWeight: 600 }}>{workflow.target}</span>
          <span style={{ fontSize: '12px', color: '#8a95a7' }}>
            {completedSteps}/{workflow.steps.length} steps
          </span>
        </div>

        <div
          className="progress-bar"
          style={{
            width: '100%',
            height: '6px',
            backgroundColor: '#2a3445',
            borderRadius: '3px',
            overflow: 'hidden'
          }}
        >
          <div
            style={{
              width: `${(completedSteps / workflow.steps.length) * 100}%`,
              height: '100%',
              backgroundColor: '#0066CC',
              transition: 'width 0.3s ease'
            }}
          />
        </div>

        <div style={{ marginTop: '8px', fontSize: '12px' }}>
          {workflow.steps
            .filter((s) => s.status !== 'pending')
            .map((s) => (
              <div key={s.step_id} style={{ marginBottom: '4px' }}>
                {'\u2713'} {s.name}
              </div>
            ))}
        </div>
      </div>
    )
  }

  // Main render
  return (
    <div
      className="unified-dashboard"
      style={{
        display: 'grid',
        gridTemplateColumns: '300px 1fr 350px',
        gap: '16px',
        padding: '16px',
        backgroundColor: '#0b0f14',
        minHeight: '100vh'
      }}
    >
      {/* Left Sidebar: Agent Status */}
      <div className="agent-panel" style={{ borderRight: '1px solid #355E3B' }}>
        <h3 style={{ marginBottom: '16px' }}>Active Agents</h3>

        <div
          className="connection-status"
          style={{
            padding: '8px',
            backgroundColor: orchestrationConnected ? 'rgba(95, 143, 107, 0.12)' : 'rgba(239, 68, 68, 0.12)',
            borderRadius: '4px',
            marginBottom: '16px',
            fontSize: '12px'
          }}
        >
          Orchestration: {orchestrationConnected ? '\u{1F7E2} Connected' : '\u{1F534} Offline'}
        </div>

        <div className="agents-list">
          {agents.length > 0 ? (
            agents.map((agent) => renderAgentLane(agent))
          ) : (
            <p style={{ color: '#7b8798', fontSize: '12px' }}>No agents active</p>
          )}
        </div>

        <hr style={{ margin: '16px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>MCP Servers</h4>
        <div className="mcp-status">
          {mcpServers.map((server) => (
            <div key={server.server_id} style={{ fontSize: '12px', marginBottom: '8px' }}>
              <span style={{ color: server.status === 'online' ? '#22c55e' : '#7b8798' }}>{'\u25CF'}</span>
              {' '}
              {server.name} ({server.tools?.length || 0} tools)
            </div>
          ))}
        </div>

        <hr style={{ margin: '16px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>LLM Status</h4>
        <div className="llm-status" style={{ fontSize: '12px' }}>
          <div>Primary: {llmStats?.primary || 'N/A'}</div>
          <div style={{ marginTop: '4px', color: '#8a95a7' }}>
            Cost (session): ${llmStats?.stats?.total_cost_usd?.toFixed(2) || '0.00'}
          </div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <h4 style={{ marginBottom: '8px' }}>Quota</h4>
        <QuotaIndicator quota={quota} onRefresh={fetchQuota} />
      </div>

      {/* Center: Command & Results */}
      <div className="main-content">
        {/* Quick Hunt Section */}
        <div
          className="quick-hunt-section"
          style={{
            padding: '16px',
            backgroundColor: '#0f141b',
            borderRadius: '8px',
            marginBottom: '24px'
          }}
        >
          <h2 style={{ marginBottom: '16px' }}>Quick Vulnerability Hunt</h2>

          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input
              type="text"
              placeholder="Enter target domain (e.g., example.com)"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleQuickHunt()}
              style={{
                flex: 1,
                padding: '8px',
                border: '1px solid #2a3445',
                borderRadius: '4px',
                fontFamily: 'monospace'
              }}
              disabled={isHunting}
            />
            <button
              onClick={handleQuickHunt}
              disabled={isHunting || !target.trim()}
              style={{
                padding: '8px 16px',
                backgroundColor: isHunting ? '#2a3445' : '#0066CC',
                color: '#c7d2e0',
                border: 'none',
                borderRadius: '4px',
                cursor: isHunting ? 'not-allowed' : 'pointer',
                fontWeight: 600
              }}
            >
              {isHunting ? 'Hunting...' : 'Start Hunt'}
            </button>
          </div>

          <p style={{ fontSize: '12px', color: '#8a95a7', margin: 0 }}>
            Agents will automatically discover vulnerabilities, validate findings, analyze chains, and generate reports.
          </p>
        </div>

        {/* Natural Language Commands */}
        <div
          className="command-section"
          style={{
            padding: '16px',
            backgroundColor: '#0f141b',
            borderRadius: '8px',
            marginBottom: '24px'
          }}
        >
          <h3 style={{ marginBottom: '12px' }}>Natural Language Commands</h3>

          <div style={{ display: 'flex', gap: '8px', marginBottom: '12px' }}>
            <input
              type="text"
              placeholder="Try: 'analyze this for attack chains' or 'validate the evidence quality'"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleCommand()}
              style={{
                flex: 1,
                padding: '8px',
                border: '1px solid #2a3445',
                borderRadius: '4px'
              }}
            />
            <button
              onClick={handleCommand}
              disabled={!command.trim()}
              style={{
                padding: '8px 16px',
                backgroundColor: command.trim() ? '#0066CC' : '#2a3445',
                color: '#c7d2e0',
                border: 'none',
                borderRadius: '4px',
                cursor: command.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              Send
            </button>
          </div>

          <div style={{ fontSize: '12px', color: '#8a95a7' }}>
            <strong>Examples:</strong>
            <ul style={{ marginTop: '8px', paddingLeft: '16px' }}>
              <li>Find all critical vulnerabilities</li>
              <li>Build attack chains for this target</li>
              <li>Generate professional report</li>
              <li>Match findings to bug bounty programs</li>
            </ul>
          </div>
        </div>

        {/* Workflow Progress */}
        {currentWorkflow && (
          <div
            className="workflow-section"
            style={{
              padding: '16px',
              backgroundColor: '#0f141b',
              borderRadius: '8px',
              marginBottom: '24px'
            }}
          >
            <h3 style={{ marginBottom: '12px' }}>Current Workflow</h3>
            {renderWorkflowProgress(currentWorkflow)}
          </div>
        )}

        {/* Findings Stream */}
        {findings.length > 0 && (
          <div
            className="findings-section"
            style={{
              padding: '16px',
              backgroundColor: '#0f141b',
              borderRadius: '8px'
            }}
          >
            <h3 style={{ marginBottom: '12px' }}>Discovered Vulnerabilities</h3>

            {findings.map((finding) => {
              const sev = (finding.severity || 'info').toLowerCase()
              const color =
                sev === 'critical'
                  ? '#d32f2f'
                  : sev === 'high'
                    ? '#f57c00'
                    : sev === 'medium'
                      ? '#fbc02d'
                      : '#0288d1'
              return (
                <div
                  key={finding.finding_id}
                  style={{
                    padding: '12px',
                    backgroundColor: '#111316',
                    borderLeft: `4px solid ${color}`,
                    marginBottom: '8px',
                    borderRadius: '2px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 600 }}>{finding.title}</div>
                    {finding.validated && (
                      <span style={{ background: 'rgba(95, 143, 107, 0.12)', color: '#22c55e', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
                        Validated
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: '#8a95a7', marginTop: '4px' }}>
                    Severity: <strong>{(finding.severity || 'INFO').toUpperCase()}</strong> | Confidence:{' '}
                    {typeof finding.confidence === 'number' ? `${(finding.confidence as number) * 100}%` : finding.confidence ?? '\u2014'}
                  </div>
                  {finding.source_tool && (
                    <div style={{ fontSize: '11px', color: '#7b8798', marginTop: '4px' }}>
                      Source: {finding.source_tool}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Right Sidebar: Activity & Status */}
      <div className="activity-panel" style={{ borderLeft: '1px solid #355E3B' }}>
        <h3 style={{ marginBottom: '16px' }}>Statistics</h3>

        <div style={{ fontSize: '14px', marginBottom: '12px' }}>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#8a95a7' }}>Active Workflows:</span>
            <strong style={{ marginLeft: '4px' }}>{workflows.length}</strong>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#8a95a7' }}>Findings:</span>
            <strong style={{ marginLeft: '4px' }}>{findings.length}</strong>
          </div>
          <div>
            <span style={{ color: '#8a95a7' }}>Active Agents:</span>
            <strong style={{ marginLeft: '4px' }}>
              {agents.filter((a) => a.status !== 'idle').length}/{agents.length}
            </strong>
          </div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>Cost Tracking</h4>
        <div style={{ fontSize: '12px' }}>
          <div>Session Cost: ${llmStats?.stats?.total_cost_usd?.toFixed(2) || '0.00'}</div>
          <div>Tokens: {llmStats?.stats?.total_tokens || 0}</div>
          <div style={{ marginTop: '8px', color: '#0066CC' }}>
            Avg Latency: {llmStats?.stats?.avg_latency_ms?.toFixed(0) || '0'}ms
          </div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>System Health</h4>
        {/* Q6: Live health indicators polled every 10s */}
        <div style={{ fontSize: '12px' }}>
          {[
            ['llm', 'LLM System'],
            ['mcp', 'MCP Servers'],
            ['a2a', 'A2A Bus'],
            ['orchestration', 'Orchestration'],
          ].map(([key, label]) => (
            <div key={key} style={{ marginBottom: '3px', color: systemHealth[key] ? '#22c55e' : '#ef4444' }}>
              {systemHealth[key] ? '\u2713' : '\u2717'} {label}
            </div>
          ))}
        </div>

        <hr style={{ margin: '12px 0' }} />

        <p style={{ fontSize: '12px', color: '#8a95a7', margin: 0 }}>
          K1 v7.0 | Gemini CLI Orchestration
        </p>
      </div>
    </div>
  )
}

export default UnifiedOrchestrationDashboard
