"use client";

import { useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useOpportunityRankings } from "@/hooks/useOpportunityRankings";
import { useScanQueue } from "@/hooks/useScanQueue";
import { getScanSuggestions } from "@/lib/api/credentials";
import { queueBatch } from "@/lib/api/scans";
import { queryKeys } from "@/lib/query-keys";

import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { OpportunityRankingTable } from "@/components/bugbounty/OpportunityRankingTable";
import { ScanQueuePanel } from "@/components/scan/ScanQueuePanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { OpportunityRankingRow } from "@/hooks/useOpportunityRankings";

export default function OpportunitiesPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [subjectTypeFilter, setSubjectTypeFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const [accountReadyOnly, setAccountReadyOnly] = useState(true);
  const [launchingQueued, setLaunchingQueued] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);
  const queuePanelRef = useRef<HTMLDivElement | null>(null);
  const data = useOpportunityRankings(programIdFilter.trim() || undefined);
  const { items, addItem, removeItem, reorder, updateItem, clearCompleted } = useScanQueue();
  const scanSuggestionsQuery = useQuery({
    queryKey: queryKeys.credentials.scanSuggestions(50),
    queryFn: ({ signal }) => getScanSuggestions(50, signal),
    staleTime: 120_000,
  });

  const accountReadyIds = useMemo(() => {
    return new Set((scanSuggestionsQuery.data?.items ?? []).map((item) => item.opportunity_id));
  }, [scanSuggestionsQuery.data?.items]);
  const programs = data.programsQuery?.data ?? [];
  const programById = useMemo(() => {
    return new Map(programs.map((program) => [program.id, program] as const));
  }, [programs]);
  const accountReadySuggestions = scanSuggestionsQuery.data?.items ?? [];
  const suggestionById = useMemo(() => {
    return new Map(accountReadySuggestions.map((suggestion) => [suggestion.opportunity_id, suggestion] as const));
  }, [accountReadySuggestions]);
  const accountReadySuggestionRows = useMemo<OpportunityRankingRow[]>(() => {
    return accountReadySuggestions.map((item) => {
      const rankedRow = data.rows.find((row) => row.programId === item.opportunity_id || row.id === item.opportunity_id);
      if (rankedRow) {
        return rankedRow;
      }
      const program = programById.get(item.opportunity_id);
      const subjectKey = program?.handle ?? program?.program_key ?? program?.name ?? item.opportunity_id;
      return {
        id: item.opportunity_id,
        programId: item.opportunity_id,
        scopeTargetId: null,
        subjectType: "PROGRAM",
        subjectKey,
        selectionScore: item.score,
        priorityRank: null,
        confidenceScore: null,
        duplicateRiskScore: null,
        evidenceCompletenessScore: null,
        recommendedWorkflow: "phase7_prediction",
        recommendedAction: "add_to_queue",
        reasoningSummary: item.reasons.join(" • "),
      };
    });
  }, [accountReadySuggestions, data.rows, programById]);
  const queuedAccountReadyCount = useMemo(() => {
    const visibleIds = new Set(accountReadySuggestionRows.map((row) => row.id));
    return items.filter((item) => visibleIds.has(item.opportunityId)).length;
  }, [accountReadySuggestionRows, items]);
  const visibleAccountReadyCount = accountReadySuggestionRows.length;

  const enforceAccountReady = accountReadyOnly && scanSuggestionsQuery.isSuccess;

  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return data.rows.filter((row) => {
      if (enforceAccountReady && !accountReadyIds.has(row.id)) {
        return false;
      }
      if (subjectTypeFilter !== "ALL" && (row.subjectType ?? "UNKNOWN") !== subjectTypeFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [
        row.subjectType,
        row.subjectKey,
        row.programId,
        row.scopeTargetId,
        row.recommendedWorkflow,
        row.recommendedAction
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [accountReadyIds, data.rows, enforceAccountReady, searchText, subjectTypeFilter]);

  const handleAddToQueue = (rows: OpportunityRankingRow[]) => {
    for (const row of rows) {
      addItem(row);
    }
  };

  const handleAddVisibleToQueue = () => {
    handleAddToQueue(accountReadySuggestionRows.slice(0, 50));
  };

  const handleAddAndLaunchVisible = async () => {
    handleAddVisibleToQueue();
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve());
    });
    await handleLaunchQueued();
  };

  const handleSelectProgram = (programId: string) => {
    setProgramIdFilter(programId);
    setSearchText("");
  };

  const handleLaunchQueued = async () => {
    const queued = items.filter((item) => item.status === "queued");
    if (queued.length === 0) {
      setLaunchError("No queued items to launch.");
      return;
    }
    setLaunchingQueued(true);
    setLaunchError(null);
    try {
      const response = await queueBatch({
        items: queued.map((item) => ({
          program_id: item.programId,
          scope_target_id: item.scopeTargetId ?? null,
          subject_key: item.subjectKey,
          subject_type: item.subjectType,
          recommended_workflow: item.recommendedWorkflow ?? null,
        })),
        force: true,
        safe_mode: true,
      });
      for (const dispatched of response.queued) {
        const localItem = queued[dispatched.item_index];
        if (localItem) {
          updateItem(localItem.id, {
            status: "running",
            campaignId: dispatched.schedule_job_id,
          });
        }
      }
      if (response.errors.length > 0) {
        setLaunchError(
          `${response.queued.length} dispatched, ${response.errors.length} failed: ` +
          response.errors.map((e) => e.error).join("; ")
        );
      }
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setLaunchingQueued(false);
    }
  };

  return (
    <div className="operator-grid">
      <PageHeader
        title="Opportunity Rankings"
        description="Phase 7 opportunity scoring with explainable reasoning and next workflow recommendations."
      />

      <Card>
        <CardHeader>
          <CardTitle>Queue Workflow</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted">
          <div className="grid gap-2 md:grid-cols-3">
            <div className="rounded-md border border-border bg-panel px-3 py-2">
              <div className="text-xs uppercase tracking-wide text-warning">1. Account-ready</div>
              <div className="mt-1">Only show opportunities already covered by Vault / Proton account data.</div>
            </div>
            <div className="rounded-md border border-border bg-panel px-3 py-2">
              <div className="text-xs uppercase tracking-wide text-warning">2. Queue</div>
              <div className="mt-1">Select rows and click <span className="text-foreground">Add to Queue</span> to stage scans.</div>
            </div>
            <div className="rounded-md border border-border bg-panel px-3 py-2">
              <div className="text-xs uppercase tracking-wide text-warning">3. Launch</div>
              <div className="mt-1">Use <span className="text-foreground">Start queued scans</span> to dispatch the current queue.</div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant={accountReadyOnly ? "default" : "outline"}
              size="sm"
              onClick={() => setAccountReadyOnly((current) => !current)}
            >
              {accountReadyOnly ? "Account-ready only" : "Show all opportunities"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleAddVisibleToQueue()}
              disabled={visibleAccountReadyCount === 0}
              title="Add every visible account-ready opportunity to the scan queue"
            >
              Add all visible to Queue ({visibleAccountReadyCount})
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => queuePanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
            >
              Jump to Queue
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => void handleAddAndLaunchVisible()}
              disabled={launchingQueued}
            >
              {launchingQueued ? "Launching..." : `Add visible + launch (${visibleAccountReadyCount})`}
            </Button>
          </div>
          {launchError && <div className="text-xs text-danger">{launchError}</div>}
          <div className="text-xs text-muted">
            Account-ready suggestions: {scanSuggestionsQuery.data?.items.length ?? 0} / 50 available · {queuedAccountReadyCount} already queued.
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Account-Ready Opportunities</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">
            These are the opportunities with matching hunter-account coverage already available in Vault or the imported Proton CSV data.
            Queue them directly, then jump to the scan queue to launch the dispatch.
          </p>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <span className="rounded-full border border-border bg-elevated px-2 py-0.5 uppercase tracking-wide text-warning">
              {visibleAccountReadyCount} visible
            </span>
            <span className="rounded-full border border-border bg-elevated px-2 py-0.5 uppercase tracking-wide text-warning">
              {queuedAccountReadyCount} queued
            </span>
            <span className="rounded-full border border-border bg-elevated px-2 py-0.5 uppercase tracking-wide text-warning">
              50 max
            </span>
          </div>
          {scanSuggestionsQuery.isLoading ? (
            <LoadingState label="Loading account-ready opportunity suggestions..." />
          ) : accountReadySuggestionRows.length > 0 ? (
            <div className="grid gap-2">
              {accountReadySuggestionRows.slice(0, 50).map((item) => {
                const program = programs.find((program) => program.id === item.programId);
                return (
                  <div
                    key={item.id}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border bg-panel px-3 py-2"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="truncate text-sm font-medium text-foreground">
                          {item.subjectType}:{item.subjectKey}
                        </p>
                        <span className="rounded-full border border-border bg-elevated px-2 py-0.5 text-[11px] uppercase tracking-wide text-warning">
                          account ready
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted">
                        score {item.selectionScore} · {item.reasoningSummary}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        Accounts: {suggestionById.get(item.programId)?.matching_accounts.join(", ") ?? "n/a"}
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => program && handleSelectProgram(program.id)}
                        disabled={!program}
                      >
                        Open program
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => handleAddToQueue([item])}
                      >
                        Add to Queue
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState
              title="No account-ready opportunities"
              description="Import more hunter accounts or sync the Proton CSV data to populate the queue."
            />
          )}
        </CardContent>
      </Card>

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

      <Card>
        <CardHeader>
          <CardTitle>Ranked Opportunities</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Select value={subjectTypeFilter} onChange={(event) => setSubjectTypeFilter(event.target.value)}>
              <option value="ALL">All subject types</option>
              <option value="PROGRAM">PROGRAM</option>
              <option value="TARGET">TARGET</option>
              <option value="CANDIDATE">CANDIDATE</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search subject, ids, workflow, actions"
            />
          </div>
          <div className="text-xs text-muted">results: {filteredRows.length}</div>
          {data.rankingsQuery.isLoading ? <LoadingState label="Loading opportunity rankings..." /> : null}
          {data.rankingsQuery.isError ? (
            <ErrorState error={data.rankingsQuery.error} title="Opportunity rankings failed" />
          ) : null}
          {data.recommendationsQuery.isError ? (
            <ErrorState error={data.recommendationsQuery.error} title="Recommendations source failed" />
          ) : null}
          {data.predictionsQuery.isError ? (
            <ErrorState error={data.predictionsQuery.error} title="Predictions source failed" />
          ) : null}
          {data.programsQuery?.isError ? (
            <ErrorState error={data.programsQuery.error} title="Program source failed" />
          ) : null}
          {filteredRows.length > 0 ? (
            <OpportunityRankingTable rows={filteredRows} onAddToQueue={handleAddToQueue} />
          ) : !data.rankingsQuery.isLoading ? (
            <EmptyState
              title="No opportunities match filters"
              description="No opportunity rankings match the selected subject type and search filters."
            />
          ) : null}
        </CardContent>
      </Card>

      <div ref={queuePanelRef}>
        <Card>
        <CardHeader>
          <CardTitle>Scan Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <ScanQueuePanel
            items={items}
            onReorder={reorder}
            onRemove={removeItem}
            onUpdateItem={updateItem}
            onClearCompleted={clearCompleted}
          />
        </CardContent>
        </Card>
      </div>
    </div>
  );
}
