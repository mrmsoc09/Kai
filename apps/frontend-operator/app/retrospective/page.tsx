"use client";

import { useMemo, useState } from "react";

import { useRetrospective } from "@/hooks/useRetrospective";

import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Td, Th } from "@/components/ui/table";

export default function RetrospectivePage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [windowDays, setWindowDays] = useState(30);
  const programId = programIdFilter.trim() || undefined;
  const data = useRetrospective(programId, windowDays);

  const summary = data.summaryQuery.data;
  const topPrograms = Array.isArray(summary?.top_programs) ? summary.top_programs : [];
  const topTargets = Array.isArray(summary?.top_targets) ? summary.top_targets : [];
  const workflowLeaders = Array.isArray(summary?.workflow_value_leaders) ? summary.workflow_value_leaders : [];
  const alertSummary = summary?.alert_noise_summary ?? {};
  const recommendationSummary = summary?.recommendation_success_summary ?? {};

  const isAnyLoading =
    data.summaryQuery.isLoading ||
    data.workflowsQuery.isLoading ||
    data.targetsQuery.isLoading ||
    data.recommendationsQuery.isLoading ||
    data.alertsQuery.isLoading;

  const summaryMetrics = useMemo(
    () => [
      {
        title: "Workflow Records",
        value: data.workflowsQuery.data?.length ?? 0
      },
      {
        title: "Target Records",
        value: data.targetsQuery.data?.length ?? 0
      },
      {
        title: "Recommendation Outcomes",
        value: data.recommendationsQuery.data?.length ?? 0
      },
      {
        title: "Alert Outcomes",
        value: data.alertsQuery.data?.length ?? 0
      }
    ],
    [data.alertsQuery.data, data.recommendationsQuery.data, data.targetsQuery.data, data.workflowsQuery.data]
  );

  return (
    <div className="operator-grid">
      <PageHeader
        title="Retrospective Intelligence"
        description="Phase 10 historical outcome analysis that feeds deterministic scoring modifiers for opportunity selection."
      />

      <div className="grid gap-3 lg:grid-cols-[1fr_auto_auto]">
        <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />
        <Card>
          <CardHeader>
            <CardTitle>Window (Days)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Input
              value={windowDays}
              onChange={(event) => {
                const parsed = Number(event.target.value);
                if (!Number.isFinite(parsed)) {
                  return;
                }
                setWindowDays(Math.max(1, Math.min(365, Math.round(parsed))));
              }}
              type="number"
              min={1}
              max={365}
            />
            <p className="text-xs text-muted">Retrospective aggregation window.</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Retrospective Run</CardTitle>
          </CardHeader>
          <CardContent>
            <Button onClick={() => data.runMutation.mutate()} disabled={data.runMutation.isPending}>
              Run Phase 10
            </Button>
          </CardContent>
        </Card>
      </div>

      {isAnyLoading ? <LoadingState label="Loading retrospective intelligence..." /> : null}
      {data.summaryQuery.isError ? (
        <ErrorState error={data.summaryQuery.error} title="Retrospective summary failed" />
      ) : null}
      {data.workflowsQuery.isError ? (
        <ErrorState error={data.workflowsQuery.error} title="Workflow retrospective records failed" />
      ) : null}
      {data.targetsQuery.isError ? (
        <ErrorState error={data.targetsQuery.error} title="Target retrospective records failed" />
      ) : null}
      {data.recommendationsQuery.isError ? (
        <ErrorState error={data.recommendationsQuery.error} title="Recommendation outcomes failed" />
      ) : null}
      {data.alertsQuery.isError ? (
        <ErrorState error={data.alertsQuery.error} title="Alert outcomes failed" />
      ) : null}
      {data.runMutation.isError ? (
        <ErrorState error={data.runMutation.error} title="Phase 10 run failed" />
      ) : null}

      <div className="grid gap-3 md:grid-cols-4">
        {summaryMetrics.map((metric) => (
          <Card key={metric.title}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted">{metric.title}</CardTitle>
            </CardHeader>
            <CardContent className="text-2xl font-semibold">{metric.value}</CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Top Programs (Yield)</CardTitle>
          </CardHeader>
          <CardContent>
            {topPrograms.length ? (
              <DataTable>
                <thead>
                  <tr>
                    <Th>Program</Th>
                    <Th>Avg Yield</Th>
                    <Th>Records</Th>
                  </tr>
                </thead>
                <tbody>
                  {topPrograms.slice(0, 15).map((row, index) => (
                    <tr key={`${row.program_id ?? "unknown"}:${index}`}>
                      <Td>{String(row.program_id ?? "n/a")}</Td>
                      <Td>
                        <ScoreBadge
                          value={typeof row.avg_target_yield_score === "number" ? row.avg_target_yield_score : null}
                          label="yield"
                        />
                      </Td>
                      <Td>{String(row.target_records ?? "0")}</Td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            ) : (
              <EmptyState
                title="No program retrospective records"
                description="Run Phase 10 to materialize program-level retrospective yield summaries."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Targets</CardTitle>
          </CardHeader>
          <CardContent>
            {topTargets.length ? (
              <DataTable>
                <thead>
                  <tr>
                    <Th>Target</Th>
                    <Th>Yield</Th>
                    <Th>Reportability</Th>
                    <Th>Duplicate</Th>
                  </tr>
                </thead>
                <tbody>
                  {topTargets.slice(0, 20).map((row, index) => (
                    <tr key={`${row.scope_target_id ?? "unknown"}:${index}`}>
                      <Td className="font-mono text-xs">{String(row.scope_target_id ?? "n/a")}</Td>
                      <Td>
                        <ScoreBadge value={typeof row.target_yield_score === "number" ? row.target_yield_score : null} label="yield" />
                      </Td>
                      <Td>
                        <ScoreBadge
                          value={typeof row.target_reportability_rate === "number" ? row.target_reportability_rate : null}
                          label="reportability"
                        />
                      </Td>
                      <Td>
                        <ScoreBadge
                          value={typeof row.target_duplicate_rate === "number" ? row.target_duplicate_rate : null}
                          label="duplicate"
                        />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            ) : (
              <EmptyState
                title="No target retrospective records"
                description="No target-level retrospective records are available for this filter and window."
              />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Workflow Value Leaders</CardTitle>
          </CardHeader>
          <CardContent>
            {workflowLeaders.length ? (
              <DataTable>
                <thead>
                  <tr>
                    <Th>Workflow</Th>
                    <Th>Signal Value</Th>
                    <Th>Reportability</Th>
                    <Th>Noise</Th>
                  </tr>
                </thead>
                <tbody>
                  {workflowLeaders.slice(0, 20).map((row, index) => (
                    <tr key={`${row.workflow_template ?? "workflow"}:${index}`}>
                      <Td>{String(row.workflow_template ?? "unknown")}</Td>
                      <Td>
                        <ScoreBadge
                          value={typeof row.workflow_signal_value === "number" ? row.workflow_signal_value : null}
                          label="signal"
                        />
                      </Td>
                      <Td>
                        <ScoreBadge
                          value={
                            typeof row.workflow_reportability_rate === "number"
                              ? row.workflow_reportability_rate
                              : null
                          }
                          label="reportability"
                        />
                      </Td>
                      <Td>
                        <ScoreBadge
                          value={typeof row.workflow_noise_rate === "number" ? row.workflow_noise_rate : null}
                          label="noise"
                        />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </DataTable>
            ) : (
              <EmptyState
                title="No workflow value leaders"
                description="Run Phase 10 to generate workflow retrospective performance metrics."
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Outcome Quality Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="rounded border border-border p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Alert Noise</p>
              <p className="text-sm">Total outcomes: {String(alertSummary.total_alert_outcomes ?? 0)}</p>
              <p className="text-sm">Ignored: {String(alertSummary.ignored_alerts ?? 0)}</p>
              <p className="text-sm">Resolved noise: {String(alertSummary.resolved_noise_alerts ?? 0)}</p>
              <p className="text-sm">Actionable: {String(alertSummary.actionable_alerts ?? 0)}</p>
            </div>
            <div className="rounded border border-border p-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted">Recommendation Outcomes</p>
              <p className="text-sm">
                Total outcomes: {String(recommendationSummary.total_recommendation_outcomes ?? 0)}
              </p>
              <p className="text-sm">
                Weighted success: {String(recommendationSummary.weighted_success_rate ?? 0)}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
