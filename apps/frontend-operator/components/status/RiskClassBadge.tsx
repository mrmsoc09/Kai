import { StatusBadge } from "@/components/status/StatusBadge";

export function RiskClassBadge({ riskClass }: { riskClass: string | null | undefined }) {
  return <StatusBadge status={riskClass ?? "UNKNOWN"} />;
}
