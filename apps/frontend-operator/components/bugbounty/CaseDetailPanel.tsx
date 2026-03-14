import { useState } from "react";

import { StatusBadge } from "@/components/status/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { AnalystCase, CasePriority, CaseStatus } from "@/lib/types";

const statusOptions: CaseStatus[] = [
  "new",
  "acknowledged",
  "triaging",
  "needs_manual_validation",
  "ready_for_report",
  "dismissed",
  "duplicate",
  "escalated",
  "submitted",
  "closed"
];

const priorityOptions: CasePriority[] = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];

export function CaseDetailPanel({
  row,
  actionsDisabled,
  onStatusChange,
  onPriorityChange,
  onAssign,
  onAddNote
}: {
  row: AnalystCase;
  actionsDisabled?: boolean;
  onStatusChange?: (status: CaseStatus) => void;
  onPriorityChange?: (priority: CasePriority) => void;
  onAssign?: (owner: string) => void;
  onAddNote?: (note: string) => void;
}) {
  const [ownerInput, setOwnerInput] = useState(row.owner ?? "");
  const [noteInput, setNoteInput] = useState("");
  const evidenceRefs = Array.isArray(row.evidence_refs_json) ? row.evidence_refs_json : [];
  const triageNotes = Array.isArray(row.triage_notes_json) ? row.triage_notes_json : [];

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>{row.title || "Untitled case"}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted">{row.summary || "No case summary provided."}</p>
          {row.reasoning_summary ? <p className="text-xs text-muted">{row.reasoning_summary}</p> : null}
          <div className="grid gap-2 md:grid-cols-4">
            <div>
              <p className="text-[10px] uppercase text-muted">Status</p>
              <StatusBadge status={row.status} />
            </div>
            <div>
              <p className="text-[10px] uppercase text-muted">Priority</p>
              <StatusBadge status={row.priority} />
            </div>
            <div>
              <p className="text-[10px] uppercase text-muted">Owner</p>
              <p className="text-sm">{row.owner ?? "unassigned"}</p>
            </div>
            <div>
              <p className="text-[10px] uppercase text-muted">Last Actor</p>
              <p className="text-sm">{row.last_actor ?? "n/a"}</p>
            </div>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <Select
              defaultValue={row.status}
              onChange={(event) => onStatusChange?.(event.target.value as CaseStatus)}
              disabled={actionsDisabled}
            >
              {statusOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
            <Select
              defaultValue={row.priority}
              onChange={(event) => onPriorityChange?.(event.target.value as CasePriority)}
              disabled={actionsDisabled}
            >
              {priorityOptions.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid gap-2 md:grid-cols-[1fr_auto]">
            <Input
              value={ownerInput}
              onChange={(event) => setOwnerInput(event.target.value)}
              placeholder="assign owner identity"
            />
            <Button
              type="button"
              variant="secondary"
              disabled={actionsDisabled || ownerInput.trim().length === 0}
              onClick={() => onAssign?.(ownerInput.trim())}
            >
              Assign
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evidence and Notes</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-muted">Evidence References</p>
            {evidenceRefs.length > 0 ? (
              <ul className="space-y-1">
                {evidenceRefs.map((entry) => (
                  <li key={entry} className="font-mono text-xs text-muted">
                    {entry}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">No evidence references linked yet.</p>
            )}
          </div>

          <Textarea
            value={noteInput}
            onChange={(event) => setNoteInput(event.target.value)}
            placeholder="add analyst note"
            rows={4}
          />
          <Button
            type="button"
            disabled={actionsDisabled || noteInput.trim().length === 0}
            onClick={() => {
              onAddNote?.(noteInput.trim());
              setNoteInput("");
            }}
          >
            Add Note
          </Button>

          <div className="space-y-1">
            <p className="text-xs uppercase tracking-wide text-muted">Triage Notes</p>
            {triageNotes.length > 0 ? (
              <ul className="space-y-2">
                {triageNotes.map((entry, index) => (
                  <li key={`note-${index}`} className="rounded border border-border bg-panel px-2 py-1 text-xs text-muted">
                    <p>{String(entry.note ?? "")}</p>
                    <p className="text-[10px] text-muted">
                      {String(entry.actor ?? "unknown")} @ {String(entry.at ?? "unknown")}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-xs text-muted">No notes yet.</p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
