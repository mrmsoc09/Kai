"use client";

import { FormEvent, useMemo, useState } from "react";

import { useAttackSurface } from "@/hooks/useAttackSurface";
import { isUuid } from "@/lib/utils";

import { AttackSurfaceTable } from "@/components/soc/AttackSurfaceTable";
import { BackendSupportPending } from "@/components/soc/BackendSupportPending";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function AttackSurfacePage() {
  const [campaignFilterInput, setCampaignFilterInput] = useState("");
  const [campaignFilter, setCampaignFilter] = useState<string | undefined>();
  const data = useAttackSurface(campaignFilter);

  function onApplyFilter(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignFilterInput.trim();
    if (!trimmed) {
      setCampaignFilter(undefined);
      return;
    }
    if (!isUuid(trimmed)) {
      return;
    }
    setCampaignFilter(trimmed);
  }

  const summary = useMemo(() => {
    const assets = data.assetRows.length;
    const findings = data.findingsQueueQuery.data?.count ?? 0;
    const technologies = new Set(data.assetRows.flatMap((row) => row.technologies)).size;
    return { assets, findings, technologies };
  }, [data.assetRows, data.findingsQueueQuery.data?.count]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Attack Surface Intelligence"
        description="Asset exposure view derived from canonical findings queue and diagnostics context."
      />

      <Card>
        <CardHeader>
          <CardTitle>Campaign Filter</CardTitle>
        </CardHeader>
        <CardContent>
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={onApplyFilter}>
            <Input
              value={campaignFilterInput}
              onChange={(event) => setCampaignFilterInput(event.target.value)}
              placeholder="campaign UUID (optional)"
            />
            <Button type="submit" variant="secondary">
              Apply Filter
            </Button>
          </form>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Assets</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.assets}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Findings in Scope</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.findings}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Technology Hints</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{summary.technologies}</CardContent>
        </Card>
      </div>

      <BackendSupportPending
        title="Derived attack-surface view"
        description="Full canonical asset inventory and drift endpoints are not yet implemented. This table is derived from findings and observation metadata."
      />

      {data.isLoading ? <LoadingState label="Loading attack surface intelligence..." /> : null}

      {data.errors.length > 0 ? (
        <div className="space-y-2">
          {data.errors.map((error, index) => (
            <ErrorState key={`surface-error-${index}`} error={error} title="Attack surface load failed" />
          ))}
        </div>
      ) : null}

      {data.assetRows.length > 0 ? (
        <AttackSurfaceTable rows={data.assetRows} />
      ) : (
        <EmptyState
          title="No asset exposure rows"
          description="No findings-derived assets are currently available for this filter."
        />
      )}
    </div>
  );
}
