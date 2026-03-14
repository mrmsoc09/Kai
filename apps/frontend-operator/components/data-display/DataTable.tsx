import { Table } from "@/components/ui/table";
import { cn } from "@/lib/utils";

export function DataTable({
  children,
  className
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("overflow-auto rounded-md border border-border bg-panel", className)}>
      <Table>{children}</Table>
    </div>
  );
}
