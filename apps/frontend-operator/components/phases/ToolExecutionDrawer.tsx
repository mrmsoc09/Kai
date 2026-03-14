import type { CampaignDiagnosticsResponse } from "@/lib/types";

import { JsonViewer } from "@/components/data-display/JsonViewer";

export function ToolExecutionDrawer({ diagnostics }: { diagnostics: CampaignDiagnosticsResponse }) {
  return <JsonViewer value={diagnostics.status_breakdown.tool_executions ?? {}} />;
}
