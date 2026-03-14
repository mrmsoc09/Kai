import { EmptyState } from "@/components/data-display/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function EvidenceLinkPanel({
  title,
  links
}: {
  title: string;
  links: string[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {links.length > 0 ? (
          <ul className="space-y-1 text-xs text-muted">
            {links.map((link) => (
              <li key={link} className="rounded border border-border bg-elevated px-2 py-1 font-mono">
                {link}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No evidence links" description="No evidence references were provided by the backend." />
        )}
      </CardContent>
    </Card>
  );
}
