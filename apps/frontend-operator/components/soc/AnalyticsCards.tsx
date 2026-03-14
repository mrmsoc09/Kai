import type { DiagnosticsSummaryResponse } from "@/lib/types";

import { DiagnosticsSummaryCards } from "@/components/diagnostics/DiagnosticsSummaryCards";

export function AnalyticsCards({ summary }: { summary: DiagnosticsSummaryResponse }) {
  return <DiagnosticsSummaryCards summary={summary} />;
}
