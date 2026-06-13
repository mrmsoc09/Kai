"use client";

import { useOperatorTheme } from "@/lib/theme";

type PageHeaderProps = {
  title: string;
  description?: string;
  actions?: React.ReactNode;
};

export function PageHeader({ title, description, actions }: PageHeaderProps) {
  const { colors, mode } = useOperatorTheme();
  return (
    <div
      style={{
        marginBottom: "1rem",
        paddingBottom: "0.75rem",
        borderBottom: `1px solid ${colors.border}`,
        display: "flex",
        flexWrap: "wrap",
        alignItems: "flex-start",
        justifyContent: "space-between",
        gap: "0.75rem",
      }}
    >
      <div>
        {/* Breadcrumb-style prefix */}
        <p
          style={{
            fontSize: "0.6rem",
            letterSpacing: "0.2em",
            textTransform: "uppercase",
            color: colors.textMuted,
            fontFamily: "IBM Plex Mono, monospace",
            marginBottom: "2px",
          }}
        >
          {"// KAI OPERATOR ▸"}
        </p>
        <h2
          style={{
            fontSize: "1.1rem",
            fontWeight: 700,
            color: colors.accent,
            fontFamily: "IBM Plex Mono, monospace",
            letterSpacing: "0.1em",
            textTransform: "uppercase",
            textShadow: mode === "dark" ? `0 0 8px ${colors.accentGlow}` : "none",
          }}
        >
          <span style={{ color: colors.highlight, marginRight: "0.4em" }}>›</span>
          {title}
          <span
            style={{
              display: "inline-block",
              width: 8,
              marginLeft: 4,
              animation: "blink 1s step-end infinite",
              color: colors.accent,
            }}
          >
            _
          </span>
        </h2>
        {description ? (
          <p
          style={{
            marginTop: "3px",
            fontSize: "0.7rem",
            color: colors.textMuted,
            fontFamily: "IBM Plex Mono, monospace",
            letterSpacing: "0.04em",
          }}
          >
            {description}
          </p>
        ) : null}
      </div>
      {actions ? <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>{actions}</div> : null}
    </div>
  );
}
