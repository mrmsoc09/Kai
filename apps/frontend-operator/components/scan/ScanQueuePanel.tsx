"use client";

import { useCallback, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ScanActionButtons } from "@/components/scan/ScanActionButtons";
import { queueBatch } from "@/lib/api/scans";
import type { ScanQueueItem } from "@/lib/scan-queue";

type ScanQueuePanelProps = {
  items: ScanQueueItem[];
  onReorder: (fromIndex: number, toIndex: number) => void;
  onRemove: (id: string) => void;
  onUpdateItem: (id: string, patch: Partial<ScanQueueItem>) => void;
  onClearCompleted?: () => void;
};

const STATUS_CLASSES: Record<ScanQueueItem["status"], string> = {
  queued: "bg-elevated text-muted",
  running: "bg-active/20 text-active",
  approved: "bg-success/20 text-success",
  killed: "bg-danger/20 text-danger",
  failed: "bg-danger/20 text-danger",
  completed: "bg-elevated text-muted"
};

export function ScanQueuePanel({
  items,
  onReorder,
  onRemove,
  onUpdateItem,
  onClearCompleted
}: ScanQueuePanelProps) {
  const dragIndexRef = useRef<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  const [launching, setLaunching] = useState(false);
  const [launchError, setLaunchError] = useState<string | null>(null);

  const handleLaunchAll = useCallback(async () => {
    const queued = items.filter((item) => item.status === "queued");
    if (queued.length === 0) {
      return;
    }
    setLaunching(true);
    setLaunchError(null);
    try {
      const response = await queueBatch({
        items: queued.map((item) => ({
          program_id: item.programId,
          scope_target_id: item.scopeTargetId ?? null,
          subject_key: item.subjectKey,
          subject_type: item.subjectType,
          recommended_workflow: item.recommendedWorkflow ?? null,
        })),
        force: true,
        safe_mode: true,
      });

      // Update successfully dispatched items to "running"
      for (const dispatched of response.queued) {
        const localItem = queued[dispatched.item_index];
        if (localItem) {
          onUpdateItem(localItem.id, {
            status: "running",
            campaignId: dispatched.schedule_job_id,
          });
        }
      }

      if (response.errors.length > 0) {
        setLaunchError(
          `${response.queued.length} dispatched, ${response.errors.length} failed: ` +
          response.errors.map((e) => e.error).join("; ")
        );
      }
    } catch (err) {
      setLaunchError(err instanceof Error ? err.message : "Launch failed");
    } finally {
      setLaunching(false);
    }
  }, [items, onUpdateItem]);

  const handleDragStart = (index: number) => (e: React.DragEvent) => {
    dragIndexRef.current = index;
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (index: number) => (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    setDragOverIndex(index);
  };

  const handleDrop = (toIndex: number) => (e: React.DragEvent) => {
    e.preventDefault();
    const fromIndex = dragIndexRef.current;
    setDragOverIndex(null);
    dragIndexRef.current = null;
    if (fromIndex === null || fromIndex === toIndex) {
      return;
    }
    onReorder(fromIndex, toIndex);
  };

  const handleDragEnd = () => {
    dragIndexRef.current = null;
    setDragOverIndex(null);
  };

  const hasTerminal = items.some(
    (item) =>
      item.status === "completed" ||
      item.status === "killed" ||
      item.status === "failed"
  );

  const queuedCount = items.filter((item) => item.status === "queued").length;

  return (
    <div>
      {/* Header */}
      <div className="mb-2 flex items-center justify-between gap-2 flex-wrap">
        <span className="text-sm font-medium text-foreground">
          {items.length} item{items.length !== 1 ? "s" : ""} in queue
        </span>
        <div className="flex items-center gap-2">
          {queuedCount > 0 && (
            <Button
              variant="default"
              size="sm"
              onClick={() => void handleLaunchAll()}
              disabled={launching}
              title={`Dispatch all ${queuedCount} queued items via subfinder → httpx → nuclei pipeline`}
            >
              {launching ? (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border border-foreground border-t-transparent mr-1" />
              ) : (
                "▶▶"
              )}
              {launching ? "Launching…" : `Launch All (${queuedCount})`}
            </Button>
          )}
          {hasTerminal && onClearCompleted && (
            <Button variant="outline" size="sm" onClick={onClearCompleted}>
              Clear Completed
            </Button>
          )}
        </div>
      </div>
      {launchError && (
        <p className="mb-2 text-xs text-danger">{launchError}</p>
      )}

      {/* Empty state */}
      {items.length === 0 && (
        <div className="rounded-md border border-border bg-panel p-6 text-sm text-muted">
          <p className="font-semibold text-foreground">No scans in queue</p>
          <p className="mt-1">
            Select opportunities and click Add to Queue.
          </p>
        </div>
      )}

      {/* Table */}
      {items.length > 0 && (
        <div className="overflow-auto rounded-md border border-border bg-panel">
          <table className="w-full border-collapse text-sm text-foreground">
            <thead>
              <tr>
                <th className="border-b border-border bg-elevated px-2 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted w-8">
                  ⠿
                </th>
                <th className="border-b border-border bg-elevated px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted w-10">
                  #
                </th>
                <th className="border-b border-border bg-elevated px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">
                  Subject
                </th>
                <th className="border-b border-border bg-elevated px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">
                  Workflow
                </th>
                <th className="border-b border-border bg-elevated px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted w-24">
                  Status
                </th>
                <th className="border-b border-border bg-elevated px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => {
                const isDragOver = dragOverIndex === index;
                return (
                  <tr
                    key={item.id}
                    draggable
                    onDragStart={handleDragStart(index)}
                    onDragOver={handleDragOver(index)}
                    onDrop={handleDrop(index)}
                    onDragEnd={handleDragEnd}
                    className={isDragOver ? "bg-elevated/60" : undefined}
                  >
                    {/* Drag handle */}
                    <td className="border-b border-border px-2 py-2 text-center text-muted cursor-grab select-none">
                      ⠿
                    </td>
                    {/* Priority */}
                    <td className="border-b border-border px-3 py-2 text-muted tabular-nums">
                      {item.priority}
                    </td>
                    {/* Subject */}
                    <td className="border-b border-border px-3 py-2 align-top">
                      <p className="font-medium text-foreground">
                        {item.subjectType}:{item.subjectKey}
                      </p>
                      <p className="font-mono text-xs text-muted">
                        program={item.programId.slice(0, 8)}...
                      </p>
                    </td>
                    {/* Workflow */}
                    <td className="border-b border-border px-3 py-2 text-xs text-muted align-top">
                      {item.recommendedWorkflow ?? "n/a"}
                    </td>
                    {/* Status badge */}
                    <td className="border-b border-border px-3 py-2 align-top">
                      <span
                        className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${STATUS_CLASSES[item.status]}`}
                      >
                        {item.status}
                      </span>
                    </td>
                    {/* Actions */}
                    <td className="border-b border-border px-3 py-2 align-top">
                      <ScanActionButtons
                        item={item}
                        compact={false}
                        onStart={(campaignId) =>
                          onUpdateItem(item.id, {
                            campaignId,
                            status: "running"
                          })
                        }
                        onKill={() =>
                          onUpdateItem(item.id, { status: "killed" })
                        }
                        onRemove={() => onRemove(item.id)}
                        onRequeue={() =>
                          onUpdateItem(item.id, { status: "queued", campaignId: null })
                        }
                      />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
