import { StatusBadge } from "@/components/status/StatusBadge";

export function PhaseStatusBadge({ status }: { status: string | null | undefined }) {
  return <StatusBadge status={status} />;
}
