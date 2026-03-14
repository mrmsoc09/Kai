"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { startCampaign, scheduleCampaign } from "@/lib/api/campaigns";
import { useCampaigns } from "@/hooks/useCampaigns";
import { useDiagnosticsSummary } from "@/hooks/useDiagnosticsSummary";
import { queryKeys } from "@/lib/query-keys";
import {
  addTrackedCampaignId,
  loadTrackedCampaignIds,
  removeTrackedCampaignId,
  saveTrackedCampaignIds
} from "@/lib/tracked-campaigns";
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

export default function CampaignsPage() {
  const queryClient = useQueryClient();
  const [trackedCampaignIds, setTrackedCampaignIds] = useState<string[]>([]);
  const [trackInput, setTrackInput] = useState("");

  useEffect(() => {
    setTrackedCampaignIds(loadTrackedCampaignIds());
  }, []);

  useEffect(() => {
    saveTrackedCampaignIds(trackedCampaignIds);
  }, [trackedCampaignIds]);

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
      setTrackedCampaignIds((prev) => addTrackedCampaignId(prev, response.campaign_id));
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
    setTrackedCampaignIds((prev) => addTrackedCampaignId(prev, trimmed));
    setTrackInput("");
  }

  const queryErrors = campaignQueries
    .map((query, index) => ({ query, campaignId: trackedCampaignIds[index] ?? "unknown" }))
    .filter((entry) => entry.query.isError)
    .map((entry) => ({ key: entry.campaignId, error: entry.query.error }));

  return (
    <div className="operator-grid">
      <PageHeader
        title="Campaign Dashboard"
        description="Operator control over campaign lifecycle, scheduling, and execution visibility."
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
          <CardTitle>Campaigns</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {campaignRows.length === 0 ? (
            <EmptyState
              title="No tracked campaigns"
              description="Start a campaign or track an existing campaign ID to populate this table."
            />
          ) : (
            <CampaignTable rows={campaignRows} onSchedule={(campaignId) => scheduleMutation.mutate(campaignId)} />
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
                    setTrackedCampaignIds((prev) => removeTrackedCampaignId(prev, campaignId))
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
