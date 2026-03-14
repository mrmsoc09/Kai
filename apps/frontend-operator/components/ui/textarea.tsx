import * as React from "react";

import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "min-h-20 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground shadow-sm outline-none placeholder:text-muted focus:border-active focus:ring-2 focus:ring-active/20",
        className
      )}
      {...props}
    />
  );
}
