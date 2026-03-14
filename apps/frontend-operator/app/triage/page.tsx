"use client";

import { useMemo, useState } from "react";

import { useCandidateQueue } from "@/hooks/useCandidateQueue";

import { CandidateQueueTable } from "@/components/bugbounty/CandidateQueueTable";
import { ProgramUuidFilterCard } from "@/components/bugbounty/ProgramUuidFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function TriagePage() {
  const [programInput, setProgramInput] = useState("");
  const [programFilter, setProgramFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [readinessFilter, setReadinessFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const queue = useCandidateQueue(programFilter, statusFilter === "ALL" ? undefined : statusFilter);

  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    const rows = queue.rows;
    return rows.filter((row) => {
      if (readinessFilter !== "ALL" && (row.evidence_readiness_state ?? "UNKNOWN") !== readinessFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [
        row.vulnerability_type,
        row.affected_asset,
        row.affected_endpoint,
        row.recommended_workflow,
        row.recommended_action,
        row.id
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [queue.rows, readinessFilter, searchText]);

  const readyCount = filteredRows.filter((row) => row.ready_for_report).length;
  const needsManualCount = filteredRows.filter((row) => row.status === "needs_manual_validation").length;

  return (
    <div className="operator-grid">
      <PageHeader
        title="Findings Triage Center"
        description="Candidate-finding triage queue with reportability, duplicate-risk, and evidence-completeness scoring."
      />

      <ProgramUuidFilterCard
        inputValue={programInput}
        onInputChange={setProgramInput}
        onApply={setProgramFilter}
        activeProgramId={programFilter}
      />

      <Card>
        <CardHeader>
          <CardTitle>Triage Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-3">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All candidate statuses</option>
              <option value="new">new</option>
              <option value="acknowledged">acknowledged</option>
              <option value="triaged">triaged</option>
              <option value="needs_manual_validation">needs_manual_validation</option>
              <option value="ready_for_report">ready_for_report</option>
              <option value="dismissed">dismissed</option>
              <option value="duplicate_suspected">duplicate_suspected</option>
              <option value="submitted_externally">submitted_externally</option>
            </Select>
            <Select value={readinessFilter} onChange={(event) => setReadinessFilter(event.target.value)}>
              <option value="ALL">All evidence readiness states</option>
              <option value="READY_FOR_REPORT">READY_FOR_REPORT</option>
              <option value="READY_FOR_REVIEW">READY_FOR_REVIEW</option>
              <option value="PARTIAL">PARTIAL</option>
              <option value="INSUFFICIENT">INSUFFICIENT</option>
              <option value="UNKNOWN">UNKNOWN</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search vulnerability, asset, endpoint, workflow"
            />
          </div>
          <div className="grid gap-2 text-xs text-muted md:grid-cols-3">
            <p>results: {filteredRows.length}</p>
            <p>ready_for_report: {readyCount}</p>
            <p>needs_manual_validation: {needsManualCount}</p>
          </div>
        </CardContent>
      </Card>

      {queue.queueQuery.isLoading ? <LoadingState label="Loading triage queue..." /> : null}
      {queue.queueQuery.isError ? <ErrorState error={queue.queueQuery.error} title="Triage queue failed" /> : null}
      {queue.updateStatusMutation.isError ? (
        <ErrorState error={queue.updateStatusMutation.error} title="Candidate update failed" />
      ) : null}
      {queue.generateDraftMutation.isError ? (
        <ErrorState error={queue.generateDraftMutation.error} title="Report draft generation failed" />
      ) : null}

      {queue.queueQuery.data ? (
        filteredRows.length > 0 ? (
          <CandidateQueueTable
            rows={filteredRows}
            onStatusChange={(queueItemId, status) => queue.updateStatusMutation.mutate({ queueItemId, status })}
            onGenerateDraft={(queueItemId) => queue.generateDraftMutation.mutate({ queueItemId })}
            actionsDisabled={queue.updateStatusMutation.isPending || queue.generateDraftMutation.isPending}
          />
        ) : (
          <EmptyState
            title="No candidates match filters"
            description="No queue entries match the current triage filters."
          />
        )
      ) : null}
    </div>
  );
}
