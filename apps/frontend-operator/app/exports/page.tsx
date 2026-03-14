"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { previewExport, stageExport, type ExportProvider } from "@/lib/api/exports";
import { isUuid } from "@/lib/utils";

import { ErrorState } from "@/components/data-display/ErrorState";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ExportPreviewCard } from "@/components/exports/ExportPreviewCard";
import { ExportStageForm } from "@/components/forms/ExportStageForm";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export default function ExportsPage() {
  const [findingId, setFindingId] = useState("");
  const [previewResult, setPreviewResult] = useState<Awaited<ReturnType<typeof previewExport>> | null>(null);
  const [stagedResult, setStagedResult] = useState<Awaited<ReturnType<typeof stageExport>> | null>(null);

  const previewMutation = useMutation({
    mutationFn: (payload: { provider: ExportProvider; actor: string; draftId?: string }) =>
      previewExport(findingId, payload.provider, {
        actor: `${payload.actor}.preview`,
        submissionDraftId: payload.draftId
      }),
    onSuccess: (response) => setPreviewResult(response)
  });

  const stageMutation = useMutation({
    mutationFn: (payload: { provider: ExportProvider; actor: string; draftId?: string }) =>
      stageExport(findingId, payload.provider, {
        actor: payload.actor,
        submission_draft_id: payload.draftId
      }),
    onSuccess: (response) => setStagedResult(response)
  });

  return (
    <div className="operator-grid">
      <PageHeader
        title="Exports"
        description="Provider payload preview and staging for approved findings."
      />

      <Card>
        <CardHeader>
          <CardTitle>Finding Selection</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            value={findingId}
            onChange={(event) => setFindingId(event.target.value.trim())}
            placeholder="finding UUID"
          />
          {isUuid(findingId) ? (
            <ExportStageForm
              loadingPreview={previewMutation.isPending}
              loadingStage={stageMutation.isPending}
              onPreview={(payload) => previewMutation.mutate(payload)}
              onStage={(payload) => stageMutation.mutate(payload)}
            />
          ) : (
            <EmptyState
              title="Finding required"
              description="Enter a valid finding UUID to preview or stage export payloads."
            />
          )}
        </CardContent>
      </Card>

      {previewMutation.isError ? <ErrorState error={previewMutation.error} title="Export preview failed" /> : null}
      {stageMutation.isError ? <ErrorState error={stageMutation.error} title="Export staging failed" /> : null}

      <ExportPreviewCard result={previewResult} title="Preview Result" />
      <ExportPreviewCard result={stagedResult} title="Staged Result" />
    </div>
  );
}
