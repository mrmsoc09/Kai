import { StatusBadge } from "@/components/status/StatusBadge";

export function HealthIndicator({ status }: { status: string | null | undefined }) {
  return <StatusBadge status={status} />;
}
