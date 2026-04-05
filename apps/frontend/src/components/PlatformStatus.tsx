/**
 * Platform Status Dashboard
 * Health check for all platform components
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  Typography,
  CircularProgress,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
} from '@mui/material'
import { orchestratorApi, PlatformHealth } from '../api/orchestrator'

const PlatformStatus: React.FC = () => {
  const [health, setHealth] = useState<PlatformHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedService, setSelectedService] = useState<
    (typeof health)['services'][0] | null
  >(null)
  const [detailOpen, setDetailOpen] = useState(false)

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        setLoading(true)
        const res = await orchestratorApi.getPlatformHealth()
        setHealth(res.data)
        setError(null)
      } catch (err) {
        setError('Failed to fetch platform health')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchHealth()
    const interval = setInterval(fetchHealth, 30000)
    return () => clearInterval(interval)
  }, [])

  const statusColor = (status: string): string => {
    switch (status) {
      case 'up':
        return '#4caf50'
      case 'degraded':
        return '#ff9800'
      case 'down':
        return '#f44336'
      default:
        return '#888'
    }
  }

  const statusIcon = (status: string): string => {
    switch (status) {
      case 'up':
        return '✓'
      case 'degraded':
        return '⚠'
      case 'down':
        return '✗'
      default:
        return '?'
    }
  }

  const getReadinessColor = (overall: string): string => {
    switch (overall) {
      case 'healthy':
        return '#4caf50'
      case 'degraded':
        return '#ff9800'
      case 'critical':
        return '#f44336'
      default:
        return '#666'
    }
  }

  if (loading) {
    return (
      <Box sx={{ padding: 3, display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    )
  }

  if (error || !health) {
    return (
      <Box sx={{ padding: 3 }}>
        <Alert severity="error">
          {error || 'Failed to load platform status'}
        </Alert>
      </Box>
    )
  }

  const groupedServices: Record<string, typeof health.services> = {
    'BACKEND SERVICES': [],
    'TOOL AGENTS': [],
    'ORCHESTRATION': [],
    'INTEGRATIONS': [],
  }

  health.services.forEach((service) => {
    if (
      service.name.includes('FastAPI') ||
      service.name.includes('PostgreSQL') ||
      service.name.includes('Redis') ||
      service.name.includes('Celery') ||
      service.name.includes('Vault')
    ) {
      groupedServices['BACKEND SERVICES'].push(service)
    } else if (
      service.name.includes('agents') ||
      service.name.includes('binaries') ||
      service.name.includes('memory')
    ) {
      groupedServices['TOOL AGENTS'].push(service)
    } else if (
      service.name.includes('orchestrator') ||
      service.name.includes('API keys') ||
      service.name.includes('Crew')
    ) {
      groupedServices['ORCHESTRATION'].push(service)
    } else {
      groupedServices['INTEGRATIONS'].push(service)
    }
  })

  return (
    <Box sx={{ padding: 3 }}>
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 3,
        }}
      >
        <Box>
          <Typography variant="h4" sx={{ fontWeight: 'bold', marginBottom: 1 }}>
            Platform Status
          </Typography>
          <Typography variant="body2" sx={{ color: '#888' }}>
            Last updated:{' '}
            {new Date().toLocaleTimeString()} (auto-refresh every 30s)
          </Typography>
        </Box>

        {/* Ready to Hunt Indicator */}
        <Card
          sx={{
            background: '#1a1a1a',
            border: `2px solid ${
              health.ready_to_hunt ? '#4caf50' : '#ff9800'
            }`,
            minWidth: 200,
          }}
        >
          <CardContent
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
            }}
          >
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: getReadinessColor(health.overall),
                boxShadow: `0 0 10px ${getReadinessColor(health.overall)}`,
              }}
            />
            <Box>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Ready to Hunt
              </Typography>
              <Typography
                variant="subtitle2"
                sx={{
                  color: '#fff',
                  fontWeight: 'bold',
                }}
              >
                {health.ready_to_hunt ? 'YES' : 'NO'}
              </Typography>
            </Box>
          </CardContent>
        </Card>
      </Box>

      {/* Status Grid */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        {Object.entries(groupedServices).map(([groupName, services]) =>
          services.length > 0 ? (
            <Box key={groupName}>
              <Typography
                variant="subtitle1"
                sx={{
                  fontWeight: 'bold',
                  marginBottom: 1,
                  color: '#ccc',
                  fontSize: '0.9rem',
                  letterSpacing: '0.1em',
                }}
              >
                {groupName}
              </Typography>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {services.map((service) => (
                  <Card
                    key={service.name}
                    sx={{
                      background: '#1a1a1a',
                      border: '1px solid #333',
                      cursor: 'pointer',
                      transition: 'all 0.12s',
                      '&:hover': {
                        borderColor: '#555',
                        background: '#222',
                      },
                    }}
                    onClick={() => {
                      setSelectedService(service)
                      setDetailOpen(true)
                    }}
                  >
                    <CardContent
                      sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '12px 16px',
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 24,
                            height: 24,
                            borderRadius: '50%',
                            background: statusColor(service.status),
                            color: '#fff',
                            fontWeight: 'bold',
                            fontSize: '0.9rem',
                          }}
                        >
                          {statusIcon(service.status)}
                        </Box>
                        <Box>
                          <Typography
                            variant="body2"
                            sx={{
                              color: '#aaa',
                              fontWeight: 'bold',
                            }}
                          >
                            {service.name}
                          </Typography>
                          <Typography
                            variant="caption"
                            sx={{ color: '#888' }}
                          >
                            {service.detail}
                          </Typography>
                        </Box>
                      </Box>

                      <Typography
                        variant="caption"
                        sx={{
                          color: '#888',
                          textAlign: 'right',
                        }}
                      >
                        {new Date(
                          service.last_checked
                        ).toLocaleTimeString()}
                      </Typography>
                    </CardContent>
                  </Card>
                ))}
              </Box>
            </Box>
          ) : null
        )}
      </Box>

      {/* Detail Modal */}
      <Dialog
        open={detailOpen}
        onClose={() => setDetailOpen(false)}
        maxWidth="sm"
        fullWidth
      >
        <DialogTitle sx={{ background: '#1a1a1a', color: '#fff' }}>
          {selectedService?.name} — Details
        </DialogTitle>
        <DialogContent sx={{ background: '#0a0a0a', color: '#aaa' }}>
          {selectedService && (
            <Box sx={{ marginTop: 2 }}>
              <Box sx={{ marginBottom: 2 }}>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  STATUS
                </Typography>
                <Typography
                  variant="body1"
                  sx={{
                    color: statusColor(selectedService.status),
                    fontWeight: 'bold',
                  }}
                >
                  {selectedService.status.toUpperCase()}
                </Typography>
              </Box>

              <Box sx={{ marginBottom: 2 }}>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  DETAIL
                </Typography>
                <Typography variant="body2" sx={{ color: '#aaa' }}>
                  {selectedService.detail}
                </Typography>
              </Box>

              <Box sx={{ marginBottom: 2 }}>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  LAST CHECKED
                </Typography>
                <Typography variant="body2" sx={{ color: '#aaa' }}>
                  {new Date(
                    selectedService.last_checked
                  ).toLocaleString()}
                </Typography>
              </Box>

              {selectedService.status === 'down' && (
                <Alert severity="error">
                  This service is down. Mission execution may be blocked.
                </Alert>
              )}

              {selectedService.status === 'degraded' && (
                <Alert severity="warning">
                  This service is degraded. Some operations may be slower.
                </Alert>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ background: '#1a1a1a' }}>
          <Button
            onClick={() => setDetailOpen(false)}
            sx={{ color: '#888' }}
          >
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  )
}

export default PlatformStatus
