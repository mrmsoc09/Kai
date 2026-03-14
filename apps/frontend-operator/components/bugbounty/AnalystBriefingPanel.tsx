import type { AnalystBriefing, Phase7AnalystSupport } from "@/lib/types";

import { JsonViewer } from "@/components/data-display/JsonViewer";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function AnalystBriefingPanel({
  briefing,
  phase7Support
}: {
  briefing?: AnalystBriefing;
  phase7Support?: Phase7AnalystSupport;
}) {
  const topTargets = Array.isArray(briefing?.top_targets) ? briefing.top_targets : [];
  const topCandidates = Array.isArray(briefing?.top_candidates) ? briefing.top_candidates : [];

  if (!briefing && !phase7Support) {
    return (
      <EmptyState
        title="No analyst briefing available"
        description="Inference outputs are not yet available for the selected program."
      />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Top Targets</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {topTargets.length === 0 ? (
            <p className="text-sm text-muted">No top target records.</p>
          ) : (
            topTargets.map((item) => (
              <div key={`${item.program_id}:${item.scope_target_id ?? "none"}`} className="rounded border border-border p-2">
                <p className="font-mono text-xs text-muted">program={item.program_id}</p>
                <p className="font-mono text-xs text-muted">target={item.scope_target_id ?? "none"}</p>
                <div className="mt-2 flex flex-wrap gap-1">
                  <ScoreBadge value={item.opportunity_score} label="opportunity" />
                  <ScoreBadge value={item.target_priority_score} label="priority" />
                </div>
                <p className="mt-2 text-xs">workflow={item.recommended_workflow || "n/a"}</p>
                <p className="text-xs text-muted">action={item.next_best_action || "n/a"}</p>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Top Candidates</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {topCandidates.length === 0 ? (
            <p className="text-sm text-muted">No candidate records.</p>
          ) : (
            topCandidates.map((item) => (
              <div key={item.queue_item_id} className="rounded border border-border p-2">
                <p className="font-medium text-sm">{item.vulnerability_type || "Unknown vulnerability type"}</p>
                <p className="text-xs text-muted">{item.affected_asset || "Unknown asset"}</p>
                <div className="mt-2 flex items-center gap-2">
                  <ScoreBadge value={item.reportability_score} label="reportability" />
                  <span className="text-xs text-muted">status={item.status || "unknown"}</span>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader>
          <CardTitle>Phase 7 Decision Support</CardTitle>
        </CardHeader>
        <CardContent>
          {phase7Support ? (
            <JsonViewer value={phase7Support} />
          ) : (
            <p className="text-sm text-muted">Phase 7 analyst support records are not available.</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
