/**
 * LLM Provider Dashboard
 * Tracks provider usage, costs, and fallover chain
 */

import React, { useState, useEffect } from 'react'
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  Alert,
  Chip,
} from '@mui/material'
import { orchestratorApi, LLMProvider, LLMUsage } from '../api/orchestrator'

const PROVIDER_COLORS: Record<string, string> = {
  Anthropic: '#4f46e5',
  OpenAI: '#10b981',
  Gemini: '#f59e0b',
  Ollama: '#8b5cf6',
}

const ProviderStatusIndicator: React.FC<{
  provider: LLMProvider
}> = ({ provider }) => {
  const statusColors: Record<string, string> = {
    active: '#4caf50',
    degraded: '#ff9800',
    unavailable: '#f44336',
  }

  return (
    <Card sx={{ background: '#1a1a1a', border: '1px solid #333', marginBottom: 2 }}>
      <CardContent>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Box
              sx={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                background: statusColors[provider.status],
              }}
            />
            <Typography variant="subtitle2" sx={{ fontWeight: 'bold', color: '#fff' }}>
              {provider.name}
            </Typography>
            <Chip
              label={provider.status.toUpperCase()}
              size="small"
              sx={{
                background: statusColors[provider.status],
                color: '#fff',
              }}
            />
            <Chip
              label={`Priority ${provider.priority}`}
              size="small"
              variant="outlined"
              sx={{ borderColor: '#555', color: '#aaa' }}
            />
          </Box>
        </Box>

        {provider.daily_budget_usd && (
          <Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', marginBottom: 1 }}>
              <Typography variant="caption" sx={{ color: '#888' }}>
                Daily Budget
              </Typography>
              <Typography variant="caption" sx={{ color: '#aaa' }}>
                ${provider.spent_today_usd?.toFixed(2) || '0.00'} / ${provider.daily_budget_usd.toFixed(2)}
              </Typography>
            </Box>
            <LinearProgress
              variant="determinate"
              value={((provider.spent_today_usd || 0) / provider.daily_budget_usd) * 100}
              sx={{
                height: 6,
                borderRadius: 3,
                background: '#333',
                '& .MuiLinearProgress-bar': {
                  background:
                    ((provider.spent_today_usd || 0) / provider.daily_budget_usd) * 100 > 80
                      ? '#f44336'
                      : '#4caf50',
                },
              }}
            />
          </Box>
        )}

        <Box sx={{ marginTop: 2 }}>
          <Typography variant="caption" sx={{ color: '#888', display: 'block', marginBottom: 1 }}>
            Models:
          </Typography>
          <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
            {provider.models.map((model) => (
              <Chip
                key={model}
                label={model}
                size="small"
                sx={{
                  background: '#333',
                  color: '#aaa',
                }}
              />
            ))}
          </Box>
        </Box>
      </CardContent>
    </Card>
  )
}

const LLMProviderDashboard: React.FC = () => {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [usage, setUsage] = useState<LLMUsage[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const [providersRes, usageRes] = await Promise.all([
          orchestratorApi.getProviders(),
          orchestratorApi.getLLMUsage(),
        ])
        setProviders(providersRes.data)
        setUsage(usageRes.data)
      } catch (err) {
        setError('Failed to load provider data')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 60000)
    return () => clearInterval(interval)
  }, [])

  const totalCostToday = usage.reduce((sum, u) => sum + u.estimated_cost_usd, 0)
  const totalRequests = usage.reduce((sum, u) => sum + u.request_count, 0)
  const totalErrors = usage.reduce((sum, u) => sum + u.error_count, 0)

  return (
    <Box sx={{ padding: 3 }}>
      <Typography variant="h4" sx={{ marginBottom: 3, fontWeight: 'bold' }}>
        LLM Provider Dashboard
      </Typography>

      {error && <Alert severity="error">{error}</Alert>}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', padding: 4 }}>
          <CircularProgress />
        </Box>
      ) : (
        <>
          {/* Cost Summary */}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
              gap: 2,
              marginBottom: 4,
            }}
          >
            <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
              <CardContent>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  Today
                </Typography>
                <Typography variant="h5" sx={{ color: '#4caf50', fontWeight: 'bold' }}>
                  ${totalCostToday.toFixed(2)}
                </Typography>
              </CardContent>
            </Card>
            <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
              <CardContent>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  Total Requests
                </Typography>
                <Typography variant="h5" sx={{ color: '#2196f3', fontWeight: 'bold' }}>
                  {totalRequests}
                </Typography>
              </CardContent>
            </Card>
            <Card sx={{ background: '#1a1a1a', border: '1px solid #333' }}>
              <CardContent>
                <Typography variant="caption" sx={{ color: '#888' }}>
                  Errors
                </Typography>
                <Typography variant="h5" sx={{ color: totalErrors > 0 ? '#f44336' : '#4caf50', fontWeight: 'bold' }}>
                  {totalErrors}
                </Typography>
              </CardContent>
            </Card>
          </Box>

          {/* Fallover Chain */}
          <Box sx={{ marginBottom: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold', marginBottom: 2, color: '#ccc' }}>
              Fallover Chain
            </Typography>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                padding: 2,
                background: '#1a1a1a',
                border: '1px solid #333',
                borderRadius: 1,
              }}
            >
              {providers
                .sort((a, b) => a.priority - b.priority)
                .map((provider, idx) => (
                  <React.Fragment key={provider.name}>
                    <Chip
                      label={provider.name}
                      sx={{
                        background:
                          provider.status === 'active'
                            ? PROVIDER_COLORS[provider.name] || '#666'
                            : '#666',
                        color: '#fff',
                      }}
                    />
                    {idx < providers.length - 1 && (
                      <Typography sx={{ color: '#555' }}>→</Typography>
                    )}
                  </React.Fragment>
                ))}
            </Box>
          </Box>

          {/* Provider Status */}
          <Box sx={{ marginBottom: 4 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold', marginBottom: 2, color: '#ccc' }}>
              Provider Status
            </Typography>
            {providers
              .sort((a, b) => a.priority - b.priority)
              .map((provider) => (
                <ProviderStatusIndicator key={provider.name} provider={provider} />
              ))}
          </Box>

          {/* Usage Table */}
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 'bold', marginBottom: 2, color: '#ccc' }}>
              Usage Details
            </Typography>
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
                    <TableCell sx={{ color: '#888' }}>Provider</TableCell>
                    <TableCell sx={{ color: '#888' }}>Model</TableCell>
                    <TableCell sx={{ color: '#888' }} align="right">
                      Requests
                    </TableCell>
                    <TableCell sx={{ color: '#888' }} align="right">
                      Tokens
                    </TableCell>
                    <TableCell sx={{ color: '#888' }} align="right">
                      Cost
                    </TableCell>
                    <TableCell sx={{ color: '#888' }} align="right">
                      Latency (ms)
                    </TableCell>
                    <TableCell sx={{ color: '#888' }} align="right">
                      Errors
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {usage.map((u, idx) => (
                    <TableRow key={idx} sx={{ '&:hover': { background: '#222' } }}>
                      <TableCell sx={{ color: '#aaa' }}>{u.provider}</TableCell>
                      <TableCell sx={{ color: '#aaa' }}>{u.model}</TableCell>
                      <TableCell sx={{ color: '#aaa' }} align="right">
                        {u.request_count}
                      </TableCell>
                      <TableCell sx={{ color: '#aaa' }} align="right">
                        {u.total_tokens.toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ color: '#4caf50', fontWeight: 'bold' }} align="right">
                        ${u.estimated_cost_usd.toFixed(4)}
                      </TableCell>
                      <TableCell sx={{ color: '#aaa' }} align="right">
                        {u.avg_latency_ms.toFixed(0)}
                      </TableCell>
                      <TableCell
                        sx={{
                          color: u.error_count > 0 ? '#f44336' : '#4caf50',
                          fontWeight: 'bold',
                        }}
                        align="right"
                      >
                        {u.error_count}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        </>
      )}
    </Box>
  )
}

export default LLMProviderDashboard
