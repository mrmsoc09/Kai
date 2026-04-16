import { ApprovalDecisionForm, type ApprovalDecisionPayload } from "@/components/forms/ApprovalDecisionForm";

export type { ApprovalDecisionPayload };

export function ApprovalDecisionDialog({
  loading = false,
  onSubmit
}: {
  loading?: boolean;
  onSubmit: (payload: ApprovalDecisionPayload) => void;
}) {
  return <ApprovalDecisionForm loading={loading} onSubmit={onSubmit} />;
}
