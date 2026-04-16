"use client";

import { FormEvent, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { startCampaign, scheduleCampaign } from "@/lib/api/campaigns";
import { useCampaigns } from "@/hooks/useCampaigns";
import { useDiagnosticsSummary } from "@/hooks/useDiagnosticsSummary";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";
import { queryKeys } from "@/lib/query-keys";
import { isUuid } from "@/lib/utils";
import type { CampaignStartRequest } from "@/lib/types";

import { CampaignTable } from "@/components/campaigns/CampaignTable";
import { StartCampaignDialog } from "@/components/campaigns/StartCampaignDialog";
import { DiagnosticsSummaryCards } from "@/components/diagnostics/DiagnosticsSummaryCards";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function CampaignsPage() {
  const queryClient = useQueryClient();
  const { trackedCampaignIds, addCampaignId, removeCampaignId } = useTrackedCampaignIds();
  const [trackInput, setTrackInput] = useState("");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");

  const diagnosticsSummaryQuery = useDiagnosticsSummary();
  const campaignQueries = useCampaigns(trackedCampaignIds);

  const campaignRows = useMemo(
    () =>
      campaignQueries
        .filter((query) => query.isSuccess)
        .map((query) => query.data)
        .map((status) => ({
          ...status.campaign,
          branch_count: status.branches.length,
          phase_job_count: status.phase_jobs.length
        })),
    [campaignQueries]
  );
  const filteredCampaignRows = useMemo(() => {
    const loweredSearch = searchText.trim().toLowerCase();
    return campaignRows.filter((row) => {
      if (statusFilter !== "ALL" && row.status !== statusFilter) {
        return false;
      }
      if (!loweredSearch) {
        return true;
      }
      const haystack = [row.id, row.program_id, row.status]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(loweredSearch);
    });
  }, [campaignRows, searchText, statusFilter]);

  const scheduleMutation = useMutation({
    mutationFn: (campaignId: string) => scheduleCampaign(campaignId),
    onSuccess: (_response, campaignId) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(campaignId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
    }
  });

  const startCampaignMutation = useMutation({
    mutationFn: (body: CampaignStartRequest) => startCampaign(body),
    onSuccess: (response) => {
      addCampaignId(response.campaign_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.diagnostics.summary() });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.detail(response.campaign_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.campaigns.diagnostics(response.campaign_id) });
    }
  });

  function onTrackCampaign(event: FormEvent) {
    event.preventDefault();
    const trimmed = trackInput.trim();
    if (!isUuid(trimmed)) {
      return;
    }
    addCampaignId(trimmed);
    setTrackInput("");
  }

  const queryErrors = campaignQueries
    .map((query, index) => ({ query, campaignId: trackedCampaignIds[index] ?? "unknown" }))
    .filter((entry) => entry.query.isError)
    .map((entry) => ({ key: entry.campaignId, error: entry.query.error }));

  return (
    <div className="operator-grid">
      <PageHeader
        title="Missions"
        description="Mission lifecycle operations for scheduling, execution, approvals, and human decision gates."
      />

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <StartCampaignDialog
            onSubmit={(body) => startCampaignMutation.mutate(body)}
            loading={startCampaignMutation.isPending}
            error={startCampaignMutation.error}
          />
        </div>
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Track Existing Campaign</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="flex gap-2" onSubmit={onTrackCampaign}>
              <Input
                value={trackInput}
                onChange={(event) => setTrackInput(event.target.value)}
                placeholder="campaign UUID"
              />
              <Button type="submit" variant="secondary">
                Track
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Diagnostics Summary</CardTitle>
        </CardHeader>
        <CardContent>
          {diagnosticsSummaryQuery.isLoading ? <LoadingState label="Loading diagnostics summary..." /> : null}
          {diagnosticsSummaryQuery.isError ? (
            <ErrorState error={diagnosticsSummaryQuery.error} title="Diagnostics summary failed" />
          ) : null}
          {diagnosticsSummaryQuery.data ? <DiagnosticsSummaryCards summary={diagnosticsSummaryQuery.data} /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mission Queue</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All statuses</option>
              <option value="CREATED">CREATED</option>
              <option value="READY">READY</option>
              <option value="RUNNING">RUNNING</option>
              <option value="WAITING_APPROVAL">WAITING_APPROVAL</option>
              <option value="BLOCKED">BLOCKED</option>
              <option value="FAILED">FAILED</option>
              <option value="COMPLETED">COMPLETED</option>
              <option value="CANCELED">CANCELED</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search mission id, program id, status"
            />
          </div>
          <p className="text-xs text-muted">results: {filteredCampaignRows.length}</p>
          {filteredCampaignRows.length === 0 ? (
            <EmptyState
              title="No missions match current filters"
              description="Start a mission or adjust status/search filters."
            />
          ) : (
            <CampaignTable rows={filteredCampaignRows} onSchedule={(campaignId) => scheduleMutation.mutate(campaignId)} />
          )}

          {scheduleMutation.isError ? (
            <ErrorState error={scheduleMutation.error} title="Re-schedule failed" />
          ) : null}

          {queryErrors.length > 0 ? (
            <div className="space-y-2">
              {queryErrors.map(({ key, error }) => (
                <ErrorState key={key} error={error} title={`Campaign load failed (${key})`} />
              ))}
            </div>
          ) : null}

          {trackedCampaignIds.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {trackedCampaignIds.map((campaignId) => (
                <button
                  key={campaignId}
                  onClick={() =>
                    removeCampaignId(campaignId)
                  }
                  className="rounded-md border border-border bg-elevated px-2 py-1 font-mono text-xs text-muted hover:bg-panel"
                  type="button"
                >
                  remove {campaignId}
                </button>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
