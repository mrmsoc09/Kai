/**
 * Tool Registry Browser
 * Browse all 51 registered tool agents with filtering
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Chip,
  CircularProgress,
  Button,
  MenuItem,
  Select,
  TextField,
  Grid,
  Alert,
} from '@mui/material'
import { agentsApi, ToolRegistryEntry } from '../api/agents'

type SafetyType = 'all' | 'passive' | 'active' | 'intrusive'
type PhaseFilter = 'all' | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9

const CATEGORIES = ['all', 'recon', 'scanning', 'osint', 'exploitation', 'aggregation']

const ToolRegistryBrowser: React.FC = () => {
  const [tools, setTools] = useState<ToolRegistryEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [safetyFilter, setSafetyFilter] = useState<SafetyType>('all')
  const [phaseFilter, setPhaseFilter] = useState<PhaseFilter>('all')
  const [categoryFilter, setCategoryFilter] = useState('all')
  const [searchTerm, setSearchTerm] = useState('')

  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set())

  useEffect(() => {
    const fetchTools = async () => {
      try {
        setLoading(true)
        const res = await agentsApi.getToolRegistry()
        setTools(res.data)
        setError(null)
      } catch (err) {
        setError('Failed to load tool registry')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchTools()
  }, [])

  const filteredTools = tools.filter((tool) => {
    const matchesSafety =
      safetyFilter === 'all' || tool.safety_classification === safetyFilter
    const matchesPhase =
      phaseFilter === 'all' || tool.phase === phaseFilter
    const matchesCategory =
      categoryFilter === 'all' || tool.category === categoryFilter
    const matchesSearch =
      searchTerm === '' ||
      tool.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tool.display_name.toLowerCase().includes(searchTerm.toLowerCase())

    return (
      matchesSafety && matchesPhase && matchesCategory && matchesSearch
    )
  })

  const safetyStats = {
    passive: tools.filter((t) => t.safety_classification === 'passive').length,
    active: tools.filter((t) => t.safety_classification === 'active').length,
    intrusive: tools.filter((t) => t.safety_classification === 'intrusive')
      .length,
  }

  const safetyColor = (classification: string): string => {
    switch (classification) {
      case 'passive':
        return '#4caf50'
      case 'active':
        return '#ff9800'
      case 'intrusive':
        return '#f44336'
      default:
        return '#666'
    }
  }

  const toggleExpanded = (toolName: string) => {
    const newExpanded = new Set(expandedRows)
    if (newExpanded.has(toolName)) {
      newExpanded.delete(toolName)
    } else {
      newExpanded.add(toolName)
    }
    setExpandedRows(newExpanded)
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Typography variant="h4" sx={{ marginBottom: 1, fontWeight: 'bold' }}>
        Tool Registry
      </Typography>
      <Typography
        variant="body2"
        sx={{ marginBottom: 3, color: '#888' }}
      >
        {tools.length} tools registered | {safetyStats.passive} passive |{' '}
        {safetyStats.active} active | {safetyStats.intrusive} intrusive | Phases
        1-9 covered
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      {/* Filter Bar */}
      <Card
        sx={{
          background: '#1a1a1a',
          border: '1px solid #333',
          marginBottom: 3,
        }}
      >
        <CardContent>
          <Grid container spacing={2}>
            <Grid item xs={12} sm={6} md={2}>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Safety
              </Typography>
              <Select
                value={safetyFilter}
                onChange={(e) =>
                  setSafetyFilter(e.target.value as SafetyType)
                }
                sx={{
                  width: '100%',
                  background: '#0a0a0a',
                  color: '#aaa',
                  '.MuiOutlinedInput-notchedOutline': {
                    borderColor: '#333',
                  },
                }}
              >
                <MenuItem value="all">All</MenuItem>
                <MenuItem value="passive">Passive</MenuItem>
                <MenuItem value="active">Active</MenuItem>
                <MenuItem value="intrusive">Intrusive</MenuItem>
              </Select>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Phase
              </Typography>
              <Select
                value={phaseFilter}
                onChange={(e) =>
                  setPhaseFilter(
                    e.target.value === 'all'
                      ? 'all'
                      : (Number(e.target.value) as 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9)
                  )
                }
                sx={{
                  width: '100%',
                  background: '#0a0a0a',
                  color: '#aaa',
                  '.MuiOutlinedInput-notchedOutline': {
                    borderColor: '#333',
                  },
                }}
              >
                <MenuItem value="all">All</MenuItem>
                {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((p) => (
                  <MenuItem key={p} value={p}>
                    {p}
                  </MenuItem>
                ))}
              </Select>
            </Grid>

            <Grid item xs={12} sm={6} md={2}>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Category
              </Typography>
              <Select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                sx={{
                  width: '100%',
                  background: '#0a0a0a',
                  color: '#aaa',
                  '.MuiOutlinedInput-notchedOutline': {
                    borderColor: '#333',
                  },
                }}
              >
                {CATEGORIES.map((cat) => (
                  <MenuItem key={cat} value={cat}>
                    {cat === 'all' ? 'All' : cat}
                  </MenuItem>
                ))}
              </Select>
            </Grid>

            <Grid item xs={12} md={6}>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Search
              </Typography>
              <TextField
                placeholder="Search by name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                sx={{
                  width: '100%',
                  '& .MuiOutlinedInput-root': {
                    background: '#0a0a0a',
                    color: '#aaa',
                  },
                }}
              />
            </Grid>
          </Grid>
        </CardContent>
      </Card>

      {/* Tools Table */}
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', padding: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer
          sx={{
            background: '#1a1a1a',
            border: '1px solid #333',
            borderRadius: 1,
          }}
        >
          <Table>
            <TableHead>
              <TableRow sx={{ background: '#0a0a0a' }}>
                <TableCell sx={{ color: '#888' }}></TableCell>
                <TableCell sx={{ color: '#888' }}>Tool Name</TableCell>
                <TableCell sx={{ color: '#888' }}>Phase</TableCell>
                <TableCell sx={{ color: '#888' }}>Safety</TableCell>
                <TableCell sx={{ color: '#888' }}>Category</TableCell>
                <TableCell sx={{ color: '#888' }}>Timeout</TableCell>
                <TableCell sx={{ color: '#888' }}>API Key</TableCell>
                <TableCell sx={{ color: '#888' }}>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredTools.map((tool) => (
                <React.Fragment key={tool.name}>
                  <TableRow
                    sx={{
                      '&:hover': { background: '#222' },
                      cursor: 'pointer',
                    }}
                    onClick={() => toggleExpanded(tool.name)}
                  >
                    <TableCell sx={{ color: '#aaa' }}>
                      {expandedRows.has(tool.name) ? '▼' : '▶'}
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.display_name}
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.phase}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={tool.safety_classification.toUpperCase()}
                        size="small"
                        sx={{
                          background: safetyColor(
                            tool.safety_classification
                          ),
                          color: '#fff',
                        }}
                      />
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.category}
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.timeout_seconds}s
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.api_keys_required ? '✓' : '—'}
                    </TableCell>
                    <TableCell sx={{ color: '#aaa' }}>
                      {tool.enabled ? '🟢' : '🔴'}
                    </TableCell>
                  </TableRow>

                  {expandedRows.has(tool.name) && (
                    <TableRow sx={{ background: '#0a0a0a' }}>
                      <TableCell colSpan={8} sx={{ paddingY: 2 }}>
                        <Box sx={{ paddingLeft: 2 }}>
                          <Typography
                            variant="body2"
                            sx={{
                              color: '#aaa',
                              marginBottom: 1,
                            }}
                          >
                            {tool.description}
                          </Typography>

                          <Box
                            sx={{
                              display: 'grid',
                              gridTemplateColumns: 'repeat(3, 1fr)',
                              gap: 2,
                              marginTop: 1,
                            }}
                          >
                            <Box>
                              <Typography
                                variant="caption"
                                sx={{ color: '#888' }}
                              >
                                Knowledge Files
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{ color: '#aaa' }}
                              >
                                {tool.knowledge_files?.length || 0}
                              </Typography>
                            </Box>

                            <Box>
                              <Typography
                                variant="caption"
                                sx={{ color: '#888' }}
                              >
                                Memory Files
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{ color: '#aaa' }}
                              >
                                {tool.memory_files?.length || 0}
                              </Typography>
                            </Box>

                            <Box>
                              <Typography
                                variant="caption"
                                sx={{ color: '#888' }}
                              >
                                Requires Auth
                              </Typography>
                              <Typography
                                variant="body2"
                                sx={{ color: '#aaa' }}
                              >
                                {tool.requires_auth ? 'Yes' : 'No'}
                              </Typography>
                            </Box>
                          </Box>

                          <Button
                            variant="outlined"
                            size="small"
                            sx={{
                              marginTop: 1,
                              borderColor: '#555',
                              color: '#aaa',
                            }}
                          >
                            Details
                          </Button>
                        </Box>
                      </TableCell>
                    </TableRow>
                  )}
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  )
}

export default ToolRegistryBrowser
