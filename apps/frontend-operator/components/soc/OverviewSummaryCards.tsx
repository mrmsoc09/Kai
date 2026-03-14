import { StatusBadge } from "@/components/status/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type OverviewMetric = {
  title: string;
  value: number;
  status?: string;
  helper?: string;
};

export function OverviewSummaryCards({ metrics }: { metrics: OverviewMetric[] }) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => (
        <Card key={metric.title}>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted">{metric.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-semibold text-foreground">{metric.value}</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {metric.status ? <StatusBadge status={metric.status} /> : null}
              {metric.helper ? <span className="text-xs text-muted">{metric.helper}</span> : null}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
