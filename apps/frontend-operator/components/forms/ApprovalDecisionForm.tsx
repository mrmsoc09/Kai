import { useState } from "react";

import { APPROVAL_CONSOLE_ACTOR } from "@/lib/operator-identity";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

type ApprovalAction = "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";

export type ApprovalDecisionPayload = {
  gateId: string;
  status: ApprovalAction;
  decidedBy: string;
  notes?: string;
  intention: string;
};

export function ApprovalDecisionForm({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (payload: ApprovalDecisionPayload) => void;
}) {
  const [gateId, setGateId] = useState("");
  const [status, setStatus] = useState<ApprovalAction>("APPROVED");
  const [decidedBy, setDecidedBy] = useState<string>(APPROVAL_CONSOLE_ACTOR);
  const [notes, setNotes] = useState("");
  const [intention, setIntention] = useState("");

  const intentionRequired = status === "APPROVED";
  const intentionMissing = intentionRequired && intention.trim().length === 0;
  const canSubmit = !loading && gateId.trim().length > 0 && !intentionMissing;

  function handleSubmit() {
    if (!canSubmit) {
      return;
    }
    onSubmit({
      gateId: gateId.trim(),
      status,
      decidedBy: decidedBy.trim() || APPROVAL_CONSOLE_ACTOR,
      notes: notes.trim() || undefined,
      intention: intention.trim()
    });
  }

  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-2">
        <Input
          value={gateId}
          onChange={(event) => setGateId(event.target.value)}
          placeholder="approval gate ID (UUID)"
        />
        <Select value={status} onChange={(event) => setStatus(event.target.value as ApprovalAction)}>
          <option value="APPROVED">APPROVED</option>
          <option value="REJECTED">REJECTED</option>
          <option value="DEFERRED">DEFERRED</option>
          <option value="CANCELED">CANCELED</option>
        </Select>
        <Input
          value={decidedBy}
          onChange={(event) => setDecidedBy(event.target.value)}
          placeholder="decided_by (operator identity)"
        />
        <Input
          value={notes}
          onChange={(event) => setNotes(event.target.value)}
          placeholder="operator notes (optional)"
        />
      </div>

      {/* Intention — required for APPROVE decisions */}
      <div className="space-y-1">
        <p className="text-xs font-medium text-foreground">
          Reviewer Intention{" "}
          {intentionRequired ? (
            <span className="text-danger">*</span>
          ) : (
            <span className="text-muted">(optional for non-approve decisions)</span>
          )}
        </p>
        <Textarea
          value={intention}
          onChange={(event) => setIntention(event.target.value)}
          placeholder="State the security objective, scope confirmation, and expected outcome that justifies this approval."
          className={intentionMissing ? "border-danger focus:border-danger" : ""}
          rows={3}
        />
        {intentionMissing ? (
          <Alert className="border-danger/50 bg-danger/10 text-danger">
            Intention is required before approving a gate request. Describe the security rationale and
            expected outcome so this decision is auditable.
          </Alert>
        ) : null}
      </div>

      <Button disabled={!canSubmit} onClick={handleSubmit}>
        {loading ? "Submitting…" : "Submit Decision"}
      </Button>
    </div>
  );
}
