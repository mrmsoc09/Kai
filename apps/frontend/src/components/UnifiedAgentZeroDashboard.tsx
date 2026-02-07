/**
 * Unified Agent Zero Dashboard Hub
 * K1 + Agent Zero Integration Frontend
 * Primary user communication interface
 *
 * Features:
 * - Real-time agent activity visualization
 * - Natural language command input
 * - Findings stream
 * - Workflow progress tracking
 * - Agent Zero integration status
 */

import React, { useState, useEffect, useRef } from 'react'
import { useAuth } from '../store/system'
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

export const UnifiedAgentZeroDashboard: React.FC = () => {
  // State
  const [command, setCommand] = useState('')
  const [agents, setAgents] = useState<Agent[]>([])
  const [findings, setFindings] = useState<Finding[]>([])
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [currentWorkflow, setCurrentWorkflow] = useState<Workflow | null>(null)
  const [agentZeroConnected, setAgentZeroConnected] = useState(false)
  const [isHunting, setIsHunting] = useState(false)
  const [target, setTarget] = useState('')
  const [llmStats, setLLMStats] = useState<any>(null)
  const [mcpServers, setMCPServers] = useState<any[]>([])

  const wsRef = useRef<WebSocket | null>(null)
  const token = useAuth().getState().token
  const API_URL = 'http://localhost:8000/api/v1'

  // Initialize dashboard
  useEffect(() => {
    const initializeDashboard = async () => {
      try {
        // Check Agent Zero connection
        const healthResponse = await axios.get(`${API_URL}/agent-zero/health`, {
          headers: { Authorization: `Bearer ${token}` }
        })

        setAgentZeroConnected(
          healthResponse.data.systems.agent_zero.status === 'operational'
        )

        // Get agent status
        const agentsResponse = await axios.get(`${API_URL}/agent-zero/agents`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        setAgents(agentsResponse.data.agents || [])

        // Get MCP servers
        const mcpResponse = await axios.get(`${API_URL}/agent-zero/mcp/registry`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        setMCPServers(mcpResponse.data.servers || [])

        // Get LLM stats
        const llmResponse = await axios.get(`${API_URL}/agent-zero/llm/providers`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        setLLMStats(llmResponse.data)

      } catch (error) {
        console.error('Failed to initialize dashboard:', error)
      }
    }

    initializeDashboard()

    // Setup WebSocket for real-time updates
    const wsUrl = 'ws://localhost:8000/api/v1/agent-zero/ws/agents'
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
  }, [token])

  // Handle natural language command
  const handleCommand = async () => {
    if (!command.trim()) return

    try {
      const response = await axios.post(
        `${API_URL}/agent-zero/commands/natural-language`,
        {
          query: command,
          context: { user_id: 'current_user', timestamp: new Date().toISOString() }
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )

      console.log('Command executed:', response.data)
      setCommand('')

      // Refresh workflows
      await refreshWorkflows()

    } catch (error) {
      console.error('Command execution failed:', error)
    }
  }

  // Start quick hunt
  const handleQuickHunt = async () => {
    if (!target.trim()) return

    try {
      setIsHunting(true)

      const response = await axios.post(
        `${API_URL}/agent-zero/workflows/hunt?target=${target}`,
        {},
        { headers: { Authorization: `Bearer ${token}` } }
      )

      const workflowId = response.data.workflow_id
      setCurrentWorkflow(response.data)

      // Connect to workflow WebSocket
      const wsUrl = `ws://localhost:8000/api/v1/agent-zero/ws/workflows/${workflowId}`
      const ws = new WebSocket(wsUrl)

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data)

        if (data.type === 'status_update') {
          console.log('Workflow status:', data)
        } else if (data.type === 'finding_discovered') {
          setFindings((prev) => [...prev, data.finding])
        }
      }

      // Auto-refresh workflow status
      const interval = setInterval(async () => {
        try {
          const statusResponse = await axios.get(
            `${API_URL}/agent-zero/workflows/${workflowId}`,
            { headers: { Authorization: `Bearer ${token}` } }
          )

          setCurrentWorkflow(statusResponse.data)

          if (statusResponse.data.status === 'complete') {
            clearInterval(interval)
            setIsHunting(false)
          }

        } catch (error) {
          console.error('Failed to fetch workflow status:', error)
        }
      }, 2000)

    } catch (error) {
      console.error('Hunt workflow creation failed:', error)
      setIsHunting(false)
    }
  }

  // Refresh workflows
  const refreshWorkflows = async () => {
    try {
      const response = await axios.get(`${API_URL}/agent-zero/workflows`, {
        headers: { Authorization: `Bearer ${token}` }
      })

      setWorkflows(response.data.workflows || [])

    } catch (error) {
      console.error('Failed to fetch workflows:', error)
    }
  }

  // Render agent status indicator
  const renderAgentLane = (agent: Agent) => {
    const statusColor: Record<string, string> = {
      idle: '#gray',
      working: '#green',
      waiting: '#yellow',
      error: '#red'
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
          <span className="agent-status" style={{ fontSize: '12px', color: '#666' }}>
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
          backgroundColor: '#f5f5f5',
          borderRadius: '4px',
          marginBottom: '12px'
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontWeight: 600 }}>{workflow.target}</span>
          <span style={{ fontSize: '12px', color: '#666' }}>
            {completedSteps}/{workflow.steps.length} steps
          </span>
        </div>

        <div
          className="progress-bar"
          style={{
            width: '100%',
            height: '6px',
            backgroundColor: '#e0e0e0',
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
                ✓ {s.name}
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
        backgroundColor: '#fff',
        minHeight: '100vh'
      }}
    >
      {/* Left Sidebar: Agent Status */}
      <div className="agent-panel" style={{ borderRight: '1px solid #e0e0e0' }}>
        <h3 style={{ marginBottom: '16px' }}>Active Agents</h3>

        <div
          className="connection-status"
          style={{
            padding: '8px',
            backgroundColor: agentZeroConnected ? '#e8f5e9' : '#ffebee',
            borderRadius: '4px',
            marginBottom: '16px',
            fontSize: '12px'
          }}
        >
          Agent Zero: {agentZeroConnected ? '🟢 Connected' : '🔴 Offline'}
        </div>

        <div className="agents-list">
          {agents.length > 0 ? (
            agents.map((agent) => renderAgentLane(agent))
          ) : (
            <p style={{ color: '#999', fontSize: '12px' }}>No agents active</p>
          )}
        </div>

        <hr style={{ margin: '16px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>MCP Servers</h4>
        <div className="mcp-status">
          {mcpServers.map((server) => (
            <div key={server.server_id} style={{ fontSize: '12px', marginBottom: '8px' }}>
              <span style={{ color: server.status === 'online' ? '#4caf50' : '#999' }}>●</span>
              {' '}
              {server.name} ({server.tools?.length || 0} tools)
            </div>
          ))}
        </div>

        <hr style={{ margin: '16px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>LLM Status</h4>
        <div className="llm-status" style={{ fontSize: '12px' }}>
          <div>Primary: {llmStats?.primary || 'N/A'}</div>
          <div style={{ marginTop: '4px', color: '#666' }}>
            Cost (session): ${llmStats?.stats?.total_cost_usd?.toFixed(2) || '0.00'}
          </div>
        </div>
      </div>

      {/* Center: Command & Results */}
      <div className="main-content">
        {/* Quick Hunt Section */}
        <div
          className="quick-hunt-section"
          style={{
            padding: '16px',
            backgroundColor: '#f9f9f9',
            borderRadius: '8px',
            marginBottom: '24px'
          }}
        >
          <h2 style={{ marginBottom: '16px' }}>🚀 Quick Vulnerability Hunt</h2>

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
                border: '1px solid #ddd',
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
                backgroundColor: isHunting ? '#ccc' : '#0066CC',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: isHunting ? 'not-allowed' : 'pointer',
                fontWeight: 600
              }}
            >
              {isHunting ? 'Hunting...' : 'Start Hunt'}
            </button>
          </div>

          <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>
            Agents will automatically discover vulnerabilities, validate findings, analyze chains, and generate reports.
          </p>
        </div>

        {/* Natural Language Commands */}
        <div
          className="command-section"
          style={{
            padding: '16px',
            backgroundColor: '#f9f9f9',
            borderRadius: '8px',
            marginBottom: '24px'
          }}
        >
          <h3 style={{ marginBottom: '12px' }}>💬 Natural Language Commands</h3>

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
                border: '1px solid #ddd',
                borderRadius: '4px'
              }}
            />
            <button
              onClick={handleCommand}
              disabled={!command.trim()}
              style={{
                padding: '8px 16px',
                backgroundColor: command.trim() ? '#0066CC' : '#ccc',
                color: 'white',
                border: 'none',
                borderRadius: '4px',
                cursor: command.trim() ? 'pointer' : 'not-allowed'
              }}
            >
              Send
            </button>
          </div>

          <div style={{ fontSize: '12px', color: '#666' }}>
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
              backgroundColor: '#f9f9f9',
              borderRadius: '8px',
              marginBottom: '24px'
            }}
          >
            <h3 style={{ marginBottom: '12px' }}>🔄 Current Workflow</h3>
            {renderWorkflowProgress(currentWorkflow)}
          </div>
        )}

        {/* Findings Stream */}
        {findings.length > 0 && (
          <div
            className="findings-section"
            style={{
              padding: '16px',
              backgroundColor: '#f9f9f9',
              borderRadius: '8px'
            }}
          >
            <h3 style={{ marginBottom: '12px' }}>🎯 Discovered Vulnerabilities</h3>

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
                    backgroundColor: 'white',
                    borderLeft: `4px solid ${color}`,
                    marginBottom: '8px',
                    borderRadius: '2px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ fontWeight: 600 }}>{finding.title}</div>
                    {finding.validated && (
                      <span style={{ background: '#e8f5e9', color: '#2e7d32', padding: '2px 6px', borderRadius: 4, fontSize: 11 }}>
                        Validated
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                    Severity: <strong>{(finding.severity || 'INFO').toUpperCase()}</strong> | Confidence:{' '}
                    {typeof finding.confidence === 'number' ? `${(finding.confidence as number) * 100}%` : finding.confidence ?? '—'}
                  </div>
                  {finding.source_tool && (
                    <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
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
      <div className="activity-panel" style={{ borderLeft: '1px solid #e0e0e0' }}>
        <h3 style={{ marginBottom: '16px' }}>📊 Statistics</h3>

        <div style={{ fontSize: '14px', marginBottom: '12px' }}>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#666' }}>Active Workflows:</span>
            <strong style={{ marginLeft: '4px' }}>{workflows.length}</strong>
          </div>
          <div style={{ marginBottom: '8px' }}>
            <span style={{ color: '#666' }}>Findings:</span>
            <strong style={{ marginLeft: '4px' }}>{findings.length}</strong>
          </div>
          <div>
            <span style={{ color: '#666' }}>Active Agents:</span>
            <strong style={{ marginLeft: '4px' }}>
              {agents.filter((a) => a.status !== 'idle').length}/{agents.length}
            </strong>
          </div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>💰 Cost Tracking</h4>
        <div style={{ fontSize: '12px' }}>
          <div>Session Cost: ${llmStats?.stats?.total_cost_usd?.toFixed(2) || '0.00'}</div>
          <div>Tokens: {llmStats?.stats?.total_tokens || 0}</div>
          <div style={{ marginTop: '8px', color: '#0066CC' }}>
            Avg Latency: {llmStats?.stats?.avg_latency_ms?.toFixed(0) || '0'}ms
          </div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <h4 style={{ marginBottom: '12px' }}>🔧 System Health</h4>
        <div style={{ fontSize: '12px' }}>
          <div>✓ LLM System</div>
          <div>✓ MCP Servers</div>
          <div>✓ A2A Bus</div>
          <div>{agentZeroConnected && '✓ Agent Zero'}</div>
        </div>

        <hr style={{ margin: '12px 0' }} />

        <p style={{ fontSize: '12px', color: '#666', margin: 0 }}>
          K1 v7.0 | Powered by Agent Zero
        </p>
      </div>
    </div>
  )
}

export default UnifiedAgentZeroDashboard
