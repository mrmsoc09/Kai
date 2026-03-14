import { useState } from "react";

import type { FindingReviewActionRequest } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { isUuid } from "@/lib/utils";

export function ReviewActionForm({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (body: FindingReviewActionRequest) => void;
}) {
  const [reviewerId, setReviewerId] = useState("operator.console.reviewer");
  const [action, setAction] = useState<FindingReviewActionRequest["action"]>("APPROVE");
  const [notes, setNotes] = useState("");
  const [duplicateId, setDuplicateId] = useState("");

  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-2">
        <Input value={reviewerId} onChange={(event) => setReviewerId(event.target.value)} placeholder="reviewer_id" />
        <Select
          value={action}
          onChange={(event) => setAction(event.target.value as FindingReviewActionRequest["action"])}
        >
          <option value="APPROVE">APPROVE</option>
          <option value="REJECT">REJECT</option>
          <option value="NEEDS_MORE_EVIDENCE">NEEDS_MORE_EVIDENCE</option>
          <option value="DUPLICATE">DUPLICATE</option>
          <option value="SUPPRESS">SUPPRESS</option>
        </Select>
      </div>
      {action === "DUPLICATE" ? (
        <Input
          value={duplicateId}
          onChange={(event) => setDuplicateId(event.target.value)}
          placeholder="duplicate_of_finding_id"
        />
      ) : null}
      <Textarea value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="review_notes" />
      <Button
        disabled={loading}
        onClick={() =>
          onSubmit({
            action,
            reviewer_id: reviewerId,
            review_notes: notes || undefined,
            duplicate_of_finding_id: action === "DUPLICATE" && isUuid(duplicateId) ? duplicateId : undefined
          })
        }
      >
        {loading ? "Applying..." : "Apply Review Action"}
      </Button>
    </div>
  );
}
