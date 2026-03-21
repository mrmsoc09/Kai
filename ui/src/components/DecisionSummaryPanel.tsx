interface DecisionSummaryPanelProps {
  summary: string | null | undefined;
  detail?: Record<string, unknown> | null;
  title?: string;
}

const pickDecisionFields = (detail: Record<string, unknown> | null | undefined): Array<{ key: string; value: string }> => {
  if (!detail) {
    return [];
  }
  const candidates: Array<[string, unknown]> = [
    ['chosen_action', detail.chosen_action],
    ['decision', detail.decision],
    ['reason', detail.reason],
    ['reason_code', detail.reason_code],
    ['score', detail.score],
  ];

  return candidates
    .map(([key, value]) => {
      if (typeof value === 'string' && value.trim()) {
        return { key, value };
      }
      if (typeof value === 'number' && Number.isFinite(value)) {
        return { key, value: value.toFixed(2) };
      }
      return null;
    })
    .filter((row): row is { key: string; value: string } => Boolean(row));
};

export function DecisionSummaryPanel({
  summary,
  detail,
  title = 'Decision Trace Summary',
}: DecisionSummaryPanelProps) {
  const fields = pickDecisionFields(detail);
  const rejectedAlternatives = Array.isArray(detail?.rejected_alternatives)
    ? detail?.rejected_alternatives.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === 'object').slice(0, 5)
    : [];

  if (!summary && fields.length === 0) {
    return (
      <section className="rounded border border-slate-800 bg-slate-950/40 p-3">
        <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
        <p className="mt-1 text-xs text-slate-500">No decision summary available.</p>
      </section>
    );
  }

  return (
    <section className="rounded border border-slate-800 bg-slate-950/40 p-3">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-400">{title}</h4>
      {summary ? <p className="mt-2 text-xs text-slate-200">{summary}</p> : null}
      {fields.length > 0 ? (
        <details className="mt-2 text-xs text-slate-300">
          <summary className="cursor-pointer text-slate-400">Decision detail</summary>
          <dl className="mt-2 space-y-1">
            {fields.map((row) => (
              <div key={row.key} className="flex justify-between gap-3">
                <dt className="text-slate-500">{row.key}</dt>
                <dd className="text-right text-slate-200">{row.value}</dd>
              </div>
            ))}
          </dl>
          {rejectedAlternatives.length > 0 ? (
            <div className="mt-2 border-t border-slate-800 pt-2">
              <p className="text-slate-500">Rejected alternatives</p>
              <ul className="mt-1 space-y-1">
                {rejectedAlternatives.map((row, index) => (
                  <li key={`rejected-${index}`} className="text-slate-300">
                    {String(row.action ?? row.chosen_action ?? 'alternative')} — {String(row.reason ?? row.reason_code ?? 'no reason provided')}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </details>
      ) : null}
    </section>
  );
}
