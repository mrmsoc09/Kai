/**
 * Crew YAML Browser
 * Browse CrewAI and AutoGen2 crew definitions
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  Tabs,
  Tab,
  Typography,
  Chip,
  CircularProgress,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Grid,
} from '@mui/material'
import { agentsApi, CrewYAMLDefinition } from '../api/agents'

type TabValue = 'phase' | 'framework' | 'all'

const CrewYAMLBrowser: React.FC = () => {
  const [crews, setCrews] = useState<CrewYAMLDefinition[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tabValue, setTabValue] = useState<TabValue>('phase')
  const [selectedCrew, setSelectedCrew] = useState<CrewYAMLDefinition | null>(
    null
  )
  const [showYamlModal, setShowYamlModal] = useState(false)
  const [runningJob, setRunningJob] = useState<string | null>(null)

  useEffect(() => {
    const fetchCrews = async () => {
      try {
        setLoading(true)
        const res = await agentsApi.listCrewYAMLs()
        setCrews(res.data)
        setError(null)
      } catch (err) {
        setError('Failed to load crew definitions')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchCrews()
  }, [])

  const handleRunCrew = async (crew: CrewYAMLDefinition) => {
    try {
      setRunningJob(`Running ${crew.name}...`)
      const res = await agentsApi.runCrewYAML(crew.file_path)
      setRunningJob(null)
      setShowYamlModal(false)
      setSelectedCrew(null)
      alert(`Crew launched with job ID: ${res.data.job_id}`)
    } catch (err) {
      console.error(err)
      setRunningJob(null)
      alert('Failed to run crew')
    }
  }

  const crewsByPhase: Record<string, CrewYAMLDefinition[]> = {}
  const crewsByFramework: Record<string, CrewYAMLDefinition[]> = {}

  crews.forEach((crew) => {
    if (!crewsByPhase[crew.phase]) crewsByPhase[crew.phase] = []
    crewsByPhase[crew.phase].push(crew)

    if (!crewsByFramework[crew.framework])
      crewsByFramework[crew.framework] = []
    crewsByFramework[crew.framework].push(crew)
  })

  const renderCrewCards = (crewList: CrewYAMLDefinition[]) => (
    <Grid container spacing={2}>
      {crewList.map((crew) => (
        <Grid item xs={12} sm={6} md={4} key={crew.file_path}>
          <Card
            sx={{
              background: '#1a1a1a',
              border: '1px solid #333',
              cursor: 'pointer',
              transition: 'all 0.12s',
              '&:hover': { borderColor: '#555', background: '#222' },
            }}
            onClick={() => {
              setSelectedCrew(crew)
              setShowYamlModal(true)
            }}
          >
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
                <Typography
                  variant="h6"
                  sx={{ color: '#fff', fontWeight: 'bold' }}
                >
                  {crew.name}
                </Typography>
                {crew.is_primary && (
                  <Chip
                    label="Primary"
                    size="small"
                    sx={{
                      background: '#4caf50',
                      color: '#fff',
                    }}
                  />
                )}
              </Box>

              <Typography
                variant="body2"
                sx={{ color: '#aaa', marginBottom: 1 }}
              >
                Phase: <strong>{crew.phase}</strong>
              </Typography>

              <Typography
                variant="body2"
                sx={{ color: '#aaa', marginBottom: 1 }}
              >
                Topic: <strong>{crew.topic}</strong>
              </Typography>

              <Box sx={{ marginBottom: 1 }}>
                <Chip
                  label={crew.framework.toUpperCase()}
                  size="small"
                  sx={{
                    background:
                      crew.framework === 'crewai'
                        ? '#2196f3'
                        : crew.framework === 'autogen'
                        ? '#ff9800'
                        : '#9c27b0',
                    color: '#fff',
                  }}
                />
              </Box>

              <Typography
                variant="caption"
                sx={{ color: '#888' }}
              >
                {crew.roles.length} roles
              </Typography>

              <Typography
                variant="caption"
                sx={{ color: '#888', display: 'block', marginTop: 1 }}
              >
                {crew.roles.reduce((sum, r) => sum + r.task_count, 0)}{' '}
                total tasks
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      ))}
    </Grid>
  )

  return (
    <Box sx={{ padding: 3 }}>
      <Typography variant="h4" sx={{ marginBottom: 1, fontWeight: 'bold' }}>
        Crew Library
      </Typography>
      <Typography
        variant="body2"
        sx={{ marginBottom: 3, color: '#888' }}
      >
        CrewAI and AutoGen2 crew definitions ({crews.length} total)
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', padding: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          <Box
            sx={{
              borderBottom: '1px solid #333',
              marginBottom: 2,
            }}
          >
            <Tabs
              value={tabValue}
              onChange={(_, val) => setTabValue(val)}
              sx={{
                '& .MuiTab-root': { color: '#888' },
                '& .Mui-selected': { color: '#fff' },
              }}
            >
              <Tab label="By Phase" value="phase" />
              <Tab label="By Framework" value="framework" />
              <Tab label="All" value="all" />
            </Tabs>
          </Box>

          {tabValue === 'phase' && (
            <Box>
              {Object.entries(crewsByPhase)
                .sort()
                .map(([phase, crewList]) => (
                  <Box key={phase} sx={{ marginBottom: 4 }}>
                    <Typography
                      variant="h6"
                      sx={{
                        color: '#fff',
                        fontWeight: 'bold',
                        marginBottom: 2,
                      }}
                    >
                      Phase {phase}
                    </Typography>
                    {renderCrewCards(crewList)}
                  </Box>
                ))}
            </Box>
          )}

          {tabValue === 'framework' && (
            <Box>
              {Object.entries(crewsByFramework)
                .sort()
                .map(([framework, crewList]) => (
                  <Box key={framework} sx={{ marginBottom: 4 }}>
                    <Typography
                      variant="h6"
                      sx={{
                        color: '#fff',
                        fontWeight: 'bold',
                        marginBottom: 2,
                      }}
                    >
                      {framework.toUpperCase()}
                    </Typography>
                    {renderCrewCards(crewList)}
                  </Box>
                ))}
            </Box>
          )}

          {tabValue === 'all' && renderCrewCards(crews)}
        </>
      )}

      {/* YAML Display Modal */}
      <Dialog
        open={showYamlModal}
        onClose={() => setShowYamlModal(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle sx={{ background: '#1a1a1a', color: '#fff' }}>
          {selectedCrew?.name} — Crew Definition
        </DialogTitle>
        <DialogContent sx={{ background: '#0a0a0a', color: '#aaa' }}>
          {selectedCrew && (
            <Box sx={{ marginTop: 2 }}>
              <Typography variant="body2" sx={{ marginBottom: 1 }}>
                <strong>Framework:</strong> {selectedCrew.framework.toUpperCase()}
              </Typography>
              <Typography variant="body2" sx={{ marginBottom: 1 }}>
                <strong>Phase:</strong> {selectedCrew.phase}
              </Typography>
              <Typography variant="body2" sx={{ marginBottom: 2 }}>
                <strong>Topic:</strong> {selectedCrew.topic}
              </Typography>

              <Typography
                variant="subtitle2"
                sx={{ marginBottom: 1, color: '#fff' }}
              >
                Roles ({selectedCrew.roles.length}):
              </Typography>

              <Box
                sx={{
                  background: '#1a1a1a',
                  border: '1px solid #333',
                  borderRadius: 1,
                  padding: 2,
                  marginBottom: 2,
                  fontFamily: 'monospace',
                  fontSize: '0.85rem',
                }}
              >
                {selectedCrew.roles.map((role) => (
                  <Box key={role.key} sx={{ marginBottom: 2 }}>
                    <Typography
                      variant="body2"
                      sx={{
                        color: '#4caf50',
                        fontWeight: 'bold',
                        marginBottom: 0.5,
                      }}
                    >
                      {role.role}
                    </Typography>
                    <Typography variant="caption" sx={{ color: '#aaa' }}>
                      Goal: {role.goal}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{ color: '#aaa', display: 'block', marginTop: 0.5 }}
                    >
                      Tasks: {role.task_count}
                    </Typography>
                  </Box>
                ))}
              </Box>

              <Typography variant="caption" sx={{ color: '#888' }}>
                File: {selectedCrew.file_path}
              </Typography>
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ background: '#1a1a1a' }}>
          <Button
            onClick={() => setShowYamlModal(false)}
            sx={{ color: '#888' }}
          >
            Close
          </Button>
          {selectedCrew && (
            <Button
              onClick={() => handleRunCrew(selectedCrew)}
              variant="contained"
              disabled={runningJob !== null}
              sx={{
                background: '#4caf50',
                color: '#fff',
              }}
            >
              {runningJob ? runningJob : 'Run Crew'}
            </Button>
          )}
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default CrewYAMLBrowser
