/**
 * Master Findings View
 * Displays deduplicated master findings from FaradayCoordinatorAgent
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Chip,
  TextField,
  Button,
  Tabs,
  Tab,
  Typography,
  Alert,
  Collapse,
  IconButton,
} from '@mui/material'
import {
  ExpandMore as ExpandMoreIcon,
  FileDownload as FileDownloadIcon,
} from '@mui/icons-material'
import { masterFindingsApi, MasterFinding } from '../api/findings'

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#f44336',
  high: '#ff9800',
  medium: '#ffc107',
  low: '#4caf50',
  info: '#2196f3',
}

interface FindingCardProps {
  finding: MasterFinding
}

const FindingCard: React.FC<FindingCardProps> = ({ finding }) => {
  const [expanded, setExpanded] = useState(false)
  const isMultiConfirmed = finding.confirmed_by.length > 1

  return (
    <Card
      sx={{
        background: isMultiConfirmed ? 'rgba(255, 193, 7, 0.05)' : '#1a1a1a',
        border: isMultiConfirmed
          ? '2px solid #ffc107'
          : '1px solid #333',
        marginBottom: 2,
      }}
    >
      <CardContent>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'start',
          }}
        >
          <Box sx={{ flex: 1 }}>
            <Box
              sx={{
                display: 'flex',
                gap: 1,
                alignItems: 'center',
                marginBottom: 1,
              }}
            >
              <Chip
                label={finding.severity}
                size="small"
                sx={{
                  background: SEVERITY_COLORS[finding.severity],
                  color: '#fff',
                }}
              />
              {isMultiConfirmed && (
                <Chip
                  label={`Confirmed by ${finding.confirmed_by.length}`}
                  size="small"
                  sx={{
                    background: '#ffc107',
                    color: '#000',
                    fontWeight: 'bold',
                  }}
                />
              )}
            </Box>

            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 'bold',
                color: '#fff',
                marginBottom: 0.5,
              }}
            >
              {finding.type}
            </Typography>

            <Typography
              variant="body2"
              sx={{
                color: '#aaa',
                marginBottom: 1,
                wordBreak: 'break-all',
                fontFamily: 'monospace',
                fontSize: '0.85rem',
              }}
            >
              {finding.value}
            </Typography>

            <Box
              sx={{
                display: 'flex',
                gap: 2,
                fontSize: '0.85rem',
              }}
            >
              <Typography variant="caption" sx={{ color: '#888' }}>
                <strong>Target:</strong> {finding.target}
              </Typography>
              <Typography variant="caption" sx={{ color: '#888' }}>
                <strong>Confidence:</strong>{' '}
                {(finding.confidence * 100).toFixed(0)}%
              </Typography>
              <Typography variant="caption" sx={{ color: '#888' }}>
                <strong>From:</strong> {finding.source_tool}
              </Typography>
            </Box>
          </Box>

          <IconButton
            size="small"
            onClick={() => setExpanded(!expanded)}
            sx={{
              transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
              transition: 'transform 0.2s',
            }}
          >
            <ExpandMoreIcon />
          </IconButton>
        </Box>

        <Collapse in={expanded} timeout="auto">
          <Box sx={{ marginTop: 2, paddingTop: 2, borderTop: '1px solid #333' }}>
            <Box sx={{ marginBottom: 2 }}>
              <Typography
                variant="caption"
                sx={{
                  display: 'block',
                  color: '#888',
                  marginBottom: 1,
                }}
              >
                <strong>Confirmed by:</strong>
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                {finding.confirmed_by.map((tool) => (
                  <Chip
                    key={tool}
                    label={tool}
                    size="small"
                    sx={{
                      background: '#333',
                      color: '#aaa',
                    }}
                  />
                ))}
              </Box>
            </Box>

            {finding.recommended_next_tools.length > 0 && (
              <Box sx={{ marginBottom: 2 }}>
                <Typography
                  variant="caption"
                  sx={{
                    display: 'block',
                    color: '#888',
                    marginBottom: 1,
                  }}
                >
                  <strong>Next tools to run:</strong>
                </Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                  {finding.recommended_next_tools.map((tool) => (
                    <Chip
                      key={tool}
                      label={tool}
                      size="small"
                      sx={{
                        background: '#2196f3',
                        color: '#fff',
                      }}
                    />
                  ))}
                </Box>
              </Box>
            )}

            {finding.raw_evidence && (
              <Box>
                <Typography
                  variant="caption"
                  sx={{
                    display: 'block',
                    color: '#888',
                    marginBottom: 0.5,
                  }}
                >
                  <strong>Evidence:</strong>
                </Typography>
                <Typography
                  variant="caption"
                  sx={{
                    display: 'block',
                    background: '#0a0a0a',
                    padding: 1,
                    borderRadius: 1,
                    color: '#666',
                    fontFamily: 'monospace',
                    overflow: 'auto',
                    maxHeight: 200,
                  }}
                >
                  {finding.raw_evidence}
                </Typography>
              </Box>
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  )
}

const MasterFindingsView: React.FC = () => {
  const [findings, setFindings] = useState<MasterFinding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [scanId, setScanId] = useState('default-scan')
  const [severityFilter, setSeverityFilter] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  useEffect(() => {
    const fetchFindings = async () => {
      try {
        setLoading(true)
        const response = await masterFindingsApi.getMasterFindings(scanId)
        setFindings(response.data)
      } catch (err) {
        setError('Failed to load master findings')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchFindings()
  }, [scanId])

  const handleExport = async (format: 'json' | 'csv' | 'pdf') => {
    try {
      await masterFindingsApi.exportFindings(scanId, format)
    } catch (err) {
      console.error('Export failed:', err)
    }
  }

  const filteredFindings = findings.filter((f) => {
    if (severityFilter && f.severity !== severityFilter) return false
    if (
      searchTerm &&
      !f.value.toLowerCase().includes(searchTerm.toLowerCase())
    ) {
      return false
    }
    return true
  })

  const findingsBySeverity = {
    critical: findings.filter((f) => f.severity === 'critical').length,
    high: findings.filter((f) => f.severity === 'high').length,
    medium: findings.filter((f) => f.severity === 'medium').length,
    low: findings.filter((f) => f.severity === 'low').length,
    info: findings.filter((f) => f.severity === 'info').length,
  }

  return (
    <Box sx={{ padding: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'start',
          marginBottom: 3,
        }}
      >
        <Box>
          <Typography
            variant="h4"
            sx={{ marginBottom: 1, fontWeight: 'bold' }}
          >
            Master Findings ({findings.length})
          </Typography>
          <Typography variant="body2" sx={{ color: '#888' }}>
            Deduplicated findings from Faraday aggregation
          </Typography>
        </Box>

        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            size="small"
            startIcon={<FileDownloadIcon />}
            onClick={() => handleExport('json')}
            sx={{ color: '#2196f3' }}
          >
            JSON
          </Button>
          <Button
            size="small"
            startIcon={<FileDownloadIcon />}
            onClick={() => handleExport('csv')}
            sx={{ color: '#2196f3' }}
          >
            CSV
          </Button>
          <Button
            size="small"
            startIcon={<FileDownloadIcon />}
            onClick={() => handleExport('pdf')}
            sx={{ color: '#2196f3' }}
          >
            PDF
          </Button>
        </Box>
      </Box>

      {error && <Alert severity="error">{error}</Alert>}

      {/* Filter Section */}
      <Box sx={{ marginBottom: 3 }}>
        <Box sx={{ marginBottom: 2 }}>
          <Tabs
            value={severityFilter || 'all'}
            onChange={(_, value) =>
              setSeverityFilter(value === 'all' ? null : value)
            }
          >
            <Tab label={`All (${findings.length})`} value="all" />
            <Tab
              label={`Critical (${findingsBySeverity.critical})`}
              value="critical"
            />
            <Tab
              label={`High (${findingsBySeverity.high})`}
              value="high"
            />
            <Tab
              label={`Medium (${findingsBySeverity.medium})`}
              value="medium"
            />
            <Tab label={`Low (${findingsBySeverity.low})`} value="low" />
          </Tabs>
        </Box>

        <TextField
          placeholder="Search findings..."
          size="small"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          sx={{
            width: '100%',
            maxWidth: 400,
            '& .MuiOutlinedInput-root': {
              background: '#1a1a1a',
              color: '#fff',
            },
          }}
        />
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
        <Box>
          {filteredFindings.length > 0 ? (
            filteredFindings.map((finding, idx) => (
              <FindingCard key={idx} finding={finding} />
            ))
          ) : (
            <Typography
              variant="body2"
              sx={{ color: '#888', textAlign: 'center', padding: 4 }}
            >
              No findings match your filters
            </Typography>
          )}
        </Box>
      )}
    </Box>
  )
}

export default MasterFindingsView
