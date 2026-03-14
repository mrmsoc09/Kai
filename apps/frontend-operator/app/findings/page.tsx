"use client";

import { FormEvent, useState } from "react";
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

export default function FindingsPage() {
  const [campaignFilter, setCampaignFilter] = useState("");
  const [findingLookupId, setFindingLookupId] = useState("");
  const [appliedCampaignFilter, setAppliedCampaignFilter] = useState<string | undefined>(undefined);

  const queueQuery = useFindingsQueue(appliedCampaignFilter);

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

  return (
    <div className="operator-grid">
      <PageHeader title="Findings Review Queue" description="Human-in-the-loop review queue for correlated findings." />

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
        </CardContent>
      </Card>

      {queueQuery.isLoading ? <LoadingState label="Loading review queue..." /> : null}
      {queueQuery.isError ? <ErrorState error={queueQuery.error} title="Review queue failed" /> : null}

      {queueQuery.data ? (
        queueQuery.data.items.length > 0 ? (
          <FindingsQueueTable rows={queueQuery.data.items} />
        ) : (
          <EmptyState
            title="No findings in queue"
            description="No findings matched the current review queue filter."
          />
        )
      ) : null}
    </div>
  );
}
