/**
 * Tool Agent Dashboard
 * Displays all 51 tool agents with status, phase, and execution metrics
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Chip,
  Grid,
  Tabs,
  Tab,
  Typography,
  Alert,
} from '@mui/material'
import { agentsApi, ToolAgent } from '../api/agents'

const PHASES = [
  { id: 0, label: 'All', range: [0, 10] },
  { id: 1, label: 'Phase 1', range: [1, 1] },
  { id: 2, label: 'Phase 2', range: [2, 2] },
  { id: 3, label: 'Phase 3', range: [3, 3] },
  { id: 4, label: 'Phase 4', range: [4, 4] },
  { id: 5, label: 'Phase 5', range: [5, 5] },
  { id: 6, label: 'Phase 6', range: [6, 6] },
  { id: 7, label: 'Phase 7', range: [7, 7] },
  { id: 8, label: 'Phase 8', range: [8, 8] },
  { id: 9, label: 'Phase 9', range: [9, 9] },
]

const getSafetyColor = (
  classification: string
) => {
  switch (classification) {
    case 'passive':
      return '#4caf50' // green
    case 'active':
      return '#ff9800' // orange
    case 'intrusive':
      return '#f44336' // red
    default:
      return '#999'
  }
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'running':
      return '#2196f3' // blue
    case 'complete':
      return '#4caf50' // green
    case 'error':
      return '#f44336' // red
    default:
      return '#999'
  }
}

const AgentCard: React.FC<{ agent: ToolAgent }> = ({
  agent,
}) => {
  const [expanded, setExpanded] = useState(false)

  return (
    <Card
      sx={{
        background: '#1a1a1a',
        border: '1px solid #333',
        cursor: 'pointer',
        transition: 'all 0.2s',
        '&:hover': {
          borderColor: '#555',
          background: '#222',
        },
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'start',
            marginBottom: 1,
          }}
        >
          <Typography
            variant="subtitle1"
            sx={{ fontWeight: 'bold', color: '#fff' }}
          >
            {agent.display_name || agent.name}
          </Typography>
          <Chip
            label={agent.safety_classification}
            size="small"
            sx={{
              background: getSafetyColor(
                agent.safety_classification
              ),
              color: '#fff',
              fontSize: '0.75rem',
            }}
          />
        </Box>

        <Box sx={{ marginBottom: 1 }}>
          <Typography
            variant="caption"
            sx={{ color: '#aaa' }}
          >
            Phase {agent.phase}
          </Typography>
          {agent.last_execution && (
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                marginTop: 0.5,
              }}
            >
              <Box
                sx={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: getStatusColor(
                    agent.last_execution.status
                  ),
                }}
              />
              <Typography
                variant="caption"
                sx={{ color: '#aaa' }}
              >
                {agent.last_execution.status} •{' '}
                {agent.last_execution.finding_count} findings
              </Typography>
            </Box>
          )}
        </Box>

        {agent.memory && (
          <Typography
            variant="caption"
            sx={{ color: '#666', display: 'block' }}
          >
            Memory: {agent.memory.confirmed_findings_count}{' '}
            confirmed, {agent.memory.scan_count} scans
          </Typography>
        )}

        {expanded && (
          <Box sx={{ marginTop: 2, paddingTop: 2, borderTop: '1px solid #333' }}>
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                color: '#aaa',
                marginBottom: 1,
              }}
            >
              <strong>Category:</strong> {agent.category}
            </Typography>
            <Typography
              variant="caption"
              sx={{
                display: 'block',
                color: '#aaa',
              }}
            >
              <strong>Timeout:</strong> {agent.timeout_seconds}s
            </Typography>
          </Box>
        )}
      </CardContent>
    </Card>
  )
}

const ToolAgentDashboard: React.FC = () => {
  const [agents, setAgents] = useState<ToolAgent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPhase, setSelectedPhase] = useState(0)

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        setLoading(true)
        const response = await agentsApi.listAgents()
        setAgents(response.data)
      } catch (err) {
        setError('Failed to load tool agents')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchAgents()
    const interval = setInterval(fetchAgents, 30000)
    return () => clearInterval(interval)
  }, [])

  const filteredAgents =
    selectedPhase === 0
      ? agents
      : agents.filter((a) => a.phase === selectedPhase)

  const agentsByPhase = PHASES.map((phase) => ({
    ...phase,
    count: agents.filter((a) => a.phase === phase.id).length,
  }))

  return (
    <Box sx={{ padding: 3 }}>
      <Typography
        variant="h4"
        sx={{ marginBottom: 2, fontWeight: 'bold' }}
      >
        Tool Agents ({agents.length})
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      <Box sx={{ marginBottom: 3 }}>
        <Tabs
          value={selectedPhase}
          onChange={(_, value) => setSelectedPhase(value)}
          sx={{ marginBottom: 2 }}
        >
          {agentsByPhase.map((phase) => (
            <Tab
              key={phase.id}
              label={`${phase.label} (${phase.count})`}
              value={phase.id}
            />
          ))}
        </Tabs>
      </Box>

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
        <Grid container spacing={2}>
          {filteredAgents.map((agent) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={agent.name}>
              <AgentCard agent={agent} />
            </Grid>
          ))}
        </Grid>
      )}
    </Box>
  )
}

export default ToolAgentDashboard
