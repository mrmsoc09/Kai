"use client";

import { useParams } from "next/navigation";

import { useCaseDetail } from "@/hooks/useCaseDetail";

import { CaseDetailPanel } from "@/components/bugbounty/CaseDetailPanel";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";

export default function CaseDetailPage() {
  const params = useParams<{ caseId: string }>();
  const caseId = params.caseId;
  const data = useCaseDetail(caseId);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Case Detail"
        description="Single-case operational workspace with lifecycle controls, assignment, and analyst note history."
      />

      {data.caseQuery.isLoading ? <LoadingState label="Loading case..." /> : null}
      {data.caseQuery.isError ? <ErrorState error={data.caseQuery.error} title="Case lookup failed" /> : null}
      {data.updateCaseMutation.isError ? (
        <ErrorState error={data.updateCaseMutation.error} title="Case update failed" />
      ) : null}
      {data.assignMutation.isError ? <ErrorState error={data.assignMutation.error} title="Case assignment failed" /> : null}
      {data.addNoteMutation.isError ? <ErrorState error={data.addNoteMutation.error} title="Case note failed" /> : null}

      {data.caseQuery.data ? (
        <CaseDetailPanel
          row={data.caseQuery.data}
          actionsDisabled={
            data.updateCaseMutation.isPending || data.assignMutation.isPending || data.addNoteMutation.isPending
          }
          onStatusChange={(status) => data.updateCaseMutation.mutate({ status })}
          onPriorityChange={(priority) => data.updateCaseMutation.mutate({ priority })}
          onAssign={(owner) => data.assignMutation.mutate(owner)}
          onAddNote={(note) => data.addNoteMutation.mutate(note)}
        />
      ) : (
        !data.caseQuery.isLoading &&
        !data.caseQuery.isError && (
          <EmptyState
            title="Case not found"
            description="No case details are available for the requested identifier."
          />
        )
      )}
    </div>
  );
}
