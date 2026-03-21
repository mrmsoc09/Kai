import { Link } from 'react-router-dom';
import { ChainSummaryPanel } from './ChainSummaryPanel';
import type { Report } from '../types';
import { formatTimestamp } from '../utils/format';
import { ReportScoreBadge } from './ReportScoreBadge';

interface ReportViewerProps {
  report: Report | null;
  onCopy: (content: string) => Promise<void>;
  onExport: (reportId: string, format: 'markdown' | 'json') => Promise<void>;
}

const renderFallbackMarkdown = (report: Report): string => {
  const lines = [
    `# ${report.title}`,
    '',
    `- Report ID: ${report.report_id}`,
    `- Severity: ${report.severity}`,
    `- Vulnerability Type: ${report.vulnerability_type}`,
    `- Target: ${report.target}`,
    '',
    '## Summary',
    report.summary,
    '',
    '## Reproduction Steps',
    ...report.reproduction_steps.map((step, index) => `${index + 1}. ${step}`),
    '',
    '## Impact',
    report.impact,
    '',
    '## Remediation',
    report.remediation,
    '',
    '## Validation Evidence',
    ...report.validation_evidence.map((row) => `- ${row}`),
  ];
  return lines.join('\n');
};

export function ReportViewer({ report, onCopy, onExport }: ReportViewerProps) {
  if (!report) {
    return (
      <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 text-sm text-slate-400">
        Select a report to view submission-ready details.
      </section>
    );
  }

  const exploitChain = report.exploit_chain ?? null;

  return (
    <section className="space-y-4 rounded-lg border border-slate-800 bg-slate-900/60 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">{report.title}</h3>
          <p className="text-xs text-slate-400">
            {report.report_id} · updated {formatTimestamp(report.updated_at)}
          </p>
          <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-wide">
            <span className="rounded border border-slate-700 px-2 py-0.5 text-slate-300">submission-ready</span>
            {exploitChain ? <span className="rounded border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-violet-200">chain-backed</span> : null}
            {report.opportunity_id ? <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-cyan-200">opportunity-derived</span> : null}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <ReportScoreBadge score={report.confidence_score} label="confidence" />
          <ReportScoreBadge score={report.quality_score} label="quality" />
          {typeof report.duplicate_risk === 'number' ? <ReportScoreBadge score={1 - report.duplicate_risk} label="novelty" /> : null}
          <button
            type="button"
            onClick={() => void onCopy(report.rendered_markdown || renderFallbackMarkdown(report))}
            className="rounded border border-cyan-500/40 bg-cyan-500/10 px-2 py-1 text-xs text-cyan-100 hover:border-cyan-400"
          >
            Copy Report
          </button>
          <button
            type="button"
            onClick={() => void onExport(report.report_id, 'markdown')}
            className="rounded border border-violet-500/40 bg-violet-500/10 px-2 py-1 text-xs text-violet-100 hover:border-violet-400"
          >
            Export MD
          </button>
          <button
            type="button"
            onClick={() => void onExport(report.report_id, 'json')}
            className="rounded border border-slate-600 px-2 py-1 text-xs text-slate-200 hover:border-slate-500"
          >
            Export JSON
          </button>
        </div>
      </div>

      <section className="rounded border border-slate-800 bg-slate-950/40 p-3">
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Linkage</h4>
        <div className="flex flex-wrap gap-2 text-xs">
          {report.opportunity_id ? (
            <Link to={`/opportunities?search=${encodeURIComponent(report.opportunity_id)}`} className="rounded border border-cyan-500/30 px-2 py-1 text-cyan-200 hover:border-cyan-400">
              Opportunity {report.opportunity_id}
            </Link>
          ) : (
            <span className="rounded border border-slate-700 px-2 py-1 text-slate-400">No linked opportunity</span>
          )}
          {report.mission_id ? (
            <Link to={`/mission-control?mission=${encodeURIComponent(report.mission_id)}`} className="rounded border border-slate-700 px-2 py-1 text-slate-300 hover:border-slate-500">
              Mission {report.mission_id}
            </Link>
          ) : null}
          <span className="rounded border border-slate-700 px-2 py-1 text-slate-300">dedupe signature {report.duplicate_hash.slice(0, 10)}</span>
        </div>
      </section>

      <section>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Summary</h4>
        <p className="text-sm text-slate-200">{report.summary}</p>
      </section>

      <section>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Reproduction Steps</h4>
        <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-200">
          {report.reproduction_steps.map((step, index) => (
            <li key={`${report.report_id}-step-${index}`}>{step}</li>
          ))}
        </ol>
      </section>

      <ChainSummaryPanel
        chain={exploitChain}
        title="Exploit Chain"
        emptyLabel="No exploit chain evidence attached to this report."
      />

      <section>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Impact</h4>
        <p className="text-sm text-slate-200">{report.impact}</p>
      </section>

      <section>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-400">Remediation</h4>
        <p className="text-sm text-slate-200">{report.remediation}</p>
      </section>

      {(report.http_requests.length > 0 || report.http_responses.length > 0) ? (
        <details className="rounded border border-slate-800 bg-slate-950/40 p-3 text-xs">
          <summary className="cursor-pointer font-semibold uppercase tracking-wide text-slate-400">HTTP Trace Evidence</summary>
          {report.http_requests.length > 0 ? (
            <div className="mt-2 space-y-1">
              <p className="text-slate-400">Requests</p>
              {report.http_requests.slice(0, 3).map((row, index) => (
                <pre key={`${report.report_id}-req-${index}`} className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 text-[11px] text-slate-300">{row}</pre>
              ))}
            </div>
          ) : null}
          {report.http_responses.length > 0 ? (
            <div className="mt-2 space-y-1">
              <p className="text-slate-400">Responses</p>
              {report.http_responses.slice(0, 3).map((row, index) => (
                <pre key={`${report.report_id}-res-${index}`} className="overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2 text-[11px] text-slate-300">{row}</pre>
              ))}
            </div>
          ) : null}
        </details>
      ) : null}
    </section>
  );
}
