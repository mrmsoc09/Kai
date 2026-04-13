/**
 * Validation and normalization utilities for V-RAD dashboard
 * Ensures data integrity and prevents UI rendering issues
 */

import { TelemetryMetrics } from '../types/dashboard';

/**
 * Telemetry bounds definition
 * All values must stay within these ranges to prevent UI overflow
 */
export const TELEMETRY_BOUNDS = {
  cpuLoad: { min: 0, max: 100 },
  coreTemp: { min: 0, max: 100 },
  vramUtilization: { min: 0, max: 100 },
  bandwidthThroughput: { min: 0, max: 5000 },
  analysisThreads: { min: 0, max: 200 },
  rateLimitLevel: { min: 0, max: 100 },
} as const;

/**
 * Critical state thresholds (>90% = critical, 70-90% = warning)
 */
export const CRITICAL_THRESHOLDS = {
  cpuLoad: 90,
  coreTemp: 90,
  vramUtilization: 90,
  rateLimitLevel: 80,
} as const;

/**
 * Clamp a value between min and max bounds
 * @param value - The value to clamp
 * @param min - Minimum bound (inclusive)
 * @param max - Maximum bound (inclusive)
 * @returns Clamped value
 */
export const clamp = (value: number, min: number, max: number): number => {
  return Math.max(min, Math.min(max, value));
};

/**
 * Validate and normalize telemetry metrics
 * Ensures all values are within acceptable bounds
 * @param metrics - Raw telemetry metrics
 * @returns Validated and clamped metrics
 */
export const validateTelemetryMetrics = (metrics: TelemetryMetrics): TelemetryMetrics => {
  if (!metrics) {
    throw new Error('Telemetry metrics is required');
  }

  const validated: TelemetryMetrics = {
    cpuLoad: clamp(metrics.cpuLoad, TELEMETRY_BOUNDS.cpuLoad.min, TELEMETRY_BOUNDS.cpuLoad.max),
    coreTemp: clamp(metrics.coreTemp, TELEMETRY_BOUNDS.coreTemp.min, TELEMETRY_BOUNDS.coreTemp.max),
    vramUtilization: clamp(metrics.vramUtilization, TELEMETRY_BOUNDS.vramUtilization.min, TELEMETRY_BOUNDS.vramUtilization.max),
    bandwidthThroughput: clamp(metrics.bandwidthThroughput, TELEMETRY_BOUNDS.bandwidthThroughput.min, TELEMETRY_BOUNDS.bandwidthThroughput.max),
    analysisThreads: clamp(metrics.analysisThreads, TELEMETRY_BOUNDS.analysisThreads.min, TELEMETRY_BOUNDS.analysisThreads.max),
    rateLimitLevel: clamp(metrics.rateLimitLevel, TELEMETRY_BOUNDS.rateLimitLevel.min, TELEMETRY_BOUNDS.rateLimitLevel.max),
  };

  // Check for NaN values (indicates calculation error)
  Object.entries(validated).forEach(([key, value]) => {
    if (typeof value === 'number' && isNaN(value)) {
      console.error(`[VALIDATION] NaN detected in telemetry field: ${key}`);
      // Provide default safe value
      validated[key as keyof TelemetryMetrics] = 0 as any;
    }
  });

  return validated;
};

/**
 * Check if a metric is in critical state
 * @param metricValue - The metric value (0-100 range)
 * @param metricKey - The metric key for threshold lookup
 * @returns true if value exceeds critical threshold
 */
export const isCriticalState = (metricValue: number, metricKey: keyof typeof CRITICAL_THRESHOLDS): boolean => {
  if (metricKey in CRITICAL_THRESHOLDS) {
    return metricValue > CRITICAL_THRESHOLDS[metricKey];
  }
  return metricValue > 90;
};

/**
 * Check if a metric is in warning state
 * @param metricValue - The metric value (0-100 range)
 * @returns true if value is between 70-90%
 */
export const isWarningState = (metricValue: number): boolean => {
  return metricValue > 70 && metricValue <= 90;
};

/**
 * Get status label for a metric value
 * @param metricValue - The metric value
 * @returns Status string: "normal" | "warning" | "critical"
 */
export const getMetricStatus = (metricValue: number): 'normal' | 'warning' | 'critical' => {
  if (isCriticalState(metricValue, 'cpuLoad')) return 'critical';
  if (isWarningState(metricValue)) return 'warning';
  return 'normal';
};

/**
 * Validate a numeric value is a valid number
 * @param value - Value to validate
 * @returns true if valid number (not NaN, not Infinity)
 */
export const isValidNumber = (value: unknown): value is number => {
  return typeof value === 'number' && isFinite(value);
};

/**
 * Calculate percentage for display
 * Safely handles edge cases
 * @param current - Current value
 * @param max - Maximum value
 * @returns Percentage (0-100), or 0 on error
 */
export const calculatePercentage = (current: number, max: number): number => {
  if (!isValidNumber(current) || !isValidNumber(max) || max === 0) {
    return 0;
  }
  return clamp((current / max) * 100, 0, 100);
};

/**
 * Format telemetry value for display
 * @param value - The numeric value
 * @param decimals - Number of decimal places (default: 0)
 * @returns Formatted string
 */
export const formatTelemetryValue = (value: number, decimals: number = 0): string => {
  if (!isValidNumber(value)) {
    return '—';
  }
  return value.toFixed(decimals);
};

/**
 * Validate bandwidth value (MB/s)
 * @param value - Bandwidth in MB/s
 * @returns Validated and formatted string (GB/s)
 */
export const formatBandwidth = (value: number): string => {
  const validated = clamp(value, 0, 5000);
  const gb = validated / 1000;
  return gb.toFixed(1);
};

/**
 * Check if all metrics are within normal ranges
 * @param metrics - Telemetry metrics to check
 * @returns true if all metrics are in normal state
 */
export const allMetricsNormal = (metrics: TelemetryMetrics): boolean => {
  return (
    !isCriticalState(metrics.cpuLoad, 'cpuLoad') &&
    !isCriticalState(metrics.coreTemp, 'coreTemp') &&
    !isCriticalState(metrics.vramUtilization, 'vramUtilization') &&
    !isCriticalState(metrics.rateLimitLevel, 'rateLimitLevel') &&
    !isWarningState(metrics.cpuLoad) &&
    !isWarningState(metrics.coreTemp) &&
    !isWarningState(metrics.vramUtilization)
  );
};
