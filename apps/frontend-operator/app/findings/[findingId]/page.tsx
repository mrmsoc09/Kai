"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { prepareSubmission, reviewFinding } from "@/lib/api/findings";
import { previewExport, stageExport, type ExportProvider } from "@/lib/api/exports";
import { useFinding } from "@/hooks/useFinding";
import { queryKeys } from "@/lib/query-keys";
import type { FindingReviewActionRequest } from "@/lib/types";

import { AuditEventList } from "@/components/data-display/AuditEventList";
import { ArtifactList } from "@/components/data-display/ArtifactList";
import { ErrorState } from "@/components/data-display/ErrorState";
import { EvidenceList } from "@/components/data-display/EvidenceList";
import { LoadingState } from "@/components/data-display/LoadingState";
import { ObservationList } from "@/components/data-display/ObservationList";
import { ExportPreviewCard } from "@/components/exports/ExportPreviewCard";
import { ExportStageForm } from "@/components/forms/ExportStageForm";
import { FindingDiagnosticsPanel } from "@/components/findings/FindingDiagnosticsPanel";
import { FindingMetadataPanel } from "@/components/findings/FindingMetadataPanel";
import { FindingReviewPanel } from "@/components/findings/FindingReviewPanel";
import { FindingSummaryPanel } from "@/components/findings/FindingSummaryPanel";
import { SubmissionPackagePreview } from "@/components/findings/SubmissionPackagePreview";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function FindingDetailPage() {
  const params = useParams<{ findingId: string }>();
  const findingId = params.findingId;
  const queryClient = useQueryClient();
  const findingQuery = useFinding(findingId);

  const [activeDraftId, setActiveDraftId] = useState<string>("");
  const [preparedPackage, setPreparedPackage] = useState<Record<string, unknown> | null>(null);
  const [previewResult, setPreviewResult] = useState<Awaited<ReturnType<typeof previewExport>> | null>(null);
  const [stagedResult, setStagedResult] = useState<Awaited<ReturnType<typeof stageExport>> | null>(null);

  useEffect(() => {
    const firstDraft = findingQuery.data?.submission_drafts[0]?.id;
    if (firstDraft && !activeDraftId) {
      setActiveDraftId(firstDraft);
    }
  }, [activeDraftId, findingQuery.data]);

  const reviewMutation = useMutation({
    mutationFn: (body: FindingReviewActionRequest) => reviewFinding(findingId, body),
    onSuccess: (response) => {
      setActiveDraftId(response.submission_draft_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.detail(findingId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.queue() });
    }
  });

  const prepareMutation = useMutation({
    mutationFn: (reviewerId: string) => prepareSubmission(findingId, reviewerId),
    onSuccess: (response) => {
      setPreparedPackage(response.package_json);
      setActiveDraftId(response.submission_draft_id);
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.detail(findingId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.queue() });
    }
  });

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
    onSuccess: (response) => {
      setStagedResult(response);
      queryClient.invalidateQueries({ queryKey: queryKeys.findings.detail(findingId) });
    }
  });

  if (findingQuery.isLoading) {
    return <LoadingState label="Loading finding workspace..." />;
  }
  if (findingQuery.isError) {
    return <ErrorState error={findingQuery.error} title="Finding diagnostics failed" />;
  }
  if (!findingQuery.data) {
    return <LoadingState label="Waiting for finding state..." />;
  }

  return (
    <div className="operator-grid">
      <PageHeader
        title="Finding Detail / Review Workspace"
        description="Operator review, package preparation, and provider export staging."
      />

      <FindingSummaryPanel finding={findingQuery.data} />
      <FindingDiagnosticsPanel finding={findingQuery.data} />

      <Card>
        <CardHeader>
          <CardTitle>Evidence</CardTitle>
        </CardHeader>
        <CardContent>
          <EvidenceList finding={findingQuery.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Observations</CardTitle>
        </CardHeader>
        <CardContent>
          <ObservationList finding={findingQuery.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Artifacts</CardTitle>
        </CardHeader>
        <CardContent>
          <ArtifactList finding={findingQuery.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Review Actions</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <FindingReviewPanel loading={reviewMutation.isPending} onSubmit={(body) => reviewMutation.mutate(body)} />
          <Button variant="secondary" disabled={prepareMutation.isPending} onClick={() => prepareMutation.mutate("operator.console.reviewer")}>
            {prepareMutation.isPending ? "Preparing..." : "Prepare Submission Package"}
          </Button>
          {reviewMutation.isError ? <ErrorState error={reviewMutation.error} title="Review action failed" /> : null}
          {prepareMutation.isError ? <ErrorState error={prepareMutation.error} title="Package preparation failed" /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Submission Package Preview</CardTitle>
        </CardHeader>
        <CardContent>
          <SubmissionPackagePreview packageJson={preparedPackage} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Provider Export Preview / Staging</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <ExportStageForm
            loadingPreview={previewMutation.isPending}
            loadingStage={stageMutation.isPending}
            onPreview={(payload) =>
              previewMutation.mutate({
                ...payload,
                draftId: payload.draftId || activeDraftId || undefined
              })
            }
            onStage={(payload) =>
              stageMutation.mutate({
                ...payload,
                draftId: payload.draftId || activeDraftId || undefined
              })
            }
          />
          {previewMutation.isError ? <ErrorState error={previewMutation.error} title="Export preview failed" /> : null}
          {stageMutation.isError ? <ErrorState error={stageMutation.error} title="Export staging failed" /> : null}
          <ExportPreviewCard result={previewResult} title="Preview Result" />
          <ExportPreviewCard result={stagedResult} title="Staged Result" />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Finding Metadata</CardTitle>
        </CardHeader>
        <CardContent>
          <FindingMetadataPanel finding={findingQuery.data} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent Audit Events</CardTitle>
        </CardHeader>
        <CardContent>
          <AuditEventList events={findingQuery.data.recent_audit_events} />
        </CardContent>
      </Card>
    </div>
  );
}
