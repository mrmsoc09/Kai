"use client";

import { useMemo, useState } from "react";

import { useBountyPrograms } from "@/hooks/useBountyPrograms";

import { ProgramTable } from "@/components/bugbounty/ProgramTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function ProgramsPage() {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const data = useBountyPrograms();
  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return data.rows.filter((row) => {
      if (statusFilter !== "ALL" && (row.status ?? "UNKNOWN") !== statusFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [row.name, row.platform, row.programId, row.status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [data.rows, searchText, statusFilter]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Bug Bounty Programs"
        description="Program-level operational view with monitored target, schedule, and candidate finding pressure."
      />

      <Card>
        <CardHeader>
          <CardTitle>Programs</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All statuses</option>
              <option value="active">active</option>
              <option value="paused">paused</option>
              <option value="archived">archived</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search name, platform, program id"
            />
          </div>
          <div className="text-xs text-muted">results: {filteredRows.length}</div>
          {data.isLoading ? <LoadingState label="Loading bug bounty programs..." /> : null}
          {data.errors.map((error, index) => (
            <ErrorState key={`programs-error-${index}`} error={error} title="Program data source failed" />
          ))}
          {filteredRows.length > 0 ? (
            <ProgramTable rows={filteredRows} />
          ) : !data.isLoading ? (
            <EmptyState
              title="No programs match filters"
              description="No bug bounty programs match the current status and search filters."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
