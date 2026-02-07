/**
 * Budget Management API Client
 * Provides functions to interact with budget tracking endpoints
 */

import { apiClient } from './client';

export interface SessionBudget {
  session_id: string;
  budget_cents: number;
  spent_cents: number;
  remaining_cents: number;
  utilization_percent: number;
  status: 'normal' | 'warning' | 'critical' | 'exhausted';
  transaction_count: number;
  created_at: string;
}

export interface DailyBudget {
  date: string;
  budget_cents: number;
  spent_cents: number;
  remaining_cents: number;
  utilization_percent: number;
  status: 'normal' | 'warning' | 'critical' | 'exhausted';
  transaction_count: number;
  session_count: number;
}

export interface BudgetAnalytics {
  daily: {
    date: string;
    budget_cents: number;
    spent_cents: number;
    remaining_cents: number;
    utilization_percent: number;
    status: string;
    transaction_count: number;
    session_count: number;
  };
  sessions: {
    total_sessions: number;
    active_sessions: number;
    default_budget_cents: number;
    sessions_over_budget: number;
  };
  spending: {
    total_spent_all_time_cents: number;
    total_transactions: number;
    by_model: Record<string, string>;
    avg_cost_per_transaction_cents: number;
  };
}

export interface BudgetAlert {
  timestamp: string;
  alert_type: string;
  message: string;
  utilization_percent: number;
  current_spent_cents: number;
  budget_limit_cents: number;
}

export interface CostForecast {
  session_id: string;
  current_spent_cents: number;
  current_remaining_cents: number;
  total_estimated_cents: number;
  budget_after_tasks_cents: number;
  tasks_breakdown: Array<{
    task_id: string;
    task_name: string;
    estimated_cost_cents: number;
    complexity: number;
  }>;
  budget_sufficient: boolean;
  recommendations: string[];
}

export interface RoutingAnalytics {
  budget: BudgetAnalytics;
  routing: {
    local_complexity_threshold: number;
    paid_complexity_threshold: number;
    default_strategy: string;
    available_local_models: number;
    available_paid_models: number;
  };
}

/**
 * Get session budget details
 */
export const getSessionBudget = async (sessionId: string): Promise<SessionBudget> => {
  const response = await apiClient.get(`/api/v1/budget/session/${sessionId}`);
  return response.data;
};

/**
 * Get daily budget aggregate
 */
export const getDailyBudget = async (): Promise<DailyBudget> => {
  const response = await apiClient.get('/api/v1/budget/daily');
  return response.data;
};

/**
 * Request emergency budget increase
 */
export const requestBudgetIncrease = async (
  sessionId: string,
  amountCents: number,
  justification: string,
  userId: string
): Promise<{
  success: boolean;
  message: string;
  new_budget_cents: number;
  approved_by: string;
}> => {
  const response = await apiClient.post(`/api/v1/budget/session/${sessionId}/increase`, {
    amount_cents: amountCents,
    justification,
    user_id: userId,
  });
  return response.data;
};

/**
 * Get comprehensive budget analytics
 */
export const getBudgetAnalytics = async (): Promise<BudgetAnalytics> => {
  const response = await apiClient.get('/api/v1/budget/analytics');
  return response.data;
};

/**
 * Get cost summary for session or daily
 */
export const getCostSummary = async (
  sessionId: string,
  timeframe: 'session' | 'daily' = 'session'
): Promise<any> => {
  const response = await apiClient.get(`/api/v1/budget/cost-summary/${sessionId}`, {
    params: { timeframe },
  });
  return response.data;
};

/**
 * Get routing analytics
 */
export const getRoutingAnalytics = async (
  sessionId?: string
): Promise<RoutingAnalytics> => {
  const params = sessionId ? { session_id: sessionId } : {};
  const response = await apiClient.get('/api/v1/budget/routing-analytics', { params });
  return response.data;
};

/**
 * Forecast cost for pending tasks
 */
export const forecastCost = async (
  sessionId: string,
  pendingTasks: Array<{
    task_id: string;
    name: string;
    description: string;
    complexity_estimate: number;
    estimated_tokens_input?: number;
    estimated_tokens_output?: number;
  }>
): Promise<CostForecast> => {
  const response = await apiClient.post('/api/v1/budget/forecast', {
    session_id: sessionId,
    pending_tasks: pendingTasks,
  });
  return response.data;
};

/**
 * Get budget alerts for session
 */
export const getBudgetAlerts = async (sessionId: string): Promise<{
  session_id: string;
  alert_count: number;
  alerts: BudgetAlert[];
}> => {
  const response = await apiClient.get(`/api/v1/budget/alerts/${sessionId}`);
  return response.data;
};

/**
 * Manually reset daily budget
 */
export const resetDailyBudget = async (): Promise<{
  success: boolean;
  message: string;
  reset_at: string;
}> => {
  const response = await apiClient.post('/api/v1/budget/reset-daily');
  return response.data;
};

/**
 * Get budget system health status
 */
export const getBudgetHealth = async (): Promise<{
  status: 'healthy' | 'unhealthy';
  components: Record<string, string>;
  daily_budget_status: string;
  daily_utilization_percent: number;
  timestamp: string;
}> => {
  const response = await apiClient.get('/api/v1/budget/health');
  return response.data;
};
