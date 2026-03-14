import { FormEvent, useState } from "react";

import { isUuid } from "@/lib/utils";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export function TrackedCampaignSelector({
  trackedCampaignIds,
  onAdd,
  onRemove,
  title = "Tracked Campaigns"
}: {
  trackedCampaignIds: string[];
  onAdd: (campaignId: string) => void;
  onRemove: (campaignId: string) => void;
  title?: string;
}) {
  const [campaignInput, setCampaignInput] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = campaignInput.trim();
    if (!isUuid(trimmed)) {
      return;
    }
    onAdd(trimmed);
    setCampaignInput("");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <form className="grid gap-2 md:grid-cols-[1fr_auto]" onSubmit={onSubmit}>
          <Input
            value={campaignInput}
            onChange={(event) => setCampaignInput(event.target.value)}
            placeholder="campaign UUID"
          />
          <Button type="submit" variant="secondary">
            Track
          </Button>
        </form>
        {trackedCampaignIds.length > 0 ? (
          <div className="flex flex-wrap gap-2">
            {trackedCampaignIds.map((campaignId) => (
              <button
                key={campaignId}
                type="button"
                onClick={() => onRemove(campaignId)}
                className="rounded-md border border-border bg-elevated px-2 py-1 font-mono text-xs text-muted hover:bg-panel"
              >
                remove {campaignId}
              </button>
            ))}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
