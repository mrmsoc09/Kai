import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

type ApprovalAction = "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";

export function ApprovalDecisionForm({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (payload: { gateId: string; status: ApprovalAction; decidedBy: string; notes?: string }) => void;
}) {
  const [gateId, setGateId] = useState("");
  const [status, setStatus] = useState<ApprovalAction>("APPROVED");
  const [decidedBy, setDecidedBy] = useState("operator.console.approvals");
  const [notes, setNotes] = useState("");

  return (
    <div className="grid gap-2 md:grid-cols-2">
      <Input value={gateId} onChange={(event) => setGateId(event.target.value)} placeholder="approval gate id" />
      <Select value={status} onChange={(event) => setStatus(event.target.value as ApprovalAction)}>
        <option value="APPROVED">APPROVED</option>
        <option value="REJECTED">REJECTED</option>
        <option value="DEFERRED">DEFERRED</option>
        <option value="CANCELED">CANCELED</option>
      </Select>
      <Input value={decidedBy} onChange={(event) => setDecidedBy(event.target.value)} placeholder="decided_by" />
      <Input value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="operator_notes (optional)" />
      <div className="md:col-span-2">
        <Button
          disabled={loading || gateId.trim().length === 0}
          onClick={() => onSubmit({ gateId, status, decidedBy, notes: notes || undefined })}
        >
          {loading ? "Submitting..." : "Submit Approval Decision"}
        </Button>
      </div>
    </div>
  );
}
