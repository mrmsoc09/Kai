import { useState } from "react";

import type { ExportProvider } from "@/lib/api/exports";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export function ExportStageForm({
  onPreview,
  onStage,
  loadingPreview = false,
  loadingStage = false
}: {
  onPreview: (payload: { provider: ExportProvider; actor: string; draftId?: string }) => void;
  onStage: (payload: { provider: ExportProvider; actor: string; draftId?: string }) => void;
  loadingPreview?: boolean;
  loadingStage?: boolean;
}) {
  const [provider, setProvider] = useState<ExportProvider>("hackerone");
  const [actor, setActor] = useState("operator.submission_export");
  const [draftId, setDraftId] = useState("");

  const payload = {
    provider,
    actor,
    draftId: draftId || undefined
  };

  return (
    <div className="space-y-2">
      <div className="grid gap-2 md:grid-cols-3">
        <Select value={provider} onChange={(event) => setProvider(event.target.value as ExportProvider)}>
          <option value="hackerone">hackerone</option>
          <option value="bugcrowd">bugcrowd</option>
          <option value="intigriti">intigriti</option>
        </Select>
        <Input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="actor" />
        <Input
          value={draftId}
          onChange={(event) => setDraftId(event.target.value)}
          placeholder="submission_draft_id (optional)"
        />
      </div>
      <div className="flex flex-wrap gap-2">
        <Button variant="secondary" disabled={loadingPreview} onClick={() => onPreview(payload)}>
          {loadingPreview ? "Previewing..." : "Preview Export Payload"}
        </Button>
        <Button disabled={loadingStage} onClick={() => onStage(payload)}>
          {loadingStage ? "Staging..." : "Stage Export Payload"}
        </Button>
      </div>
    </div>
  );
}
