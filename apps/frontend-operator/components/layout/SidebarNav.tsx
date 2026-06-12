"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useOperatorTheme } from "@/lib/theme";

type NavLink = {
  href: string;
  label: string;
  aliases?: string[];
  icon?: string; /* ASCII/unicode prefix glyph */
};

const navGroups: Array<{ title: string; links: NavLink[] }> = [
  {
    title: "Operator Cockpit",
    links: [
      { href: "/overview",        label: "Overview / Action Board", icon: "▸" },
      { href: "/missions",        label: "Missions",                icon: "◈", aliases: ["/campaigns"] },
      { href: "/scan-queue",      label: "Scan Queue",              icon: "⬡" },
      { href: "/mission-control", label: "Mission Control",         icon: "⊕" },
      { href: "/findings",        label: "Findings",                icon: "◉", aliases: ["/triage", "/cases"] },
      { href: "/evidence",        label: "Evidence",                icon: "◎", aliases: ["/attack-surface"] },
      { href: "/reports",         label: "Reports",                 icon: "≡",  aliases: ["/exports"] },
      { href: "/approvals",       label: "Approvals",               icon: "⚑" },
      { href: "/terminal",        label: "Terminal",                icon: "▶" },
      { href: "/programs",          label: "Programs / Targets",      icon: "◇", aliases: ["/targets"] },
      { href: "/hunter-accounts",  label: "Hunter Accounts",         icon: "⚿" },
      { href: "/system",           label: "System / Logs",           icon: "⌘", aliases: ["/logs", "/diagnostics"] },
    ],
  },
  {
    title: "Extended Surfaces",
    links: [
      { href: "/opportunities",  label: "Opportunities",    icon: "◆" },
      { href: "/predictions",    label: "Predictions",      icon: "⟡" },
      { href: "/agents",         label: "Agents",           icon: "⚙" },
      { href: "/briefing",       label: "Analyst Briefing", icon: "📡" },
      { href: "/recon",          label: "Recon",            icon: "⊗" },
      { href: "/threat-intel",   label: "Threat Intel",     icon: "☢" },
      { href: "/ioc",            label: "IOC",              icon: "⊘" },
      { href: "/timeline",       label: "Timeline",         icon: "⏱" },
      { href: "/analytics",      label: "Analytics",        icon: "≈" },
      { href: "/playbooks",      label: "Playbooks",        icon: "⊞" },
      { href: "/alerts",         label: "Alerts",           icon: "⚠" },
      { href: "/retrospective",  label: "Retrospective",    icon: "↺" },
    ],
  },
] as const;

export function SidebarNav() {
  const pathname = usePathname();
  const { colors, mode } = useOperatorTheme();

  return (
    <nav style={{ fontFamily: "IBM Plex Mono, monospace" }}>
      {navGroups.map((group) => (
        <div key={group.title} style={{ marginBottom: "1.25rem" }}>
          {/* Group header */}
          <p
            style={{
              fontSize: "0.6rem",
              textTransform: "uppercase",
              letterSpacing: "0.2em",
              color: colors.highlight,
              padding: "0 4px",
              marginBottom: "0.35rem",
              borderLeft: `2px solid ${colors.border}`,
              paddingLeft: "6px",
            }}
          >
            {group.title}
          </p>

          <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            {group.links.map((link) => {
              const matchable = [link.href, ...(link.aliases ?? [])];
              const active = matchable.some(
                (candidate) =>
                  pathname === candidate || pathname.startsWith(`${candidate}/`)
              );

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.45rem",
                    padding: "5px 8px",
                    borderRadius: "3px",
                    fontSize: "0.72rem",
                    fontFamily: "IBM Plex Mono, monospace",
                    letterSpacing: "0.04em",
                    textDecoration: "none",
                    transition: "all 0.1s ease",
                    ...(active
                      ? {
                          background: colors.accentSoft,
                          border: `1px solid ${colors.borderStrong}`,
                          color: colors.accent,
                          textShadow: mode === "dark" ? `0 0 6px ${colors.accentGlow}` : "none",
                          boxShadow: `inset 0 0 8px ${colors.accentSoft}`,
                        }
                      : {
                          background: colors.panelSoft,
                          border: `1px solid ${colors.border}`,
                          color: colors.textMuted,
                        }),
                  }}
                  onMouseEnter={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.color = colors.accent;
                      (e.currentTarget as HTMLAnchorElement).style.borderColor = colors.borderStrong;
                      (e.currentTarget as HTMLAnchorElement).style.background = colors.highlightSoft;
                      (e.currentTarget as HTMLAnchorElement).style.textShadow = mode === "dark" ? `0 0 4px ${colors.accentGlow}` : "none";
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!active) {
                      (e.currentTarget as HTMLAnchorElement).style.color = colors.textMuted;
                      (e.currentTarget as HTMLAnchorElement).style.borderColor = colors.border;
                      (e.currentTarget as HTMLAnchorElement).style.background = colors.panelSoft;
                      (e.currentTarget as HTMLAnchorElement).style.textShadow = "";
                    }
                  }}
                >
                  {/* Icon glyph */}
                  <span
                    style={{
                      fontSize: "0.65rem",
                      color: active ? colors.accent : colors.border,
                      minWidth: "12px",
                      textAlign: "center",
                    }}
                  >
                    {link.icon ?? "›"}
                  </span>

                  {/* Label */}
                  <span style={{ flex: 1 }}>{link.label}</span>

                  {/* Active indicator — right blinking dot */}
                  {active && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 5,
                        height: 5,
                        borderRadius: "50%",
                        background: colors.accent,
                        boxShadow: `0 0 4px ${colors.accent}`,
                        animation: "blink 1.2s step-end infinite",
                        flexShrink: 0,
                      }}
                    />
                  )}
                </Link>
              );
            })}
          </div>
        </div>
      ))}

      {/* Footer system status */}
      <div
        style={{
          marginTop: "1rem",
          padding: "6px 8px",
          borderTop: `1px solid ${colors.border}`,
          fontSize: "0.6rem",
          color: colors.textMuted,
          fontFamily: "IBM Plex Mono, monospace",
          letterSpacing: "0.08em",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between" }}>
          <span>AGENTS</span>
          <span style={{ color: colors.highlight }}>STANDBY</span>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", marginTop: 2 }}>
          <span>MISSION</span>
          <span style={{ color: colors.highlight }}>IDLE</span>
        </div>
      </div>
    </nav>
  );
}
