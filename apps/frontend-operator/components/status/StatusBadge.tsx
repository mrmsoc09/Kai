import { cn } from "@/lib/utils";
import { normalizeStatus, statusClassName } from "@/lib/utils/status";

type StatusBadgeProps = {
  status: string | null | undefined;
  className?: string;
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const normalized = normalizeStatus(status);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold uppercase tracking-wide",
        statusClassName(normalized),
        className
      )}
    >
      {normalized}
    </span>
  );
}
