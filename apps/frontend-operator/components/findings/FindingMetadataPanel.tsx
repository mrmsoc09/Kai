import type { FindingDiagnosticsResponse } from "@/lib/types";

import { JsonViewer } from "@/components/data-display/JsonViewer";

export function FindingMetadataPanel({ finding }: { finding: FindingDiagnosticsResponse }) {
  return <JsonViewer value={finding.finding.scope_json} />;
}
