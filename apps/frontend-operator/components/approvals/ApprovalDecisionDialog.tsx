import { ApprovalDecisionForm } from "@/components/forms/ApprovalDecisionForm";

export function ApprovalDecisionDialog({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (payload: {
    gateId: string;
    status: "APPROVED" | "REJECTED" | "DEFERRED" | "CANCELED";
    decidedBy: string;
    notes?: string;
  }) => void;
}) {
  return <ApprovalDecisionForm loading={loading} onSubmit={onSubmit} />;
}
