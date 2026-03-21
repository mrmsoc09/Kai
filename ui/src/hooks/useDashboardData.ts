import { useEffect, useMemo, useState } from 'react';
import { missionService, opportunityService, reportService } from '../api';
import { useSystemStatus } from './useSystemStatus';
import type { Mission, Opportunity, Report } from '../types';

export function useDashboardData() {
  const [missions, setMissions] = useState<Mission[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [isLoadingMissions, setIsLoadingMissions] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { systemStatus, error: systemError, isLoading: isLoadingSystem, refreshStatus } = useSystemStatus();

  const refreshMissions = async () => {
    setIsLoadingMissions(true);
    setError(null);
    try {
      const [missionList, opportunityPayload, reportPayload] = await Promise.all([
        missionService.list(),
        opportunityService.list({ limit: 200, sort_by: 'score' }),
        reportService.list({ limit: 200 }),
      ]);
      setMissions(missionList);
      setOpportunities(opportunityPayload.opportunities);
      setReports(reportPayload.reports);
    } catch (missionError) {
      setError(missionError instanceof Error ? missionError.message : 'Failed to load missions.');
    } finally {
      setIsLoadingMissions(false);
    }
  };

  useEffect(() => {
    void refreshMissions();
  }, []);

  const metrics = useMemo(() => {
    const running = missions.filter((mission) => mission.state === 'running').length;
    const queued = missions.filter((mission) => mission.state === 'created').length;
    const completed = missions.filter((mission) => mission.state === 'completed').length;
    const activeOpportunities = opportunities.filter((row) => !['completed', 'failed', 'rejected', 'cancelled'].includes(String(row.status ?? 'proposed'))).length;
    const approvedAwaitingExecution = opportunities.filter(
      (row) => row.approval_state === 'approved' && !['executing', 'completed'].includes(String(row.status ?? '')),
    ).length;
    const validatedFindings = opportunities.reduce((total, row) => {
      const metadata = row.execution_metadata as Record<string, unknown> | undefined;
      const value = metadata?.validated_findings_produced;
      return total + (typeof value === 'number' ? value : 0);
    }, 0);
    const opportunityWithReports = opportunities.filter((row) => (row.linked_report_count ?? 0) > 0).length;
    const conversionRate = opportunities.length > 0 ? opportunityWithReports / opportunities.length : 0;

    return {
      running,
      queued,
      completed,
      total: missions.length,
      activeOpportunities,
      approvedAwaitingExecution,
      validatedFindings,
      reportsTotal: reports.length,
      conversionRate,
    };
  }, [missions, opportunities, reports.length]);

  const recentReports = useMemo(
    () =>
      [...reports]
        .sort((left, right) => new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime())
        .slice(0, 6),
    [reports],
  );

  const topConfidenceReports = useMemo(
    () => [...reports].sort((left, right) => right.confidence_score - left.confidence_score).slice(0, 6),
    [reports],
  );

  const recentMissions = useMemo(
    () =>
      [...missions]
        .sort((left, right) => right.id.localeCompare(left.id))
        .slice(0, 8),
    [missions],
  );

  return {
    missions,
    opportunities,
    reports,
    metrics,
    recentReports,
    topConfidenceReports,
    recentMissions,
    systemStatus,
    error: error ?? systemError,
    isLoading: isLoadingMissions || isLoadingSystem,
    refreshMissions,
    refreshStatus,
  };
}
