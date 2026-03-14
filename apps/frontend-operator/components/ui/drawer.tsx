import { cn } from "@/lib/utils";

export function Drawer({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <aside className={cn("rounded-md border border-border bg-panel p-3", className)} {...props} />;
}
