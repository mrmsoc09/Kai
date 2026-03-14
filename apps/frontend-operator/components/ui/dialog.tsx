import { cn } from "@/lib/utils";

export function Dialog({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-md border border-border bg-panel p-3", className)} {...props} />;
}
