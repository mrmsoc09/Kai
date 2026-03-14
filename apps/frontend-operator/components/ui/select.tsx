import * as React from "react";

import { cn } from "@/lib/utils";

export function Select({ className, ...props }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground shadow-sm outline-none focus:border-active focus:ring-2 focus:ring-active/20",
        className
      )}
      {...props}
    />
  );
}
