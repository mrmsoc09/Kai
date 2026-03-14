import { StatusBadge } from "@/components/status/StatusBadge";

export function ExportReadinessBadge({ state }: { state: string | null | undefined }) {
  return <StatusBadge status={state} />;
}
