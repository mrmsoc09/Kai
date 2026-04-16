"use client";

import Link from "next/link";
import { useState } from "react";

import type { InferredApprovalGate } from "@/lib/types";

import { IntentionDisplayCard } from "@/components/cockpit/IntentionDisplayCard";
import { ApprovalStateBadge } from "@/components/status/ApprovalStateBadge";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";

type ApprovalAction = "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";

function RiskBandBadge({ band }: { band: string }) {
  const colorMap: Record<string, string> = {
    CRITICAL: "border-danger/50 bg-danger/10 text-danger",
    HIGH: "border-orange-500/50 bg-orange-500/10 text-orange-400",
    MEDIUM: "border-review/50 bg-review/10 text-review",
    LOW: "border-success/50 bg-success/10 text-success",
    UNSPECIFIED: "border-border bg-elevated text-muted"
  };
  const cls = colorMap[band] ?? colorMap.UNSPECIFIED;
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide ${cls}`}>
      {band}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="pb-1 text-[10px] font-semibold uppercase tracking-widest text-muted">{children}</p>
  );
}

function FieldRow({ label, value, mono = false }: { label: string; value: string | null | undefined; mono?: boolean }) {
  if (!value) {
    return null;
  }
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wide text-muted">{label}</p>
      <p className={mono ? "font-mono text-xs text-foreground break-all" : "text-sm text-foreground"}>{value}</p>
    </div>
  );
}

export function ApprovalDetailPanel({
  gate,
  onAction,
  onClose,
  loading = false
}: {
  gate: InferredApprovalGate;
  onAction: (gateId: string, status: ApprovalAction, notes?: string) => void;
  onClose: () => void;
  loading?: boolean;
}) {
  const [notes, setNotes] = useState(gate.reviewer_notes || "");
  const canApprove = gate.intention.trim().length > 0;

  return (
    <Card className="border-active/50 shadow-md">
      {/* Header */}
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1.5 min-w-0">
            <CardTitle className="text-base leading-snug">{gate.request_title}</CardTitle>
            <div className="flex flex-wrap items-center gap-2">
              <ApprovalStateBadge status={gate.status} />
              <RiskBandBadge band={gate.risk_band} />
              <span className="font-mono text-[11px] text-muted">{gate.gate_id}</span>
            </div>
          </div>
          <Button size="sm" variant="outline" onClick={onClose} className="shrink-0">
            Close ✕
          </Button>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {/* ── Intention & Safety ── PROMINENT FIRST ─────────────────── */}
        <div>
          <SectionLabel>Intention & Safety Profile</SectionLabel>
          <IntentionDisplayCard
            intention={gate.intention}
            justification={gate.justification}
            expectedImpact={gate.expected_impact}
            safetyConstraints={gate.safety_constraints}
          />
        </div>

        {/* ── Request Context ────────────────────────────────────────── */}
        <div>
          <SectionLabel>Request Context</SectionLabel>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            <FieldRow label="Requested Action" value={gate.requested_action} />
            <FieldRow label="Requesting Agent" value={gate.requesting_agent} />
            <FieldRow label="Phase" value={gate.phase_name ?? gate.phase_job_id} />
            <FieldRow label="Scope Target" value={gate.scope_target} mono />
            <div>
              <p className="text-[10px] uppercase tracking-wide text-muted">Mission</p>
              <Link
                href={`/mission-control/${gate.campaign_id}`}
                className="font-mono text-xs text-active hover:underline break-all"
              >
                {gate.campaign_id}
              </Link>
            </div>
            <FieldRow label="Source Event" value={gate.source_event_type} mono />
          </div>
        </div>

        {/* ── Evidence ───────────────────────────────────────────────── */}
        <div>
          <SectionLabel>Evidence Attached</SectionLabel>
          <div className="rounded-md border border-border bg-elevated p-3 text-sm text-foreground">
            {gate.evidence_attached || "No evidence references in current payload."}
          </div>
        </div>

        {/* ── Decision History ───────────────────────────────────────── */}
        <div>
          <SectionLabel>Decision History</SectionLabel>
          <div className="grid gap-3 md:grid-cols-3 text-xs">
            <div className="rounded-md border border-border bg-elevated p-2">
              <p className="text-muted">Requested at</p>
              <p className="mt-0.5 font-medium text-foreground">{gate.requested_at ?? "—"}</p>
            </div>
            <div className="rounded-md border border-border bg-elevated p-2">
              <p className="text-muted">Decided at</p>
              <p className="mt-0.5 font-medium text-foreground">{gate.decided_at ?? "—"}</p>
            </div>
            <div className="rounded-md border border-border bg-elevated p-2">
              <p className="text-muted">Last event</p>
              <p className="mt-0.5 font-medium text-foreground">{gate.happened_at ?? "—"}</p>
            </div>
          </div>
          {gate.reviewer_notes ? (
            <div className="mt-2 rounded-md border border-border bg-elevated p-3 text-sm">
              <p className="text-[10px] uppercase tracking-wide text-muted">Existing Reviewer Notes</p>
              <p className="mt-1 text-foreground">{gate.reviewer_notes}</p>
            </div>
          ) : null}
        </div>

        {/* ── Operator Decision ──────────────────────────────────────── */}
        <div className="space-y-3 border-t border-border pt-4">
          <SectionLabel>Make Decision</SectionLabel>

          {!canApprove ? (
            <Alert className="border-danger/50 bg-danger/10 text-danger">
              Intention metadata is missing. This request cannot be approved until the agent supplies a declared intention.
              You may still reject, defer, or cancel.
            </Alert>
          ) : null}

          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Operator notes (optional) — recorded with your decision"
            className="min-h-16"
          />

          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              disabled={loading || !canApprove}
              title={!canApprove ? "Cannot approve without intention" : undefined}
              onClick={() => onAction(gate.gate_id, "APPROVED", notes || undefined)}
            >
              Approve
            </Button>
            <Button
              size="sm"
              variant="destructive"
              disabled={loading}
              onClick={() => onAction(gate.gate_id, "REJECTED", notes || undefined)}
            >
              Reject
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={loading}
              onClick={() => onAction(gate.gate_id, "DEFERRED", notes || undefined)}
            >
              Defer
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={loading}
              onClick={() => onAction(gate.gate_id, "CANCELED", notes || undefined)}
            >
              Cancel
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
