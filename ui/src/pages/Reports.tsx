import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { reportService } from '../api';
import { ReportList } from '../components/ReportList';
import { ReportViewer } from '../components/ReportViewer';
import { useAuth } from '../hooks/useAuth';
import type { Report } from '../types';

const severities = ['all', 'critical', 'high', 'medium', 'low'] as const;

export function Reports() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { permissions } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(searchParams.get('report_id'));
  const [severity, setSeverity] = useState<(typeof severities)[number]>('all');
  const [minConfidence, setMinConfidence] = useState(0.5);
  const [targetFilter, setTargetFilter] = useState(searchParams.get('target') ?? '');
  const [missionFilter, setMissionFilter] = useState(searchParams.get('mission_id') ?? '');
  const [opportunityFilter, setOpportunityFilter] = useState(searchParams.get('opportunity_id') ?? '');
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadReports = useCallback(async () => {
    if (!permissions.canReviewGovernance) {
      setReports([]);
      setError('Reports require operator, analyst, or admin role.');
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const payload = await reportService.list({
        severity: severity === 'all' ? undefined : severity,
        min_confidence: minConfidence,
        target: targetFilter.trim() || undefined,
        mission_id: missionFilter.trim() || undefined,
        opportunity_id: opportunityFilter.trim() || undefined,
        limit: 300,
      });
      setReports(payload.reports);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : 'Failed to load reports.');
      setReports([]);
    } finally {
      setIsLoading(false);
    }
  }, [severity, minConfidence, targetFilter, missionFilter, opportunityFilter, permissions.canReviewGovernance]);

  useEffect(() => {
    void loadReports();
  }, [loadReports]);

  useEffect(() => {
    if (!reports.length) {
      setSelectedReportId(null);
      return;
    }

    const queryReportId = searchParams.get('report_id');
    if (queryReportId && reports.some((row) => row.report_id === queryReportId)) {
      setSelectedReportId(queryReportId);
      return;
    }
    if (!selectedReportId || !reports.some((row) => row.report_id === selectedReportId)) {
      setSelectedReportId(reports[0].report_id);
    }
  }, [reports, searchParams, selectedReportId]);

  const selectedReport = useMemo(
    () => reports.find((row) => row.report_id === selectedReportId) ?? null,
    [reports, selectedReportId],
  );

  useEffect(() => {
    const next = new URLSearchParams(window.location.search);
    if (selectedReportId) {
      next.set('report_id', selectedReportId);
    } else {
      next.delete('report_id');
    }
    setSearchParams(next, { replace: true });
  }, [selectedReportId, setSearchParams]);

  const copyReport = useCallback(async (content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopyStatus('Report copied to clipboard.');
      window.setTimeout(() => setCopyStatus(null), 1500);
    } catch {
      setCopyStatus('Clipboard unavailable in current browser context.');
      window.setTimeout(() => setCopyStatus(null), 2000);
    }
  }, []);

  const exportReport = useCallback(async (reportId: string, format: 'markdown' | 'json') => {
    try {
      const payload = await reportService.exportFile(reportId, format);
      const url = window.URL.createObjectURL(payload.blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = payload.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      setCopyStatus(`Exported ${payload.filename}.`);
      window.setTimeout(() => setCopyStatus(null), 1500);
    } catch {
      setCopyStatus(`Unable to export ${format} report.`);
      window.setTimeout(() => setCopyStatus(null), 2000);
    }
  }, []);

  const reportMetrics = useMemo(() => {
    const chainBacked = reports.filter((row) => Boolean(row.exploit_chain)).length;
    const highConfidence = reports.filter((row) => row.confidence_score >= 0.8).length;
    return {
      total: reports.length,
      chainBacked,
      highConfidence,
    };
  }, [reports]);

  return (
    <section className="space-y-4">
      {!permissions.canReviewGovernance ? (
        <section className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4 text-sm text-amber-200">
          Reports workspace is restricted to operator, analyst, and admin roles.
        </section>
      ) : null}

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Final Review & Export</h2>
            <p className="text-xs text-slate-400">Review quality/confidence, verify chain context, export submission payloads.</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs text-slate-300">
            <span className="rounded border border-slate-700 px-2 py-1">reports {reportMetrics.total}</span>
            <span className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-1 text-violet-200">chain-backed {reportMetrics.chainBacked}</span>
            <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-1 text-cyan-200">high confidence {reportMetrics.highConfidence}</span>
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-6">
          <label className="space-y-1 text-xs text-slate-400">
            Severity
            <select
              value={severity}
              onChange={(event) => setSeverity(event.target.value as (typeof severities)[number])}
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
            >
              {severities.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-xs text-slate-400">
            Min confidence
            <input
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={minConfidence}
              onChange={(event) => setMinConfidence(Number(event.target.value))}
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs text-slate-400">
            Target
            <input
              value={targetFilter}
              onChange={(event) => setTargetFilter(event.target.value)}
              placeholder="api.example.com"
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs text-slate-400">
            Mission
            <input
              value={missionFilter}
              onChange={(event) => setMissionFilter(event.target.value)}
              placeholder="mission id"
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
            />
          </label>

          <label className="space-y-1 text-xs text-slate-400">
            Opportunity
            <input
              value={opportunityFilter}
              onChange={(event) => setOpportunityFilter(event.target.value)}
              placeholder="opportunity id"
              className="w-full rounded border border-slate-700 bg-slate-950 px-2 py-2 text-sm text-slate-100"
            />
          </label>

          <div className="flex items-end">
            <button
              type="button"
              onClick={() => void loadReports()}
              className="w-full rounded border border-slate-700 px-3 py-2 text-xs text-slate-200 hover:border-slate-500"
            >
              Refresh
            </button>
          </div>
        </div>
      </section>

      {(missionFilter || opportunityFilter) ? (
        <section className="rounded-lg border border-cyan-500/20 bg-cyan-500/5 px-4 py-2 text-xs text-cyan-200">
          Filtered by:{' '}
          {missionFilter ? <span className="font-medium">mission {missionFilter}</span> : null}
          {missionFilter && opportunityFilter ? ' · ' : null}
          {opportunityFilter ? <span className="font-medium">opportunity {opportunityFilter}</span> : null}
          {' '}· {reportMetrics.total} report{reportMetrics.total !== 1 ? 's' : ''} shown
        </section>
      ) : null}

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-5">
        <section className="xl:col-span-2">
          <ReportList
            reports={reports}
            selectedReportId={selectedReportId}
            isLoading={isLoading}
            onSelect={(report) => setSelectedReportId(report.report_id)}
          />
        </section>
        <section className="xl:col-span-3">
          <ReportViewer report={selectedReport} onCopy={copyReport} onExport={exportReport} />
        </section>
      </section>

      {copyStatus ? <p className="text-xs text-emerald-300">{copyStatus}</p> : null}
      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
    </section>
  );
}
