"use client";

import { useMemo, useState } from "react";

import {
  BACKEND_CAPABILITY_LEDGER,
  BACKEND_COVERAGE_SUMMARY,
  BACKEND_MIDDLEWARE_LEDGER,
  type BackendCoverageStatus
} from "@/lib/backend-capability-ledger";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function statusClassName(status: BackendCoverageStatus): string {
  if (status === "FULL_UI") {
    return "border-success/40 bg-success/10 text-success";
  }
  if (status === "LINKED_UI") {
    return "border-active/30 bg-active/10 text-active";
  }
  if (status === "API_ONLY") {
    return "border-review/30 bg-review/10 text-review";
  }
  if (status === "OPTIONAL") {
    return "border-muted/40 bg-muted/10 text-muted";
  }
  return "border-danger/40 bg-danger/10 text-danger";
}

export function BackendCapabilityCoveragePanel() {
  const [statusFilter, setStatusFilter] = useState<"ALL" | BackendCoverageStatus>("ALL");

  const rows = useMemo(() => {
    const base =
      statusFilter === "ALL"
        ? BACKEND_CAPABILITY_LEDGER
        : BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === statusFilter);
    return [...base].sort((a, b) => {
      if (a.status === b.status) {
        return a.id.localeCompare(b.id);
      }
      return a.status.localeCompare(b.status);
    });
  }, [statusFilter]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Backend Capability Coverage</CardTitle>
        <p className="text-xs text-muted">
          Router and middleware ledger derived from backend runtime registration. Every backend domain is explicitly mapped to GUI, linked UX, API-only, optional, or gap.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Total Routers</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.totalRouters}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Full UI</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.fullUi}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Linked UI</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.linkedUi}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">API Only</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.apiOnly}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Optional</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.optional}</p>
          </div>
          <div className="cockpit-kpi">
            <p className="text-[11px] uppercase tracking-wide text-muted">Unmapped Gaps</p>
            <p className="text-xl font-semibold text-foreground">{BACKEND_COVERAGE_SUMMARY.unmapped}</p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          {(["ALL", "FULL_UI", "LINKED_UI", "API_ONLY", "OPTIONAL", "UNMAPPED"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setStatusFilter(option)}
              className={
                statusFilter === option
                  ? "rounded-md border border-active/40 bg-active/20 px-2 py-1 text-xs text-active"
                  : "rounded-md border border-border bg-panel px-2 py-1 text-xs text-foreground hover:bg-elevated"
              }
            >
              {option}
            </button>
          ))}
        </div>

        <div className="max-h-[360px] space-y-2 overflow-y-auto pr-1">
          {rows.map((row) => (
            <div key={row.id} className="rounded-md border border-border bg-elevated p-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="font-mono text-xs text-foreground">{row.id}</p>
                  <p className="text-[11px] text-muted">
                    {row.prefix || "(no static prefix)"} · endpoints: {row.endpointCount}
                  </p>
                </div>
                <Badge className={statusClassName(row.status)}>{row.status}</Badge>
              </div>
              <p className="mt-1 text-xs text-muted">frontend: {row.frontendSurface}</p>
              <p className="text-xs text-muted">{row.note}</p>
            </div>
          ))}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-semibold text-foreground">Middleware Coverage</p>
          {BACKEND_MIDDLEWARE_LEDGER.map((row) => (
            <div key={row.id} className="rounded-md border border-border bg-elevated p-2">
              <p className="text-xs font-medium text-foreground">{row.layer}</p>
              <p className="text-xs text-muted">frontend: {row.frontendSurface}</p>
              <p className="text-xs text-muted">{row.note}</p>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
