"use client";

import { FormEvent, useState } from "react";

import { useThreatIntel } from "@/hooks/useThreatIntel";
import { isUuid } from "@/lib/utils";

import { BackendSupportPending } from "@/components/soc/BackendSupportPending";
import { ThreatIntelPanel } from "@/components/soc/ThreatIntelPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ThreatIntelPage() {
  const [campaignInput, setCampaignInput] = useState("");
  const [campaignFilter, setCampaignFilter] = useState<string | undefined>();
  const data = useThreatIntel(campaignFilter);

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

  return (
    <div className="operator-grid">
      <PageHeader
        title="Threat Intelligence Feed"
        description="SOC-style threat context from canonical findings and observations. External feeds are not integrated in this pass."
      />

      <Card>
        <CardHeader>
          <CardTitle>Campaign Filter</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={applyCampaignFilter}>
            <Input
              value={campaignInput}
              onChange={(event) => setCampaignInput(event.target.value)}
              placeholder="campaign UUID (optional)"
            />
            <Button type="submit" variant="secondary">
              Apply Filter
            </Button>
          </form>
        </CardContent>
      </Card>

      <BackendSupportPending
        title="External threat-intel integrations pending"
        description="This feed currently shows only canonical Kai findings and observation-derived intelligence. External source connectors are deferred."
      />

      {data.findingsQueueQuery.isLoading ? <LoadingState label="Loading threat intelligence..." /> : null}
      {data.findingsQueueQuery.isError ? (
        <ErrorState error={data.findingsQueueQuery.error} title="Threat intelligence failed" />
      ) : null}

      {data.findingsQueueQuery.data ? (
        data.findingsQueueQuery.data.items.length > 0 ? (
          <ThreatIntelPanel
            findings={data.findingsQueueQuery.data.items}
            findingDiagnostics={data.findingDiagnostics}
            technologyCounts={data.technologyCounts}
          />
        ) : (
          <EmptyState
            title="No findings in threat feed"
            description="No findings are currently available for the selected filter."
          />
        )
      ) : null}
    </div>
  );
}
