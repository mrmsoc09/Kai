"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { useFindingsQueue } from "@/hooks/useFindingsQueue";
import { isUuid } from "@/lib/utils";

import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { FindingsQueueTable } from "@/components/findings/FindingsQueueTable";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function FindingsPage() {
  const [campaignFilter, setCampaignFilter] = useState("");
  const [findingLookupId, setFindingLookupId] = useState("");
  const [appliedCampaignFilter, setAppliedCampaignFilter] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [readinessFilter, setReadinessFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");

  const queueQuery = useFindingsQueue(appliedCampaignFilter);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const value = new URLSearchParams(window.location.search).get("campaign_id") ?? "";
    if (isUuid(value)) {
      setCampaignFilter(value);
      setAppliedCampaignFilter(value);
    }
  }, []);

  function applyFilter(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignFilter.trim();
    if (!trimmed) {
      setAppliedCampaignFilter(undefined);
      return;
    }
    if (!isUuid(trimmed)) {
      return;
    }
    setAppliedCampaignFilter(trimmed);
  }

  const filteredRows = useMemo(() => {
    const loweredSearch = searchText.trim().toLowerCase();
    return (queueQuery.data?.items ?? []).filter((row) => {
      if (statusFilter !== "ALL" && row.finding_status !== statusFilter) {
        return false;
      }
      if (readinessFilter !== "ALL" && row.readiness_status !== readinessFilter) {
        return false;
      }
      if (!loweredSearch) {
        return true;
      }
      const haystack = [row.title, row.program, row.asset, row.finding_id, row.campaign_id]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(loweredSearch);
    });
  }, [queueQuery.data?.items, readinessFilter, searchText, statusFilter]);

  return (
    <div className="operator-grid">
      <PageHeader title="Findings Review Queue" description="Human-in-the-loop queue with mission, readiness, and status filters." />

      <Card>
        <CardContent className="space-y-3">
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={applyFilter}>
            <Input
              value={campaignFilter}
              onChange={(event) => setCampaignFilter(event.target.value)}
              placeholder="campaign UUID (optional)"
            />
            <Button type="submit" variant="secondary">
              Apply Campaign Filter
            </Button>
          </form>
          <div className="grid gap-2 md:grid-cols-3">
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="ALL">All finding states</option>
              <option value="NEW">NEW</option>
              <option value="IN_REVIEW">IN_REVIEW</option>
              <option value="HIL_APPROVED">HIL_APPROVED</option>
              <option value="REJECTED">REJECTED</option>
              <option value="DUPLICATE">DUPLICATE</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="SUBMITTED">SUBMITTED</option>
            </Select>
            <Select value={readinessFilter} onChange={(event) => setReadinessFilter(event.target.value)}>
              <option value="ALL">All readiness states</option>
              <option value="READY_FOR_SUBMISSION">READY_FOR_SUBMISSION</option>
              <option value="READY">READY</option>
              <option value="INSUFFICIENT_EVIDENCE">INSUFFICIENT_EVIDENCE</option>
              <option value="BLOCKED">BLOCKED</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search title, asset, ids, mission"
            />
          </div>
          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <Input
              value={findingLookupId}
              onChange={(event) => setFindingLookupId(event.target.value)}
              placeholder="finding UUID to open directly"
            />
            {isUuid(findingLookupId.trim()) ? (
              <Link
                href={`/findings/${findingLookupId.trim()}`}
                className="inline-flex h-9 items-center justify-center rounded-md border border-border px-4 text-sm text-foreground hover:bg-elevated"
              >
                Open Finding
              </Link>
            ) : (
              <Button type="button" variant="outline" disabled>
                Open Finding
              </Button>
            )}
          </div>
          <p className="text-xs text-muted">results: {filteredRows.length}</p>
        </CardContent>
      </Card>

      {queueQuery.isLoading ? <LoadingState label="Loading review queue..." /> : null}
      {queueQuery.isError ? <ErrorState error={queueQuery.error} title="Review queue failed" /> : null}

      {queueQuery.data ? (
        filteredRows.length > 0 ? (
          <FindingsQueueTable rows={filteredRows} />
        ) : (
          <EmptyState
            title="No findings in queue"
            description="No findings matched the current mission, status, readiness, or search filters."
          />
        )
      ) : null}
    </div>
  );
}
