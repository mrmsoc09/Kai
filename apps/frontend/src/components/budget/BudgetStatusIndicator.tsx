/**
 * Budget Status Indicator
 * Small component to show budget status in navbar or sidebar
 */

import React, { useState, useEffect } from 'react';
import {
  Box,
  Chip,
  CircularProgress,
  Tooltip,
  Typography,
  Popover,
  Paper,
} from '@mui/material';
import {
  AttachMoney as MoneyIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
} from '@mui/icons-material';
import { getDailyBudget, type DailyBudget } from '../../api/budget';

interface BudgetStatusIndicatorProps {
  refreshInterval?: number; // milliseconds
}

export const BudgetStatusIndicator: React.FC<BudgetStatusIndicatorProps> = ({
  refreshInterval = 30000, // 30 seconds default
}) => {
  const [budget, setBudget] = useState<DailyBudget | null>(null);
  const [loading, setLoading] = useState(true);
  const [anchorEl, setAnchorEl] = useState<HTMLElement | null>(null);

  const loadBudget = async () => {
    try {
      const data = await getDailyBudget();
      setBudget({
        budget_cents: data.budget_cents ?? 0,
        spent_cents: data.spent_cents ?? 0,
        remaining_cents: data.remaining_cents ?? 0,
        utilization_percent: data.utilization_percent ?? 0,
        status: data.status ?? 'normal',
        transaction_count: data.transaction_count ?? 0,
        session_count: data.session_count ?? 0,
      });
    } catch (err) {
      console.error('Failed to load budget:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBudget();

    const interval = setInterval(loadBudget, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval]);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const open = Boolean(anchorEl);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'normal':
        return 'success';
      case 'warning':
        return 'warning';
      case 'critical':
      case 'exhausted':
        return 'error';
      default:
        return 'default';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'normal':
        return <MoneyIcon />;
      case 'warning':
        return <WarningIcon />;
      case 'critical':
      case 'exhausted':
        return <ErrorIcon />;
      default:
        return <MoneyIcon />;
    }
  };

  const formatCurrency = (cents: number) => {
    return `$${(cents / 100).toFixed(2)}`;
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', alignItems: 'center', px: 1 }}>
        <CircularProgress size={20} />
      </Box>
    );
  }

  if (!budget) {
    return null;
  }

  return (
    <>
      <Tooltip title="Click for budget details">
        <Chip
          icon={getStatusIcon(budget.status)}
          label={`${formatCurrency(budget.remaining_cents)} / ${formatCurrency(budget.budget_cents)}`}
          color={getStatusColor(budget.status) as any}
          size="small"
          onClick={handleClick}
          sx={{ cursor: 'pointer' }}
        />
      </Tooltip>

      <Popover
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={{
          vertical: 'bottom',
          horizontal: 'right',
        }}
        transformOrigin={{
          vertical: 'top',
          horizontal: 'right',
        }}
      >
        <Paper sx={{ p: 2, minWidth: 250 }}>
          <Typography variant="subtitle2" gutterBottom>
            Daily Budget Status
          </Typography>

          <Box sx={{ mt: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                Total Budget
              </Typography>
              <Typography variant="body2" fontWeight="bold">
                {formatCurrency(budget.budget_cents)}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                Spent
              </Typography>
              <Typography variant="body2" color={getStatusColor(budget.status)}>
                {formatCurrency(budget.spent_cents)}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                Remaining
              </Typography>
              <Typography variant="body2" fontWeight="bold" color="primary">
                {formatCurrency(budget.remaining_cents)}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                Utilization
              </Typography>
              <Typography variant="body2">
                {(budget.utilization_percent ?? 0).toFixed(1)}%
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
              <Typography variant="body2" color="textSecondary">
                Transactions
              </Typography>
              <Typography variant="body2">
                {budget.transaction_count}
              </Typography>
            </Box>

            <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
              <Typography variant="body2" color="textSecondary">
                Sessions
              </Typography>
              <Typography variant="body2">
                {budget.session_count}
              </Typography>
            </Box>
          </Box>

          <Box sx={{ mt: 2 }}>
            <Chip
              label={budget.status.toUpperCase()}
              color={getStatusColor(budget.status) as any}
              size="small"
              sx={{ width: '100%' }}
            />
          </Box>

          {budget.status === 'warning' && (
            <Typography variant="caption" color="warning.main" sx={{ mt: 1, display: 'block' }}>
              Budget at {(budget.utilization_percent ?? 0).toFixed(1)}% - consider using local models
            </Typography>
          )}

          {budget.status === 'critical' && (
            <Typography variant="caption" color="error.main" sx={{ mt: 1, display: 'block' }}>
              Budget critical! Paid APIs may be limited
            </Typography>
          )}

          {budget.status === 'exhausted' && (
            <Typography variant="caption" color="error.main" sx={{ mt: 1, display: 'block' }}>
              Budget exhausted - using local models only
            </Typography>
          )}
        </Paper>
      </Popover>
    </>
  );
};

export default BudgetStatusIndicator;
