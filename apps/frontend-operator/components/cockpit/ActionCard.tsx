import Link from "next/link";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ActionCard({
  title,
  value,
  status,
  detail,
  href,
  ctaLabel = "Open"
}: {
  title: string;
  value: string | number;
  status?: string;
  detail?: string;
  href?: string;
  ctaLabel?: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-xs uppercase tracking-wide text-muted">{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        <p className="text-2xl font-semibold text-foreground">{value}</p>
        <div className="flex flex-wrap items-center justify-between gap-2">
          {status ? <StatusBadge status={status} /> : <span className="text-xs text-muted">No status</span>}
          {href ? (
            <Link href={href} className="text-xs font-medium text-active hover:underline">
              {ctaLabel}
            </Link>
          ) : null}
        </div>
        {detail ? <p className="text-xs text-muted">{detail}</p> : null}
      </CardContent>
    </Card>
  );
}
