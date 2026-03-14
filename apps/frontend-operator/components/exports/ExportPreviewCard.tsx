import type { SubmissionExportResponse } from "@/lib/types";

import { EmptyState } from "@/components/data-display/EmptyState";
import { ExportMetadataPanel } from "@/components/exports/ExportMetadataPanel";
import { ProviderPayloadViewer } from "@/components/exports/ProviderPayloadViewer";
import { ValidationWarningsPanel } from "@/components/exports/ValidationWarningsPanel";

export function ExportPreviewCard({
  result,
  title
}: {
  result: SubmissionExportResponse | null;
  title?: string;
}) {
  if (!result) {
    return <EmptyState title="No export data" description="Run preview or stage export to populate this panel." />;
  }
  return (
    <div className="space-y-3 rounded-md border border-border bg-panel p-3">
      <h4 className="text-sm font-semibold text-foreground">{title ?? "Provider Export Result"}</h4>
      <ExportMetadataPanel result={result} />
      <ValidationWarningsPanel missingFields={result.missing_fields} warnings={result.warnings} />
      <ProviderPayloadViewer payload={result.payload} />
    </div>
  );
}
