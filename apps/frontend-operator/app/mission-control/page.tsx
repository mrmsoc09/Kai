"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { useCampaigns } from "@/hooks/useCampaigns";
import { useTrackedCampaignIds } from "@/hooks/useTrackedCampaignIds";
import { isUuid } from "@/lib/utils";

import { EmptyState } from "@/components/data-display/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function MissionControlPage() {
  const [missionInput, setMissionInput] = useState("");
  const { trackedCampaignIds, addCampaignId, removeCampaignId } = useTrackedCampaignIds();
  const campaignQueries = useCampaigns(trackedCampaignIds);

  function onTrackMission(event: FormEvent) {
    event.preventDefault();
    const trimmed = missionInput.trim();
    if (!isUuid(trimmed)) {
      return;
    }
    addCampaignId(trimmed);
    setMissionInput("");
  }

  const missionRows = campaignQueries
    .filter((query) => query.isSuccess)
    .map((query) => query.data.campaign)
    .sort((a, b) => (b.updated_at ?? b.created_at ?? "").localeCompare(a.updated_at ?? a.created_at ?? ""));

  return (
    <div className="operator-grid">
      <PageHeader
        title="Mission Control"
        description="Select a mission to open the central cockpit with execution, approvals, evidence, findings, and terminal linkage."
      />

      <Card>
        <CardHeader>
          <CardTitle>Mission Selection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={onTrackMission}>
            <Input
              value={missionInput}
              onChange={(event) => setMissionInput(event.target.value)}
              placeholder="mission UUID"
            />
            <Button type="submit" variant="secondary">
              Track Mission
            </Button>
          </form>
          <p className="text-xs text-muted">
            Mission Control uses campaign IDs as mission IDs in the current backend contract.
          </p>
        </CardContent>
      </Card>

      {missionRows.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Tracked Missions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {missionRows.map((mission) => (
              <div
                key={mission.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-elevated p-2"
              >
                <div className="space-y-1">
                  <p className="font-mono text-xs text-foreground">{mission.id}</p>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={mission.status} />
                    <span className="text-xs text-muted">program: {mission.program_id}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Link
                    href={`/mission-control/${mission.id}`}
                    className="inline-flex h-8 items-center justify-center rounded-md border border-border px-3 text-xs font-medium text-foreground hover:bg-panel"
                  >
                    Open
                  </Link>
                  <Button size="sm" variant="outline" onClick={() => removeCampaignId(mission.id)}>
                    Untrack
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      ) : (
        <EmptyState
          title="No tracked missions"
          description="Track or start a mission from the Missions page, then open Mission Control."
        />
      )}
    </div>
  );
}
