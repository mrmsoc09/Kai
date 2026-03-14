import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "secondary" | "destructive" | "outline";
  size?: "sm" | "md";
};

export function Button({ className, variant = "default", size = "md", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-60",
        size === "sm" ? "h-8 px-3 text-xs" : "h-9 px-4 text-sm",
        variant === "default" && "bg-active text-foreground hover:bg-active/80",
        variant === "secondary" && "bg-elevated text-foreground hover:bg-elevated/80",
        variant === "destructive" && "bg-danger text-foreground hover:bg-danger/80",
        variant === "outline" && "border border-border bg-panel text-foreground hover:bg-elevated",
        className
      )}
      {...props}
    />
  );
}
