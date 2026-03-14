"use client";

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { bugBountyApi } from "@/lib/api/bug-bounty";
import { queryKeys } from "@/lib/query-keys";
import { useAnalystBriefing } from "@/hooks/useAnalystBriefing";
import type { CandidateQueueStatus } from "@/lib/types";

import { AnalystBriefingPanel } from "@/components/bugbounty/AnalystBriefingPanel";
import { CandidateQueueTable } from "@/components/bugbounty/CandidateQueueTable";
import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function BriefingPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [searchText, setSearchText] = useState("");
  const programId = programIdFilter.trim() || undefined;
  const queryClient = useQueryClient();
  const data = useAnalystBriefing(programId);

  const updateCandidateMutation = useMutation({
    mutationFn: (input: { queueItemId: string; status: CandidateQueueStatus }) =>
      bugBountyApi.updateCandidateQueueItem(input.queueItemId, {
        status: input.status,
        actor: "operator.console.briefing"
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.candidates(programId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.analystBriefing(programId) });
    }
  });

  const reportDraftMutation = useMutation({
    mutationFn: (queueItemId: string) =>
      bugBountyApi.generateCandidateReportDraft(queueItemId, {
        actor: "operator.console.briefing",
        analyst_notes: "Generated from analyst briefing cockpit."
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.bugBounty.candidates(programId) });
    }
  });

  const queueRows = useMemo(() => {
    const rows = (data.queueQuery.data ?? []).slice(0, 200);
    const term = searchText.trim().toLowerCase();
    if (!term) {
      return rows.slice(0, 50);
    }
    return rows
      .filter((row) => {
        const haystack = [
          row.id,
          row.vulnerability_type,
          row.affected_asset,
          row.affected_endpoint,
          row.status
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        return haystack.includes(term);
      })
      .slice(0, 50);
  }, [data.queueQuery.data, searchText]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Analyst Briefing and Report Drafts"
        description="Decision-support view for triage escalation, report readiness, and report-draft generation."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

      {(data.briefingQuery.isLoading || data.analystSupportQuery.isLoading) ? (
        <LoadingState label="Loading analyst briefing..." />
      ) : null}
      {data.briefingQuery.isError ? (
        <ErrorState error={data.briefingQuery.error} title="Analyst briefing failed" />
      ) : null}
      {data.analystSupportQuery.isError ? (
        <ErrorState error={data.analystSupportQuery.error} title="Phase 7 analyst support failed" />
      ) : null}

      <AnalystBriefingPanel briefing={data.briefingQuery.data} phase7Support={data.analystSupportQuery.data} />

      <Card>
        <CardHeader>
          <CardTitle>Candidate Queue for Report Drafting</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="search candidate id, vulnerability, asset, endpoint, status"
          />
          <div className="text-xs text-muted">results (top 50 shown): {queueRows.length}</div>
          {data.queueQuery.isLoading ? <LoadingState label="Loading candidate queue..." /> : null}
          {data.queueQuery.isError ? <ErrorState error={data.queueQuery.error} title="Candidate queue failed" /> : null}
          {updateCandidateMutation.isError ? (
            <ErrorState error={updateCandidateMutation.error} title="Candidate status update failed" />
          ) : null}
          {reportDraftMutation.isError ? (
            <ErrorState error={reportDraftMutation.error} title="Report draft generation failed" />
          ) : null}
          <CandidateQueueTable
            rows={queueRows}
            onStatusChange={(queueItemId, status) => updateCandidateMutation.mutate({ queueItemId, status })}
            onGenerateDraft={(queueItemId) => reportDraftMutation.mutate(queueItemId)}
            actionsDisabled={updateCandidateMutation.isPending || reportDraftMutation.isPending}
          />
        </CardContent>
      </Card>
    </div>
  );
}
