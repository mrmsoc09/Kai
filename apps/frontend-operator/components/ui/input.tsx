import * as React from "react";

import { cn } from "@/lib/utils";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-md border border-border bg-background px-3 text-sm text-foreground shadow-sm outline-none placeholder:text-muted focus:border-active focus:ring-2 focus:ring-active/20",
        className
      )}
      {...props}
    />
  );
}
