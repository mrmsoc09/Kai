import { Link } from 'react-router-dom';
import { StatusPill } from '../components/StatusPill';
import { useDashboardData } from '../hooks/useDashboardData';
import { useAuth } from '../hooks/useAuth';
import { formatConfidence, formatTimestamp } from '../utils/format';

function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <article className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <p className="text-xs uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-100">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-500">{hint}</p> : null}
    </article>
  );
}

export function Dashboard() {
  const {
    metrics,
    recentMissions,
    opportunities,
    recentReports,
    topConfidenceReports,
    systemStatus,
    error,
    isLoading,
    refreshMissions,
    refreshStatus,
  } = useDashboardData();
  const { permissions } = useAuth();

  const actionableOpportunities = opportunities
    .filter((row) => ['proposed', 'approved', 'executing'].includes(String(row.status ?? 'proposed')))
    .slice(0, 8);

  const awaitingExecution = opportunities.filter(
    (row) => row.approval_state === 'approved' && !['executing', 'completed'].includes(String(row.status ?? '')),
  );

  return (
    <section className="space-y-6">
      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-slate-100">Revenue Workflow Command Board</h2>
            <p className="text-xs text-slate-400">signal → opportunity → execution → report → export</p>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Link to="/mission-control" className="rounded border border-slate-700 px-2 py-1 text-slate-200 hover:border-slate-500">Mission Control</Link>
            <Link to="/opportunities" className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-cyan-100 hover:border-cyan-400">Opportunities</Link>
            <Link to="/reports" className="rounded border border-violet-500/40 bg-violet-500/10 px-2 py-1 text-violet-100 hover:border-violet-400">Reports</Link>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Validated Findings" value={metrics.validatedFindings} hint="from executed opportunities" />
        <StatCard label="Active Opportunities" value={metrics.activeOpportunities} />
        <StatCard label="Approved Awaiting Execute" value={metrics.approvedAwaitingExecution} hint={`${awaitingExecution.length} ready now`} />
        <StatCard label="Reports Generated" value={metrics.reportsTotal} />
        <StatCard label="Active Missions" value={metrics.running} />
        <StatCard label="Queued Missions" value={metrics.queued} />
        <StatCard label="Completed Missions" value={metrics.completed} />
        <StatCard label="Opp→Report Conversion" value={`${Math.round(metrics.conversionRate * 100)}%`} />
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4 xl:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">Actionable Opportunities</h3>
            <Link to="/opportunities" className="text-xs text-cyan-300 hover:text-cyan-200">Open Workbench</Link>
          </div>
          {actionableOpportunities.length === 0 ? (
            <p className="text-sm text-slate-400">No actionable opportunities yet. Run missions or expand known signals.</p>
          ) : (
            <div className="space-y-2">
              {actionableOpportunities.map((opportunity) => (
                <article key={opportunity.id} className="rounded border border-slate-800 bg-slate-950/50 p-3 text-sm">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-100">{opportunity.vuln_types[0] ?? 'unknown'} · {opportunity.name}</p>
                      <p className="text-xs text-slate-400">
                        expected yield {(opportunity.expected_yield ?? opportunity.estimated_yield ?? 0).toFixed(2)} · dup risk {Math.round((opportunity.duplicate_risk ?? 0) * 100)}%
                      </p>
                    </div>
                    <span className="rounded border border-slate-700 px-2 py-0.5 text-xs uppercase text-slate-300">
                      {opportunity.status ?? 'proposed'}
                    </span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-300">
                    <span className="rounded border border-slate-700 px-2 py-0.5">targets {(opportunity.candidate_targets ?? []).length}</span>
                    <span className="rounded border border-slate-700 px-2 py-0.5">reports {opportunity.linked_report_count ?? 0}</span>
                    <span className="rounded border border-slate-700 px-2 py-0.5">missions {opportunity.linked_mission_count ?? 0}</span>
                    <Link to={`/opportunities?search=${encodeURIComponent(opportunity.id)}`} className="rounded border border-cyan-500/30 px-2 py-0.5 text-cyan-200 hover:border-cyan-400">
                      open
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">System Status</h3>
            <button
              type="button"
              onClick={() => void refreshStatus()}
              className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
            >
              Refresh
            </button>
          </div>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-400">Platform</dt><dd className="text-slate-200">{systemStatus?.status ?? 'unknown'}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Active Missions</dt><dd className="text-slate-200">{systemStatus?.active_missions ?? '-'}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Queue Depth</dt><dd className="text-slate-200">{systemStatus?.queue_depth ?? '-'}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-400">Worker</dt><dd className={systemStatus?.worker_ok ? 'text-emerald-300' : 'text-rose-300'}>{systemStatus?.worker_ok ? 'ok' : 'down'}</dd></div>
          </dl>
          {!permissions.canViewSystemStatus ? <p className="mt-3 text-xs text-amber-300">System status is visible to admin role.</p> : null}
        </section>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">Recent Reports</h3>
            <Link to="/reports" className="text-xs text-violet-300 hover:text-violet-200">Review & Export</Link>
          </div>
          {recentReports.length === 0 ? (
            <p className="text-sm text-slate-400">No reports generated yet.</p>
          ) : (
            <div className="space-y-2">
              {recentReports.map((report) => (
                <article key={report.report_id} className="rounded border border-slate-800 bg-slate-950/50 p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-slate-100">{report.title}</p>
                    <span className="text-slate-400">{formatTimestamp(report.updated_at)}</span>
                  </div>
                  <p className="mt-1 text-slate-300">
                    {report.target} · confidence {formatConfidence(report.confidence_score)} · quality {formatConfidence(report.quality_score)}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {report.opportunity_id ? (
                      <Link to={`/opportunities?search=${encodeURIComponent(report.opportunity_id)}`} className="rounded border border-cyan-500/30 px-2 py-0.5 text-cyan-200 hover:border-cyan-400">
                        opportunity
                      </Link>
                    ) : null}
                    {report.mission_id ? (
                      <Link to={`/mission-control?mission=${encodeURIComponent(report.mission_id)}`} className="rounded border border-slate-700 px-2 py-0.5 text-slate-300 hover:border-slate-500">
                        mission
                      </Link>
                    ) : null}
                    <Link to={`/reports?report_id=${encodeURIComponent(report.report_id)}`} className="rounded border border-violet-500/30 px-2 py-0.5 text-violet-200 hover:border-violet-400">
                      open report
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-slate-100">Recent Missions</h3>
            <button
              type="button"
              onClick={() => void refreshMissions()}
              className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
            >
              Refresh
            </button>
          </div>
          {recentMissions.length === 0 ? (
            <p className="text-sm text-slate-400">No mission records available.</p>
          ) : (
            <div className="space-y-2">
              {recentMissions.map((mission) => (
                <article key={mission.id} className="rounded border border-slate-800 bg-slate-950/50 p-3 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium text-slate-100">{mission.id}</p>
                    <StatusPill status={mission.state} />
                  </div>
                  <p className="mt-1 text-slate-300">{mission.workflowId} · phase {mission.phase || '-'}</p>
                  <p className="mt-1 text-slate-400">progress {Math.round((mission.progress ?? 0) * 100)}%</p>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="rounded-lg border border-slate-800 bg-slate-900/60 p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-100">Highest Confidence Reports</h3>
          <Link to="/reports" className="text-xs text-violet-300 hover:text-violet-200">All Reports</Link>
        </div>
        {topConfidenceReports.length === 0 ? (
          <p className="mt-2 text-sm text-slate-400">No confidence-ranked reports yet.</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {topConfidenceReports.slice(0, 5).map((report) => (
              <li key={report.report_id}>
                <Link
                  to={`/reports?report_id=${encodeURIComponent(report.report_id)}`}
                  className="flex items-center justify-between rounded border border-slate-800 bg-slate-950/40 px-3 py-2 text-slate-300 hover:border-slate-700 hover:bg-slate-900"
                >
                  <span className="truncate">{report.title}</span>
                  <span className="ml-3 shrink-0 font-medium text-cyan-300">{Math.round(report.confidence_score * 100)}%</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {error ? <p className="text-xs text-rose-300">{error}</p> : null}
      {isLoading ? <p className="text-xs text-slate-500">Loading dashboard data...</p> : null}
    </section>
  );
}
