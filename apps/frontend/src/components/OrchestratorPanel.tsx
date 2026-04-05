/**
 * Orchestrator Panel
 * Displays API budget, quota status, and operational metrics for midnight orchestrator
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  LinearProgress,
  Typography,
  Alert,
  Grid,
} from '@mui/material'
import { orchestratorApi, QuotaStatus, OrchestratorStatus } from '../api/orchestrator'

const getQuotaColor = (remaining: number, daily_limit: number) => {
  const percent = (remaining / daily_limit) * 100
  if (percent > 50) return '#4caf50' // green
  if (percent > 20) return '#ff9800' // orange
  return '#f44336' // red
}

const QuotaMeter: React.FC<{ quota: QuotaStatus }> = ({ quota }) => {
  const percent = ((quota.used / quota.daily_limit) * 100).toFixed(1)
  const color = getQuotaColor(quota.remaining, quota.daily_limit)

  return (
    <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
      <CardContent>
        <Box sx={{ marginBottom: 2 }}>
          <Typography variant="subtitle2" sx={{ fontWeight: 'bold' }}>
            {quota.source}
          </Typography>
          <Typography variant="caption" sx={{ color: '#888' }}>
            {quota.env_var}
          </Typography>
        </Box>

        <LinearProgress
          variant="determinate"
          value={parseFloat(percent)}
          sx={{
            height: 8,
            borderRadius: 4,
            background: '#333',
            marginBottom: 1,
            '& .MuiLinearProgress-bar': {
              background: color,
            },
          }}
        />

        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            marginTop: 1,
          }}
        >
          <Typography variant="caption" sx={{ color: '#aaa' }}>
            {quota.used}/{quota.daily_limit} calls
          </Typography>
          <Typography
            variant="caption"
            sx={{
              color: color,
              fontWeight: 'bold',
            }}
          >
            {quota.remaining} remaining
          </Typography>
        </Box>

        {quota.signal_score && (
          <Typography
            variant="caption"
            sx={{
              color: '#666',
              display: 'block',
              marginTop: 1,
            }}
          >
            Signal: {quota.signal_score.toFixed(2)} findings/call
          </Typography>
        )}

        <Typography
          variant="caption"
          sx={{
            color: '#666',
            display: 'block',
            marginTop: 0.5,
          }}
        >
          Reset: {quota.reset_time}
        </Typography>
      </CardContent>
    </Card>
  )
}

const OrchestratorPanel: React.FC = () => {
  const [status, setStatus] = useState<OrchestratorStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        setLoading(true)
        const response = await orchestratorApi.getStatus()
        setStatus(response.data)
      } catch (err) {
        setError('Failed to load orchestrator status')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchStatus()
    const interval = setInterval(fetchStatus, 60000)
    return () => clearInterval(interval)
  }, [])

  return (
    <Box sx={{ padding: 3 }}>
      <Typography
        variant="h4"
        sx={{ marginBottom: 1, fontWeight: 'bold' }}
      >
        API Budget & Orchestrator
      </Typography>

      {status && (
        <Typography
          variant="body2"
          sx={{ color: '#888', marginBottom: 3 }}
        >
          Last run: {status.last_run} • Next run: {status.next_run}
        </Typography>
      )}

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
      ) : status ? (
        <Box>
          {/* Budget Status Section */}
          <Box sx={{ marginBottom: 4 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 'bold',
                marginBottom: 2,
                color: '#ccc',
              }}
            >
              API Budget Allocation
            </Typography>

            <Grid container spacing={2}>
              {status.sources.map((quota) => (
                <Grid item xs={12} sm={6} md={4} key={quota.source}>
                  <QuotaMeter quota={quota} />
                </Grid>
              ))}
            </Grid>
          </Box>

          {/* Scan Allocation */}
          <Box sx={{ marginBottom: 4 }}>
            <Typography
              variant="h6"
              sx={{
                fontWeight: 'bold',
                marginBottom: 2,
                color: '#ccc',
              }}
            >
              Scan Allocation
            </Typography>

            <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
              <CardContent>
                <Typography
                  variant="body1"
                  sx={{ color: '#fff', marginBottom: 1 }}
                >
                  <strong>{status.scans_planned}</strong> scans planned
                  today
                </Typography>
                <Typography
                  variant="body2"
                  sx={{ color: '#888' }}
                >
                  Target allocation optimized by signal score
                </Typography>
              </CardContent>
            </Card>
          </Box>

          {/* SpiderFoot Modules */}
          {status.spiderfoot_modules.length > 0 && (
            <Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: 'bold',
                  marginBottom: 2,
                  color: '#ccc',
                }}
              >
                Active SpiderFoot Modules
              </Typography>

              <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
                <CardContent>
                  <Box
                    sx={{
                      display: 'flex',
                      flexWrap: 'wrap',
                      gap: 1,
                    }}
                  >
                    {status.spiderfoot_modules.map((module) => (
                      <Box
                        key={module}
                        sx={{
                          background: '#333',
                          padding: '4px 8px',
                          borderRadius: 1,
                          fontSize: '0.85rem',
                          color: '#aaa',
                        }}
                      >
                        {module}
                      </Box>
                    ))}
                  </Box>
                </CardContent>
              </Card>
            </Box>
          )}
        </Box>
      ) : null}
    </Box>
  )
}

export default OrchestratorPanel
