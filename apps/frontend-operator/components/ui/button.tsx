import * as React from "react";

import { cn } from "@/lib/utils";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "default" | "secondary" | "destructive" | "outline" | "ghost" | "warning";
  size?: "sm" | "md" | "lg";
};

const variantStyles: Record<NonNullable<ButtonProps["variant"]>, React.CSSProperties> = {
  default: {
    background: "rgba(0,255,65,0.12)",
    border: "1px solid rgba(0,255,65,0.4)",
    color: "#00FF41",
    textShadow: "0 0 6px rgba(0,255,65,0.5)",
    boxShadow: "0 0 8px rgba(0,255,65,0.1)",
  },
  secondary: {
    background: "rgba(0,0,0,0.6)",
    border: "1px solid #003300",
    color: "#007A1E",
  },
  destructive: {
    background: "rgba(255,51,51,0.12)",
    border: "1px solid rgba(255,51,51,0.4)",
    color: "#FF3333",
    textShadow: "0 0 6px rgba(255,51,51,0.5)",
    boxShadow: "0 0 8px rgba(255,51,51,0.1)",
  },
  outline: {
    background: "transparent",
    border: "1px solid #003300",
    color: "#007A1E",
  },
  ghost: {
    background: "transparent",
    border: "1px solid transparent",
    color: "#007A1E",
  },
  warning: {
    background: "rgba(255,215,0,0.1)",
    border: "1px solid rgba(255,215,0,0.4)",
    color: "#FFD700",
    textShadow: "0 0 6px rgba(255,215,0,0.4)",
  },
};

export function Button({
  className,
  variant = "default",
  size = "md",
  style,
  ...props
}: ButtonProps) {
  const sizeClass =
    size === "sm" ? "h-7 px-2 text-xs" : size === "lg" ? "h-10 px-5 text-sm" : "h-8 px-3 text-xs";

  return (
    <button
      className={cn(
        "inline-flex items-center justify-center rounded-sm font-medium transition-all duration-100 disabled:cursor-not-allowed disabled:opacity-40",
        sizeClass,
        className
      )}
      style={{
        fontFamily: "IBM Plex Mono, monospace",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        ...variantStyles[variant],
        ...style,
      }}
      {...props}
    />
  );
}
