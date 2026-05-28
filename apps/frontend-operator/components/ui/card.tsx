import * as React from "react";

import { cn } from "@/lib/utils";

export function Card({ className, style, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("rounded-sm border border-border bg-panel", className)}
      style={{
        boxShadow: "inset 0 0 20px rgba(0,255,65,0.03), 0 0 1px #003300",
        ...style,
      }}
      {...props}
    />
  );
}

export function CardHeader({ className, style, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("border-b border-border px-4 py-3", className)}
      style={{
        background: "linear-gradient(90deg, rgba(0,255,65,0.06) 0%, transparent 100%)",
        ...style,
      }}
      {...props}
    />
  );
}

export function CardTitle({ className, style, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2
      className={cn("text-sm font-semibold text-foreground", className)}
      style={{
        fontFamily: "IBM Plex Mono, monospace",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        textShadow: "0 0 6px rgba(0,255,65,0.4)",
        ...style,
      }}
      {...props}
    />
  );
}

export function CardContent({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-4 py-3", className)} {...props} />;
}
