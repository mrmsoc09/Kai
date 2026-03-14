"use client";

import { useMemo, useState } from "react";

import { useMonitoredTargets } from "@/hooks/useMonitoredTargets";

import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { MonitoredTargetTable } from "@/components/bugbounty/MonitoredTargetTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function TargetsPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [readinessFilter, setReadinessFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const data = useMonitoredTargets(programIdFilter.trim() || undefined);
  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return data.rows.filter((row) => {
      if (statusFilter !== "ALL" && (row.monitoringStatus ?? "UNKNOWN") !== statusFilter) {
        return false;
      }
      if (readinessFilter !== "ALL" && (row.readinessStatus ?? "UNKNOWN") !== readinessFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [row.target, row.targetType, row.targetId, row.programId, row.nextAction]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [data.rows, readinessFilter, searchText, statusFilter]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Monitored Targets"
        description="Target inventory with readiness status, yield scoring, and follow-up recommendations."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

      <Card>
        <CardHeader>
          <CardTitle>Target Inventory</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-3">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All monitoring statuses</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="PAUSED">PAUSED</option>
              <option value="DISABLED">DISABLED</option>
              <option value="ERROR">ERROR</option>
              <option value="UNKNOWN">UNKNOWN</option>
            </Select>
            <Select value={readinessFilter} onChange={(event) => setReadinessFilter(event.target.value)}>
              <option value="ALL">All readiness states</option>
              <option value="READY">READY</option>
              <option value="BLOCKED_BY_SCOPE">BLOCKED_BY_SCOPE</option>
              <option value="BLOCKED_BY_PROGRAM_POLICY">BLOCKED_BY_PROGRAM_POLICY</option>
              <option value="BLOCKED_BY_HEALTH">BLOCKED_BY_HEALTH</option>
              <option value="BLOCKED_BY_CONFIG">BLOCKED_BY_CONFIG</option>
              <option value="BLOCKED_BY_COOLDOWN">BLOCKED_BY_COOLDOWN</option>
              <option value="BLOCKED_BY_DISABLED_TARGET">BLOCKED_BY_DISABLED_TARGET</option>
              <option value="BLOCKED_BY_SAFETY_POLICY">BLOCKED_BY_SAFETY_POLICY</option>
              <option value="UNKNOWN">UNKNOWN</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search target, type, action, ids"
            />
          </div>
          <div className="text-xs text-muted">results: {filteredRows.length}</div>
          {data.isLoading ? <LoadingState label="Loading monitored targets..." /> : null}
          {data.errors.map((error, index) => (
            <ErrorState key={`targets-error-${index}`} error={error} title="Monitored target source failed" />
          ))}
          {filteredRows.length > 0 ? (
            <MonitoredTargetTable rows={filteredRows} />
          ) : !data.isLoading ? (
            <EmptyState
              title="No targets match filters"
              description="No monitored targets match the selected status, readiness, and search filters."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
