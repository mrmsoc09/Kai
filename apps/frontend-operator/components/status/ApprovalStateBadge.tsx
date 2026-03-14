import { StatusBadge } from "@/components/status/StatusBadge";

export function ApprovalStateBadge({ status }: { status: string | null | undefined }) {
  return <StatusBadge status={status} />;
}
