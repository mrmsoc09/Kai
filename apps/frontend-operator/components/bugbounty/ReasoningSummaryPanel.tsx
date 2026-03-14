import { EmptyState } from "@/components/data-display/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ReasoningSummaryPanel({
  title,
  summaries
}: {
  title: string;
  summaries: string[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {summaries.length > 0 ? (
          <ul className="space-y-2">
            {summaries.map((summary, index) => (
              <li key={`${title}-${index}`} className="rounded border border-border bg-elevated p-2 text-sm text-muted">
                {summary}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No reasoning summaries" description="No reasoning payloads are available." />
        )}
      </CardContent>
    </Card>
  );
}
