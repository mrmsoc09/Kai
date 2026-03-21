import type { Report } from '../types';
import { formatTimestamp } from '../utils/format';
import { ReportScoreBadge } from './ReportScoreBadge';

interface ReportListProps {
  reports: Report[];
  selectedReportId: string | null;
  isLoading?: boolean;
  onSelect: (report: Report) => void;
}

const severityClass = (severity: string): string => {
  const normalized = severity.toLowerCase();
  if (normalized === 'critical') {
    return 'bg-rose-500/20 text-rose-200';
  }
  if (normalized === 'high') {
    return 'bg-orange-500/20 text-orange-200';
  }
  if (normalized === 'medium') {
    return 'bg-amber-500/20 text-amber-200';
  }
  return 'bg-slate-700 text-slate-200';
};

export function ReportList({ reports, selectedReportId, isLoading = false, onSelect }: ReportListProps) {
  if (reports.length === 0) {
    return (
      <div className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
        {isLoading ? 'Loading reports...' : 'No reports found for current filters.'}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            <th className="px-3 py-2">Title</th>
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Severity</th>
            <th className="px-3 py-2">Target</th>
            <th className="px-3 py-2">Links</th>
            <th className="px-3 py-2">Scores</th>
            <th className="px-3 py-2">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {reports.map((report) => {
            const active = report.report_id === selectedReportId;
            return (
              <tr
                key={report.report_id}
                className={`cursor-pointer transition ${active ? 'bg-cyan-500/10' : 'hover:bg-slate-800/40'}`}
                onClick={() => onSelect(report)}
              >
                <td className="px-3 py-3 text-slate-100">{report.title}</td>
                <td className="px-3 py-3 text-slate-300">{report.vulnerability_type}</td>
                <td className="px-3 py-3">
                  <span className={`rounded px-2 py-0.5 text-xs uppercase ${severityClass(report.severity)}`}>{report.severity}</span>
                </td>
                <td className="px-3 py-3 text-slate-300">{report.target}</td>
                <td className="px-3 py-3 text-xs text-slate-300">
                  <div className="space-y-1">
                    <p>mission: {report.mission_id ?? '-'}</p>
                    <p>opp: {report.opportunity_id ?? '-'}</p>
                    {report.exploit_chain ? (
                      <span className="inline-flex rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] uppercase text-violet-200">
                        chain-backed
                      </span>
                    ) : null}
                  </div>
                </td>
                <td className="px-3 py-3">
                  <div className="flex flex-wrap gap-2">
                    <ReportScoreBadge score={report.confidence_score} label="confidence" />
                    <ReportScoreBadge score={report.quality_score} label="quality" />
                  </div>
                </td>
                <td className="px-3 py-3 text-xs text-slate-400">{formatTimestamp(report.updated_at)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
