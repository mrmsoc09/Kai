/**
 * Crew Agent Monitor
 * Displays 7 crew agents organized by phase group with dependency visualization
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Typography,
  Alert,
  Chip,
} from '@mui/material'
import { agentsApi, CrewAgent } from '../api/agents'

const PHASE_GROUPS = [
  {
    label: 'Phase A — Discovery (Parallel)',
    agents: ['SurfaceMapper', 'OSINTIntelligenceAgent', 'DarkWebIntelAgent', 'SecretScannerAgent'],
  },
  {
    label: 'Phase B — Content Mapping',
    agents: ['ContentDiscoveryAgent'],
  },
  {
    label: 'Phase C — Scanning (Parallel)',
    agents: ['VulnerabilityAgent', 'APISecurityAgent'],
  },
  {
    label: 'Phase D — Aggregation & Report',
    agents: ['FaradayCoordinatorAgent', 'EvidenceAnalyst', 'ReportSynthesisAgent', 'HandoffLiaison'],
  },
]

const getStatusColor = (status: string) => {
  switch (status) {
    case 'idle':
      return '#666'
    case 'running':
      return '#2196f3'
    case 'complete':
      return '#4caf50'
    case 'error':
      return '#f44336'
    default:
      return '#999'
  }
}

const CrewAgentNode: React.FC<{ agent: CrewAgent }> = ({
  agent,
}) => {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card
      sx={{
        background: '#1a1a1a',
        border: `2px solid ${getStatusColor(agent.status)}`,
        cursor: 'pointer',
        transition: 'all 0.2s',
        minWidth: 200,
        '&:hover': {
          background: '#222',
        },
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            marginBottom: 1,
          }}
        >
          <Box
            sx={{
              width: 12,
              height: 12,
              borderRadius: '50%',
              background: getStatusColor(agent.status),
            }}
          />
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 'bold', color: '#fff' }}
          >
            {agent.name}
          </Typography>
        </Box>

        <Typography
          variant="caption"
          sx={{ color: '#aaa', display: 'block', marginBottom: 1 }}
        >
          Status: <strong>{agent.status}</strong>
        </Typography>

        <Typography
          variant="caption"
          sx={{ color: '#aaa', display: 'block', marginBottom: 1 }}
        >
          Findings: <strong>{agent.findings_collected}</strong>
        </Typography>

        {agent.current_tool && (
          <Typography
            variant="caption"
            sx={{ color: '#888', display: 'block', marginBottom: 1 }}
          >
            Running: <strong>{agent.current_tool}</strong>
          </Typography>
        )}

        {expanded && (
          <Box sx={{ marginTop: 2, paddingTop: 2, borderTop: '1px solid #333' }}>
            <Typography
              variant="caption"
              sx={{ color: '#aaa', display: 'block', marginBottom: 1 }}
            >
              <strong>Tools:</strong>
            </Typography>
            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
              {agent.tool_agents.map((tool) => (
                <Chip
                  key={tool}
                  label={tool}
                  size="small"
                  sx={{
                    background: '#333',
                    color: '#aaa',
                    fontSize: '0.65rem',
                  }}
                />
              ))}
            </Box>
            {agent.errors.length > 0 && (
              <Box sx={{ marginTop: 1 }}>
                <Typography
                  variant="caption"
                  sx={{ color: '#f44336', display: 'block' }}
                >
                  <strong>Errors ({agent.errors.length}):</strong>
                </Typography>
                {agent.errors.map((err, idx) => (
                  <Typography
                    key={idx}
                    variant="caption"
                    sx={{ color: '#f44336', display: 'block' }}
                  >
                    • {err}
                  </Typography>
                ))}
              </Box>
            )}
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

const CrewAgentMonitor: React.FC = () => {
  const [agents, setAgents] = useState<CrewAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setLoading(true)
        const response = await agentsApi.listCrewAgents()
        setAgents(response.data)
      } catch (err) {
        setError('Failed to load crew agents')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
    const interval = setInterval(fetchAgents, 15000)
    return () => clearInterval(interval)
  }, [])

  return (
    <Box sx={{ padding: 3 }}>
      <Typography
        variant="h4"
        sx={{ marginBottom: 2, fontWeight: 'bold' }}
      >
        Crew Agent Orchestration (7 agents)
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      {loading ? (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            padding: 4,
          }}
        >
          <CircularProgress />
        </Box>
      ) : (
        <Box>
          {PHASE_GROUPS.map((group, idx) => (
            <Box key={idx} sx={{ marginBottom: 4 }}>
              <Typography
                variant="subtitle1"
                sx={{
                  fontWeight: 'bold',
                  color: '#888',
                  marginBottom: 2,
                  fontSize: '0.9rem',
                }}
              >
                {group.label}
              </Typography>

              <Box
                sx={{
                  display: 'flex',
                  gap: 2,
                  flexWrap: 'wrap',
                  alignItems: 'flex-start',
                }}
              >
                {group.agents.map((agentName) => {
                  const agent = agents.find((a) => a.name === agentName)
                  return agent ? (
                    <CrewAgentNode key={agentName} agent={agent} />
                  ) : (
                    <Box
                      key={agentName}
                      sx={{
                        background: '#1a1a1a',
                        border: '1px dashed #333',
                        padding: 2,
                        minWidth: 200,
                        color: '#666',
                        fontSize: '0.9rem',
                      }}
                    >
                      {agentName} (not deployed)
                    </Box>
                  )
                })}
              </Box>

              {idx < PHASE_GROUPS.length - 1 && (
                <Box
                  sx={{
                    margin: '20px 0',
                    textAlign: 'center',
                    color: '#555',
                    fontSize: '1.5rem',
                  }}
                >
                  ↓
                </Box>
              )}
            </Box>
          ))}
        </Box>
      )}
    </Box>
  )
}

export default CrewAgentMonitor
