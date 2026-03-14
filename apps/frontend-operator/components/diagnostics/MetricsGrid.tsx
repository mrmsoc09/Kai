export function MetricsGrid({
  metrics
}: {
  metrics: Array<{ title: string; total: number; breakdown: Record<string, number> }>;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div key={metric.title} className="rounded-md border border-border bg-panel p-3">
          <p className="text-xs uppercase tracking-wide text-muted">{metric.title}</p>
          <p className="text-2xl font-semibold text-foreground">{metric.total}</p>
          <div className="mt-2 space-y-1 text-xs text-muted">
            {Object.entries(metric.breakdown).length === 0 ? (
              <p>no status breakdown</p>
            ) : (
              Object.entries(metric.breakdown).map(([status, count]) => (
                <p key={status}>
                  {status}: {count}
                </p>
              ))
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
