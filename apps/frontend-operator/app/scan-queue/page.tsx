"use client";

import { useMemo } from "react";

import { useScanQueue } from "@/hooks/useScanQueue";
import { ScanQueuePanel } from "@/components/scan/ScanQueuePanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type StatChipProps = { label: string; value: number; color?: string };

function StatChip({ label, value, color = "#007A1E" }: StatChipProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "0.5rem",
        padding: "4px 10px",
        borderRadius: 3,
        border: "1px solid #003300",
        background: "rgba(0,0,0,0.5)",
        fontFamily: "IBM Plex Mono, monospace",
      }}
    >
      <span style={{ fontSize: "0.6rem", color: "#007A1E", textTransform: "uppercase", letterSpacing: "0.1em" }}>
        {label}
      </span>
      <span style={{ fontSize: "0.85rem", fontWeight: 700, color, textShadow: color === "#00FF41" ? "0 0 6px rgba(0,255,65,0.5)" : undefined, tabularNums: true } as React.CSSProperties}>
        {value}
      </span>
    </div>
  );
}

export default function ScanQueuePage() {
  const { items, removeItem, reorder, updateItem, clearCompleted } = useScanQueue();

  const stats = useMemo(() => ({
    total:     items.length,
    queued:    items.filter((i) => i.status === "queued").length,
    running:   items.filter((i) => i.status === "running").length,
    completed: items.filter((i) => i.status === "completed").length,
    killed:    items.filter((i) => i.status === "killed").length,
  }), [items]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
      <PageHeader
        title="Scan Queue"
        description="Manage and prioritize your scan pipeline. Drag rows to reorder."
      />

      {/* Stats bar */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
        <StatChip label="Total"     value={stats.total}     color="#007A1E" />
        <StatChip label="Queued"    value={stats.queued}    color="#00FF41" />
        <StatChip label="Running"   value={stats.running}   color="#00FFFF" />
        <StatChip label="Completed" value={stats.completed} color="#FFD700" />
        {stats.killed > 0 && (
          <StatChip label="Killed" value={stats.killed} color="#FF3333" />
        )}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            <span style={{ color: "#007A1E" }}>⬡</span>{" "}Queue Pipeline
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ScanQueuePanel
            items={items}
            onReorder={reorder}
            onRemove={removeItem}
            onUpdateItem={updateItem}
            onClearCompleted={clearCompleted}
          />
        </CardContent>
      </Card>
    </div>
  );
}
