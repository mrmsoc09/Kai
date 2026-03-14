import type { FindingDiagnosticsResponse } from "@/lib/types";

export function ArtifactList({ finding }: { finding: FindingDiagnosticsResponse }) {
  return (
    <div className="rounded-md border border-border bg-panel p-2 text-sm text-foreground">
      Artifact records are summarized in diagnostics only in this pass. Count: {finding.counts.artifacts}
    </div>
  );
}
