"use client";

import { useMemo, useState } from "react";

import { usePredictionSignals } from "@/hooks/usePredictionSignals";

import { EvidenceLinkPanel } from "@/components/bugbounty/EvidenceLinkPanel";
import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { PredictionTable } from "@/components/bugbounty/PredictionTable";
import { ReasoningSummaryPanel } from "@/components/bugbounty/ReasoningSummaryPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { JsonViewer } from "@/components/data-display/JsonViewer";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function PredictionsPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [searchText, setSearchText] = useState("");
  const [minOpportunity, setMinOpportunity] = useState("");
  const data = usePredictionSignals(programIdFilter.trim() || undefined);

  const filteredPredictions = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    const minScore = Number.parseFloat(minOpportunity);
    return (data.predictionsQuery.data ?? []).filter((row) => {
      if (Number.isFinite(minScore) && (row.opportunity_score ?? -1) < minScore) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [
        row.predicted_vulnerability_type,
        row.program_id,
        row.scope_target_id,
        row.recommended_next_workflow,
        row.recommended_follow_up_action,
        row.reasoning_summary
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [data.predictionsQuery.data, minOpportunity, searchText]);

  const evidenceRefs = useMemo(
    () =>
      (data.signalsQuery.data ?? [])
        .flatMap((signal) => signal.evidence_refs_json ?? [])
        .filter((value, index, arr) => arr.indexOf(value) === index)
        .slice(0, 30),
    [data.signalsQuery.data]
  );

  const reasoningSummaries = useMemo(
    () => (data.recommendationsQuery.data ?? []).slice(0, 10).map((item) => item.reasoning_summary),
    [data.recommendationsQuery.data]
  );

  return (
    <div className="operator-grid">
      <PageHeader
        title="Predictions and Signal Intelligence"
        description="Phase 6/7 intelligence outputs with explainable vulnerability predictions and next-best actions."
      />

      <div className="grid gap-3 md:grid-cols-[1fr_auto]">
        <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />
        <Card>
          <CardHeader>
            <CardTitle>Inference Action</CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={() => data.runMutation.mutate()} disabled={data.runMutation.isPending}>
              Run Prediction Cycle
            </Button>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Vulnerability Predictions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search vulnerability, workflow, action, reasoning"
            />
            <Input
              value={minOpportunity}
              onChange={(event) => setMinOpportunity(event.target.value)}
              placeholder="min opportunity score (optional)"
              inputMode="decimal"
            />
          </div>
          <div className="text-xs text-muted">results: {filteredPredictions.length}</div>
          {data.predictionsQuery.isLoading ? <LoadingState label="Loading predictions..." /> : null}
          {data.predictionsQuery.isError ? (
            <ErrorState error={data.predictionsQuery.error} title="Predictions failed" />
          ) : null}
          {data.runMutation.isError ? <ErrorState error={data.runMutation.error} title="Phase 7 run failed" /> : null}
          <PredictionTable rows={filteredPredictions} />
        </CardContent>
      </Card>

      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Signals</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{data.signalsQuery.data?.length ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Recent Deltas</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{data.deltasQuery.data?.length ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Recommendations</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {data.recommendationsQuery.data?.length ?? 0}
          </CardContent>
        </Card>
      </div>

      {data.signalsQuery.isLoading || data.deltasQuery.isLoading || data.recommendationsQuery.isLoading ? (
        <LoadingState label="Loading supporting signals and recommendations..." />
      ) : null}
      {data.signalsQuery.isError ? <ErrorState error={data.signalsQuery.error} title="Signal intelligence failed" /> : null}
      {data.deltasQuery.isError ? <ErrorState error={data.deltasQuery.error} title="Delta source failed" /> : null}
      {data.recommendationsQuery.isError ? (
        <ErrorState error={data.recommendationsQuery.error} title="Recommendation source failed" />
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        <EvidenceLinkPanel title="Supporting Signal Evidence References" links={evidenceRefs} />
        <ReasoningSummaryPanel title="Recommendation Reasoning" summaries={reasoningSummaries} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Analyst Support Snapshot</CardTitle>
        </CardHeader>
        <CardContent>
          {data.analystSupportQuery.isLoading ? <LoadingState label="Loading analyst support..." /> : null}
          {data.analystSupportQuery.isError ? (
            <ErrorState error={data.analystSupportQuery.error} title="Analyst support failed" />
          ) : null}
          {data.analystSupportQuery.data ? (
            <JsonViewer value={data.analystSupportQuery.data} />
          ) : (
            !data.analystSupportQuery.isLoading && (
              <EmptyState
                title="No analyst support output"
                description="No analyst-support summary is available for the selected program filter."
              />
            )
          )}
        </CardContent>
      </Card>
    </div>
  );
}
