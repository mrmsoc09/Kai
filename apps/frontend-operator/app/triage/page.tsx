"use client";

import { FormEvent, useMemo, useState } from "react";

import { useFindingsQueue } from "@/hooks/useFindingsQueue";
import { isUuid } from "@/lib/utils";

import { FindingsTriagePanel } from "@/components/soc/FindingsTriagePanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function TriagePage() {
  const [campaignInput, setCampaignInput] = useState("");
  const [campaignFilter, setCampaignFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [readinessFilter, setReadinessFilter] = useState("ALL");
  const queueQuery = useFindingsQueue(campaignFilter);

  function applyCampaignFilter(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignInput.trim();
    if (!trimmed) {
      setCampaignFilter(undefined);
      return;
    }
    if (!isUuid(trimmed)) {
      return;
    }
    setCampaignFilter(trimmed);
  }

  const filteredRows = useMemo(() => {
    const rows = queueQuery.data?.items ?? [];
    return rows.filter((row) => {
      if (statusFilter !== "ALL" && row.finding_status !== statusFilter) {
        return false;
      }
      if (readinessFilter !== "ALL" && row.readiness_status !== readinessFilter) {
        return false;
      }
      return true;
    });
  }, [queueQuery.data?.items, readinessFilter, statusFilter]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Findings Triage Center"
        description="Filterable findings review queue with readiness and evidence-first triage context."
      />

      <Card>
        <CardHeader>
          <CardTitle>Triage Filters</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={applyCampaignFilter}>
            <Input
              value={campaignInput}
              onChange={(event) => setCampaignInput(event.target.value)}
              placeholder="campaign UUID (optional)"
            />
            <Button type="submit" variant="secondary">
              Apply Campaign Filter
            </Button>
          </form>
          <div className="grid gap-2 md:grid-cols-2">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All finding statuses</option>
              <option value="NEW">NEW</option>
              <option value="IN_REVIEW">IN_REVIEW</option>
              <option value="HIL_APPROVED">HIL_APPROVED</option>
              <option value="REJECTED">REJECTED</option>
              <option value="DUPLICATE">DUPLICATE</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="SUBMITTED">SUBMITTED</option>
            </Select>
            <Select value={readinessFilter} onChange={(event) => setReadinessFilter(event.target.value)}>
              <option value="ALL">All draft readiness states</option>
              <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
              <option value="READY_FOR_REVIEW">READY_FOR_REVIEW</option>
              <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
              <option value="SUPPRESSED_DUPLICATE">SUPPRESSED_DUPLICATE</option>
              <option value="READY_FOR_SUBMISSION">READY_FOR_SUBMISSION</option>
            </Select>
          </div>
        </CardContent>
      </Card>

      {queueQuery.isLoading ? <LoadingState label="Loading triage queue..." /> : null}
      {queueQuery.isError ? <ErrorState error={queueQuery.error} title="Triage queue failed" /> : null}

      {queueQuery.data ? (
        filteredRows.length > 0 ? (
          <FindingsTriagePanel rows={filteredRows} />
        ) : (
          <EmptyState
            title="No findings match filters"
            description="No queue entries match the current triage filters."
          />
        )
      ) : null}
    </div>
  );
}
