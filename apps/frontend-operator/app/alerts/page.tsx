"use client";

import { useMemo, useState } from "react";

import { useAlertCenter } from "@/hooks/useAlertCenter";

import { AlertTable } from "@/components/bugbounty/AlertTable";
import { ProgramUuidFilterCard } from "@/components/bugbounty/ProgramUuidFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function AlertsPage() {
  const [programInput, setProgramInput] = useState("");
  const [programFilter, setProgramFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("OPEN");
  const [severityFilter, setSeverityFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");

  const data = useAlertCenter(
    programFilter,
    statusFilter === "ALL" ? undefined : statusFilter,
    severityFilter === "ALL" ? undefined : severityFilter
  );

  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    if (!term) {
      return data.rows;
    }
    return data.rows.filter((row) => {
      const haystack = [
        row.alert_type,
        row.summary,
        row.reasoning_summary,
        row.id,
        row.analyst_queue_item_id,
        row.prediction_record_id,
        row.recommendation_record_id
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [data.rows, searchText]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Alerting and Notifications"
        description="Canonical Phase 9 alert queue with deduplicated severity-ranked notifications and case creation controls."
      />

      <ProgramUuidFilterCard
        inputValue={programInput}
        onInputChange={setProgramInput}
        onApply={setProgramFilter}
        activeProgramId={programFilter}
      />

      <Card>
        <CardHeader>
          <CardTitle>Alert Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-4">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="OPEN">OPEN</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="SUPPRESSED">SUPPRESSED</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="ALL">ALL</option>
            </Select>
            <Select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}>
              <option value="ALL">All severities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search alert type, summary, linked IDs"
            />
            <Button
              type="button"
              onClick={() => data.syncMutation.mutate()}
              disabled={data.syncMutation.isPending}
            >
              Sync Alerts
            </Button>
          </div>
          <div className="grid gap-2 text-xs text-muted md:grid-cols-4">
            <p>results: {filteredRows.length}</p>
            <p>unresolved: {data.summaryQuery.data?.unresolved_alert_count ?? 0}</p>
            <p>high_severity: {data.summaryQuery.data?.high_severity_alert_count ?? 0}</p>
            <p>open_cases: {data.summaryQuery.data?.open_case_count ?? 0}</p>
          </div>
        </CardContent>
      </Card>

      {data.alertsQuery.isLoading ? <LoadingState label="Loading alerts..." /> : null}
      {data.alertsQuery.isError ? <ErrorState error={data.alertsQuery.error} title="Alert source failed" /> : null}
      {data.summaryQuery.isError ? (
        <ErrorState error={data.summaryQuery.error} title="Alert summary failed" />
      ) : null}
      {data.syncMutation.isError ? (
        <ErrorState error={data.syncMutation.error} title="Alert synchronization failed" />
      ) : null}
      {data.acknowledgeMutation.isError ? (
        <ErrorState error={data.acknowledgeMutation.error} title="Alert acknowledge failed" />
      ) : null}
      {data.resolveMutation.isError ? (
        <ErrorState error={data.resolveMutation.error} title="Alert resolve failed" />
      ) : null}
      {data.createCaseMutation.isError ? (
        <ErrorState error={data.createCaseMutation.error} title="Case creation from alert failed" />
      ) : null}

      {data.alertsQuery.data ? (
        filteredRows.length > 0 ? (
          <AlertTable
            rows={filteredRows}
            onAcknowledge={(alertId) => data.acknowledgeMutation.mutate({ alertId })}
            onResolve={(alertId) => data.resolveMutation.mutate({ alertId })}
            onCreateCase={(alertId) => data.createCaseMutation.mutate({ alertId })}
            actionsDisabled={
              data.syncMutation.isPending ||
              data.acknowledgeMutation.isPending ||
              data.resolveMutation.isPending ||
              data.createCaseMutation.isPending
            }
          />
        ) : (
          <EmptyState
            title="No alerts match filters"
            description="No alerts match the current status, severity, and search filters."
          />
        )
      ) : null}
    </div>
  );
}
