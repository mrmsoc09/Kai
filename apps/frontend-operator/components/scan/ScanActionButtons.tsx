"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { getCampaign } from "@/lib/api/campaigns";
import { queueBatch } from "@/lib/api/scans";
import type { ScanQueueItem } from "@/lib/scan-queue";

type ScanActionButtonsProps = {
  item: ScanQueueItem;
  onStart?: (campaignId: string) => void;
  onKill?: () => void;
  onRemove?: () => void;
  onRequeue?: () => void;
  onViewStatus?: () => void;
  compact?: boolean;
};

function StatusPopover({ campaignId }: { campaignId: string }) {
  const [open, setOpen] = useState(false);

  const statusQuery = useQuery({
    queryKey: ["campaign-status-popover", campaignId],
    queryFn: () => getCampaign(campaignId),
    enabled: open,
    staleTime: 10_000
  });

  return (
    <div className="relative inline-block">
      <Button
        variant="secondary"
        size="sm"
        onClick={() => setOpen((v) => !v)}
        title="Campaign Status"
        aria-expanded={open}
      >
        Status
      </Button>
      {open && (
        <div
          className="absolute left-0 top-full z-50 mt-1 w-56 rounded-md border border-border bg-panel p-3 shadow-lg"
          role="tooltip"
        >
          {statusQuery.isLoading && (
            <p className="text-xs text-muted">Loading status...</p>
          )}
          {statusQuery.isError && (
            <p className="text-xs text-danger">Failed to load status</p>
          )}
          {statusQuery.data && (
            <div className="space-y-1">
              <p className="text-xs font-semibold text-foreground">
                {statusQuery.data.campaign.status}
              </p>
              <p className="font-mono text-xs text-muted">
                {campaignId.slice(0, 16)}...
              </p>
              <p className="text-xs text-muted">
                Branches: {statusQuery.data.branches.length} &middot; Jobs:{" "}
                {statusQuery.data.phase_jobs.length}
              </p>
            </div>
          )}
          <button
            className="mt-2 text-xs text-muted underline"
            onClick={() => setOpen(false)}
          >
            close
          </button>
        </div>
      )}
    </div>
  );
}

export function ScanActionButtons({
  item,
  onStart,
  onKill,
  onRemove,
  onRequeue,
  compact = false
}: ScanActionButtonsProps) {
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);

  const handleStart = useCallback(async () => {
    setStarting(true);
    setStartError(null);
    try {
      const response = await queueBatch({
        items: [
          {
            program_id: item.programId,
            scope_target_id: item.scopeTargetId ?? null,
            subject_key: item.subjectKey,
            subject_type: item.subjectType,
            recommended_workflow: item.recommendedWorkflow ?? null,
          },
        ],
        force: true,
        safe_mode: true,
      });

      if (response.queued.length > 0) {
        // Use schedule_job_id as the tracking handle (status polling will
        // look up the schedule's last_run_status via the bug-bounty API).
        onStart?.(response.queued[0].schedule_job_id);
      } else {
        const firstError = response.errors[0]?.error ?? "Queue returned no dispatched jobs";
        setStartError(firstError);
      }
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to queue scan";
      setStartError(message);
    } finally {
      setStarting(false);
    }
  }, [item.subjectKey, item.programId, item.scopeTargetId, item.subjectType, item.recommendedWorkflow, onStart]);

  const handleKill = useCallback(() => {
    onKill?.();
  }, [onKill]);

  const isTerminal =
    item.status === "completed" ||
    item.status === "killed" ||
    item.status === "failed";

  const sz = "sm" as const;

  return (
    <div className="flex flex-wrap items-center gap-1">
      {/* Re-queue: shown when in terminal state */}
      {isTerminal && onRequeue && (
        <Button variant="outline" size={sz} onClick={onRequeue}>
          {compact ? "+" : "Add to Queue"}
        </Button>
      )}

      {/* Start: shown when queued */}
      {item.status === "queued" && (
        <Button
          variant="default"
          size={sz}
          onClick={() => void handleStart()}
          disabled={starting}
        >
          {starting ? (
            <span className="inline-block h-3 w-3 animate-spin rounded-full border border-foreground border-t-transparent" />
          ) : compact ? (
            "▶"
          ) : (
            "▶ Start Scan"
          )}
        </Button>
      )}

      {/* Approve: shown when running */}
      {item.status === "running" && (
        <Link
          href="/approvals"
          className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-panel px-3 text-xs font-medium text-foreground hover:bg-elevated"
        >
          {compact ? "✓" : "✓ Approve"}
        </Link>
      )}

      {/* Kill: shown when running */}
      {item.status === "running" && (
        <Button variant="destructive" size={sz} onClick={handleKill}>
          {compact ? "⏹" : "⏹ Kill Scan"}
        </Button>
      )}

      {/* Status popover: shown when campaignId is set */}
      {item.campaignId && (
        <StatusPopover campaignId={item.campaignId} />
      )}

      {/* History: shown when campaignId is set */}
      {item.campaignId && (
        <Link
          href={`/missions?campaign=${item.campaignId}`}
          className="inline-flex h-8 items-center justify-center rounded-md border border-border bg-panel px-3 text-xs font-medium text-foreground hover:bg-elevated"
        >
          {compact ? "📋" : "📋 History"}
        </Link>
      )}

      {/* Remove */}
      {onRemove && (
        <Button variant="outline" size={sz} onClick={onRemove} title="Remove from queue">
          {compact ? "✕" : "Remove"}
        </Button>
      )}

      {startError && (
        <p className="w-full text-xs text-danger">{startError}</p>
      )}
    </div>
  );
}
