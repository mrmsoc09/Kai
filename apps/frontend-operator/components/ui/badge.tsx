import * as React from "react";

import { cn } from "@/lib/utils";

type BadgeVariant = "default" | "success" | "danger" | "warning" | "info" | "muted" | "finding";

const variantStyles: Record<BadgeVariant, React.CSSProperties> = {
  default: { color: "#00FF41", border: "1px solid #003300", background: "rgba(0,255,65,0.08)" },
  success: { color: "#00FF41", border: "1px solid #003300", background: "rgba(0,255,65,0.08)", textShadow: "0 0 4px rgba(0,255,65,0.4)" },
  danger:  { color: "#FF3333", border: "1px solid #660000", background: "rgba(255,51,51,0.08)" },
  warning: { color: "#FFD700", border: "1px solid #665500", background: "rgba(255,215,0,0.08)" },
  info:    { color: "#00FFFF", border: "1px solid #005555", background: "rgba(0,255,255,0.06)" },
  muted:   { color: "#007A1E", border: "1px solid #002200", background: "rgba(0,0,0,0.4)" },
  finding: { color: "#FF00FF", border: "1px solid #440044", background: "rgba(255,0,255,0.06)", textShadow: "0 0 4px rgba(255,0,255,0.4)" },
};

type BadgeProps = React.HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
};

export function Badge({ className, variant = "default", style, ...props }: BadgeProps) {
  return (
    <span
      className={cn("inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium", className)}
      style={{
        fontFamily: "IBM Plex Mono, monospace",
        letterSpacing: "0.06em",
        ...variantStyles[variant],
        ...style,
      }}
      {...props}
    />
  );
}
