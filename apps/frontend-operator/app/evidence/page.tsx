"use client";

import { FormEvent, useMemo, useState } from "react";

import { useFindingsQueue } from "@/hooks/useFindingsQueue";
import { isUuid } from "@/lib/utils";

import { BackendSupportPending } from "@/components/soc/BackendSupportPending";
import { EvidenceRepositoryTable } from "@/components/soc/EvidenceRepositoryTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function EvidencePage() {
  const [campaignInput, setCampaignInput] = useState("");
  const [campaignFilter, setCampaignFilter] = useState<string | undefined>();
  const [providerFilter, setProviderFilter] = useState("ALL");
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
    if (providerFilter === "ALL") {
      return rows;
    }
    return rows.filter((item) =>
      item.observation_summary.items.some((obs) => (obs.summary ?? "").toLowerCase().includes(providerFilter.toLowerCase()))
    );
  }, [providerFilter, queueQuery.data?.items]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Evidence and Artifact Repository"
        description="Cross-finding evidence visibility using canonical diagnostics and review queue aggregates."
      />

      <Card>
        <CardHeader>
          <CardTitle>Repository Filters</CardTitle>
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
          <Select value={providerFilter} onChange={(event) => setProviderFilter(event.target.value)}>
            <option value="ALL">All provider context</option>
            <option value="hackerone">hackerone</option>
            <option value="bugcrowd">bugcrowd</option>
            <option value="intigriti">intigriti</option>
          </Select>
        </CardContent>
      </Card>

      <BackendSupportPending
        title="Artifact repository API is partial"
        description="A canonical artifact/evidence listing endpoint is pending. This repository view is derived from finding review queue and diagnostics counts."
      />

      {queueQuery.isLoading ? <LoadingState label="Loading evidence repository..." /> : null}
      {queueQuery.isError ? <ErrorState error={queueQuery.error} title="Evidence repository failed" /> : null}

      {queueQuery.data ? (
        filteredRows.length > 0 ? (
          <EvidenceRepositoryTable rows={filteredRows} />
        ) : (
          <EmptyState
            title="No evidence rows"
            description="No findings currently match evidence repository filters."
          />
        )
      ) : null}
    </div>
  );
}
