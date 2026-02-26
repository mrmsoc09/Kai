/**
 * Budget Dashboard Component
 * Displays comprehensive budget tracking and cost analytics
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Chip,
  Alert,
  AlertTitle,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  IconButton,
  Tooltip,
} from '@mui/material';
import {
  Refresh as RefreshIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  CheckCircle as CheckCircleIcon,
  TrendingUp as TrendingUpIcon,
} from '@mui/icons-material';
import {
  getDailyBudget,
  getBudgetAnalytics,
  getBudgetHealth,
  type DailyBudget,
  type BudgetAnalytics,
} from '../../api/budget';

interface BudgetDashboardProps {
  sessionId?: string;
}

export const BudgetDashboard: React.FC<BudgetDashboardProps> = ({ sessionId }) => {
  const [dailyBudget, setDailyBudget] = useState<DailyBudget | null>(null);
  const [analytics, setAnalytics] = useState<BudgetAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const loadData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [daily, analyticsData] = await Promise.all([
        getDailyBudget(),
        getBudgetAnalytics(),
      ]);

      setDailyBudget(daily);
      setAnalytics(analyticsData);
      setLastRefresh(new Date());
    } catch (err: any) {
      setError(err.message || 'Failed to load budget data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Auto-refresh every 30 seconds
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [sessionId]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'normal':
        return 'success';
      case 'warning':
        return 'warning';
      case 'critical':
        return 'error';
      case 'exhausted':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'normal':
        return <CheckCircleIcon />;
      case 'warning':
        return <WarningIcon />;
      case 'critical':
      case 'exhausted':
        return <ErrorIcon />;
      default:
        return null;
    }
  };

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  if (loading && !dailyBudget) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h5" gutterBottom>
          Budget Dashboard
        </Typography>
        <LinearProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Box sx={{ p: 3 }}>
        <Alert severity="error">
          <AlertTitle>Error Loading Budget Data</AlertTitle>
          {error}
        </Alert>
      </Box>
    );
  }

  return (
    <Box sx={{ p: 3 }}>
      {/* Header */}
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4" component="h1">
          Budget Dashboard
        </Typography>
        <Tooltip title="Refresh">
          <IconButton onClick={loadData} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Budget Status Alert */}
      {dailyBudget && (dailyBudget.status === 'warning' || dailyBudget.status === 'critical' || dailyBudget.status === 'exhausted') && (
        <Alert severity={getStatusColor(dailyBudget.status) as any} sx={{ mb: 3 }}>
          <AlertTitle>Budget {dailyBudget.status.toUpperCase()}</AlertTitle>
          Daily budget at {dailyBudget.utilization_percent.toFixed(1)}% utilization.
          {dailyBudget.status === 'exhausted' && ' All paid API calls will be blocked. Local models will be used.'}
          {dailyBudget.status === 'critical' && ' Consider using local models or waiting for daily reset.'}
        </Alert>
      )}

      {/* Daily Budget Overview */}
      {dailyBudget && (
        <Grid container spacing={3} sx={{ mb: 3 }}>
          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Daily Budget
                </Typography>
                <Typography variant="h4">
                  {formatCurrency(dailyBudget.budget_cents)}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {dailyBudget.date}
                </Typography>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Spent Today
                </Typography>
                <Typography variant="h4" color={getStatusColor(dailyBudget.status)}>
                  {formatCurrency(dailyBudget.spent_cents)}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', mt: 1 }}>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(dailyBudget.utilization_percent, 100)}
                    color={getStatusColor(dailyBudget.status) as any}
                    sx={{ flexGrow: 1, mr: 1 }}
                  />
                  <Typography variant="caption">
                    {dailyBudget.utilization_percent.toFixed(1)}%
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Remaining
                </Typography>
                <Typography variant="h4" color="primary">
                  {formatCurrency(dailyBudget.remaining_cents)}
                </Typography>
                <Chip
                  label={dailyBudget.status.toUpperCase()}
                  color={getStatusColor(dailyBudget.status) as any}
                  size="small"
                  icon={getStatusIcon(dailyBudget.status)}
                  sx={{ mt: 1 }}
                />
              </CardContent>
            </Card>
          </Grid>

          <Grid item xs={12} md={3}>
            <Card>
              <CardContent>
                <Typography color="textSecondary" gutterBottom>
                  Transactions
                </Typography>
                <Typography variant="h4">
                  {dailyBudget.transaction_count}
                </Typography>
                <Typography variant="caption" color="textSecondary">
                  {dailyBudget.session_count} sessions
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Spending Breakdown */}
      {analytics && (
        <Grid container spacing={3}>
          {/* Model Spending */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Spending by Model
                </Typography>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Model</TableCell>
                        <TableCell align="right">Cost</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(analytics.spending.by_model).map(([model, cost]) => (
                        <TableRow key={model}>
                          <TableCell>
                            {model}
                            {cost === '$0.00' && (
                              <Chip label="LOCAL" size="small" color="success" sx={{ ml: 1 }} />
                            )}
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight={cost !== '$0.00' ? 'bold' : 'normal'}>
                              {cost}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              </CardContent>
            </Card>
          </Grid>

          {/* Session Summary */}
          <Grid item xs={12} md={6}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Session Summary
                </Typography>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography color="textSecondary">Total Sessions</Typography>
                    <Typography variant="h6">{analytics.sessions.total_sessions}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography color="textSecondary">Active Sessions</Typography>
                    <Typography variant="h6">{analytics.sessions.active_sessions}</Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography color="textSecondary">Default Budget</Typography>
                    <Typography variant="h6">
                      {formatCurrency(analytics.sessions.default_budget_cents)}
                    </Typography>
                  </Box>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography color="textSecondary">Over Budget</Typography>
                    <Typography variant="h6" color={analytics.sessions.sessions_over_budget > 0 ? 'error' : 'success'}>
                      {analytics.sessions.sessions_over_budget}
                    </Typography>
                  </Box>
                </Box>
              </CardContent>
            </Card>
          </Grid>

          {/* All-Time Stats */}
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom sx={{ display: 'flex', alignItems: 'center' }}>
                  <TrendingUpIcon sx={{ mr: 1 }} />
                  All-Time Statistics
                </Typography>
                <Grid container spacing={3}>
                  <Grid item xs={12} sm={4}>
                    <Typography color="textSecondary" gutterBottom>
                      Total Spent
                    </Typography>
                    <Typography variant="h5">
                      {formatCurrency(analytics.spending.total_spent_all_time_cents)}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography color="textSecondary" gutterBottom>
                      Total Transactions
                    </Typography>
                    <Typography variant="h5">
                      {analytics.spending.total_transactions}
                    </Typography>
                  </Grid>
                  <Grid item xs={12} sm={4}>
                    <Typography color="textSecondary" gutterBottom>
                      Average Cost
                    </Typography>
                    <Typography variant="h5">
                      {formatCurrency(analytics.spending.avg_cost_per_transaction_cents)}
                    </Typography>
                    <Typography variant="caption" color="textSecondary">
                      per transaction
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}

      {/* Last Refresh */}
      <Box sx={{ mt: 2, textAlign: 'center' }}>
        <Typography variant="caption" color="textSecondary">
          Last updated: {lastRefresh.toLocaleTimeString()}
        </Typography>
      </Box>
    </Box>
  );
};

export default BudgetDashboard;
