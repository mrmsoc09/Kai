"use client";

import { useMemo, useState } from "react";

import { useCaseQueue } from "@/hooks/useCaseQueue";
import type { CaseStatus } from "@/lib/types";

import { CaseQueueTable } from "@/components/bugbounty/CaseQueueTable";
import { ProgramUuidFilterCard } from "@/components/bugbounty/ProgramUuidFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function CasesPage() {
  const [programInput, setProgramInput] = useState("");
  const [programFilter, setProgramFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [priorityFilter, setPriorityFilter] = useState("ALL");
  const [ownerFilter, setOwnerFilter] = useState("");
  const [searchText, setSearchText] = useState("");

  const queue = useCaseQueue(
    programFilter,
    statusFilter === "ALL" ? undefined : statusFilter,
    priorityFilter === "ALL" ? undefined : priorityFilter,
    ownerFilter.trim() || undefined
  );

  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    const rows = queue.casesQuery.data ?? [];
    if (!term) {
      return rows;
    }
    return rows.filter((row) => {
      const haystack = [row.id, row.title, row.summary, row.owner, row.status, row.priority]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [queue.casesQuery.data, searchText]);

  const unassignedCount = filteredRows.filter((row) => !row.owner).length;
  const readyCount = filteredRows.filter((row) => row.status === "ready_for_report").length;

  return (
    <div className="operator-grid">
      <PageHeader
        title="Analyst Cases"
        description="Durable case-management queue linked to alerts, candidate findings, predictions, recommendations, and report draft workflow."
      />

      <ProgramUuidFilterCard
        inputValue={programInput}
        onInputChange={setProgramInput}
        onApply={setProgramFilter}
        activeProgramId={programFilter}
      />

      <Card>
        <CardHeader>
          <CardTitle>Case Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-4">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All statuses</option>
              <option value="new">new</option>
              <option value="acknowledged">acknowledged</option>
              <option value="triaging">triaging</option>
              <option value="needs_manual_validation">needs_manual_validation</option>
              <option value="ready_for_report">ready_for_report</option>
              <option value="escalated">escalated</option>
              <option value="dismissed">dismissed</option>
              <option value="duplicate">duplicate</option>
              <option value="submitted">submitted</option>
              <option value="closed">closed</option>
            </Select>
            <Select value={priorityFilter} onChange={(event) => setPriorityFilter(event.target.value)}>
              <option value="ALL">All priorities</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="LOW">LOW</option>
            </Select>
            <Input
              value={ownerFilter}
              onChange={(event) => setOwnerFilter(event.target.value)}
              placeholder="owner filter (optional)"
            />
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search case title, summary, owner, id"
            />
          </div>
          <div className="grid gap-2 text-xs text-muted md:grid-cols-3">
            <p>results: {filteredRows.length}</p>
            <p>unassigned: {unassignedCount}</p>
            <p>ready_for_report: {readyCount}</p>
          </div>
        </CardContent>
      </Card>

      {queue.casesQuery.isLoading ? <LoadingState label="Loading cases..." /> : null}
      {queue.casesQuery.isError ? <ErrorState error={queue.casesQuery.error} title="Case queue failed" /> : null}
      {queue.updateCaseMutation.isError ? (
        <ErrorState error={queue.updateCaseMutation.error} title="Case update failed" />
      ) : null}
      {queue.assignCaseMutation.isError ? (
        <ErrorState error={queue.assignCaseMutation.error} title="Case assignment failed" />
      ) : null}

      {queue.casesQuery.data ? (
        filteredRows.length > 0 ? (
          <CaseQueueTable
            rows={filteredRows}
            actionsDisabled={queue.updateCaseMutation.isPending || queue.assignCaseMutation.isPending}
            onStatusChange={(caseId, status) =>
              queue.updateCaseMutation.mutate({ caseId, status: status as CaseStatus })
            }
          />
        ) : (
          <EmptyState title="No cases match filters" description="No cases match the selected filters." />
        )
      ) : null}
    </div>
  );
}
