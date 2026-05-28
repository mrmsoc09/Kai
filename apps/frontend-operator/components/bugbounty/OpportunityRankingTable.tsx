"use client";

import { useState } from "react";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Button } from "@/components/ui/button";
import { Td, Th } from "@/components/ui/table";
import type { OpportunityRankingRow } from "@/hooks/useOpportunityRankings";

type OpportunityRankingTableProps = {
  rows: OpportunityRankingRow[];
  onAddToQueue?: (rows: OpportunityRankingRow[]) => void;
};

export function OpportunityRankingTable({ rows, onAddToQueue }: OpportunityRankingTableProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const allSelected = rows.length > 0 && rows.every((row) => selectedIds.has(row.id));
  const someSelected = selectedIds.size > 0;

  const toggleAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(rows.map((row) => row.id)));
    }
  };

  const toggleRow = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const handleAddSelected = () => {
    if (!onAddToQueue) return;
    const selectedRows = rows.filter((row) => selectedIds.has(row.id));
    onAddToQueue(selectedRows);
    setSelectedIds(new Set());
  };

  const clearSelection = () => setSelectedIds(new Set());

  if (rows.length === 0) {
    return (
      <EmptyState
        title="No opportunity rankings"
        description="Run Phase 7 prediction to generate opportunity selection output."
      />
    );
  }

  return (
    <div className="relative">
      <DataTable>
        <thead>
          <tr>
            {onAddToQueue && (
              <Th className="w-8">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={toggleAll}
                  className="cursor-pointer accent-active"
                  aria-label="Select all rows"
                />
              </Th>
            )}
            <Th>Rank</Th>
            <Th>Subject</Th>
            <Th>Opportunity</Th>
            <Th>Confidence</Th>
            <Th>Dup Risk</Th>
            <Th>Evidence</Th>
            <Th>Recommended Workflow</Th>
            <Th>Follow-up Action</Th>
            <Th>Reasoning</Th>
            {onAddToQueue && <Th className="w-16">Add</Th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isSelected = selectedIds.has(row.id);
            return (
              <tr
                key={row.id}
                className={isSelected ? "bg-active/10" : undefined}
              >
                {onAddToQueue && (
                  <Td>
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleRow(row.id)}
                      className="cursor-pointer accent-active"
                      aria-label={`Select ${row.subjectKey}`}
                    />
                  </Td>
                )}
                <Td>{row.priorityRank ?? "-"}</Td>
                <Td>
                  <p className="font-medium">{row.subjectType ?? "UNKNOWN"}:{row.subjectKey ?? "unknown-subject"}</p>
                  <p className="font-mono text-xs text-muted">program={row.programId}</p>
                  {row.scopeTargetId ? <p className="font-mono text-xs text-muted">target={row.scopeTargetId}</p> : null}
                </Td>
                <Td>
                  <ScoreBadge value={row.selectionScore} label="opportunity" />
                </Td>
                <Td>
                  <ScoreBadge value={row.confidenceScore} label="confidence" />
                </Td>
                <Td>
                  <ScoreBadge value={row.duplicateRiskScore} label="duplicate" />
                </Td>
                <Td>
                  <ScoreBadge value={row.evidenceCompletenessScore} label="evidence" />
                </Td>
                <Td>{row.recommendedWorkflow ?? "n/a"}</Td>
                <Td>{row.recommendedAction ?? "n/a"}</Td>
                <Td className="max-w-[360px] text-xs text-muted">{row.reasoningSummary ?? "No reasoning summary provided."}</Td>
                {onAddToQueue && (
                  <Td>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onAddToQueue([row])}
                      title="Add to scan queue"
                    >
                      +
                    </Button>
                  </Td>
                )}
              </tr>
            );
          })}
        </tbody>
      </DataTable>

      {/* Sticky selection toolbar */}
      {someSelected && onAddToQueue && (
        <div
          className="sticky bottom-0 flex items-center gap-3 rounded-b-md border-t border-border bg-elevated px-4 py-2"
          role="toolbar"
          aria-label="Selection actions"
        >
          <span className="text-sm font-medium text-foreground">
            {selectedIds.size} selected
          </span>
          <Button variant="default" size="sm" onClick={handleAddSelected}>
            ▶ Add Selected to Queue
          </Button>
          <Button variant="outline" size="sm" onClick={clearSelection}>
            ✕ Clear Selection
          </Button>
        </div>
      )}
    </div>
  );
}
