"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

type NavLink = {
  href: string;
  label: string;
  aliases?: string[];
};

const navGroups: Array<{ title: string; links: NavLink[] }> = [
  {
    title: "Operator Cockpit",
    links: [
      { href: "/overview", label: "Overview / Action Board" },
      { href: "/missions", label: "Missions", aliases: ["/campaigns"] },
      { href: "/mission-control", label: "Mission Control" },
      { href: "/findings", label: "Findings", aliases: ["/triage", "/cases"] },
      { href: "/evidence", label: "Evidence", aliases: ["/attack-surface"] },
      { href: "/reports", label: "Reports", aliases: ["/exports"] },
      { href: "/approvals", label: "Approvals" },
      { href: "/terminal", label: "Terminal" },
      { href: "/programs", label: "Programs / Targets", aliases: ["/targets"] },
      { href: "/system", label: "System / Logs", aliases: ["/logs", "/diagnostics"] }
    ]
  },
  {
    title: "Extended Surfaces",
    links: [
      { href: "/opportunities", label: "Opportunities" },
      { href: "/predictions", label: "Predictions" },
      { href: "/agents", label: "Agents" },
      { href: "/briefing", label: "Analyst Briefing" },
      { href: "/recon", label: "Recon" },
      { href: "/threat-intel", label: "Threat Intel" },
      { href: "/ioc", label: "IOC" },
      { href: "/timeline", label: "Timeline" },
      { href: "/analytics", label: "Analytics" },
      { href: "/playbooks", label: "Playbooks" },
      { href: "/alerts", label: "Alerts" },
      { href: "/retrospective", label: "Retrospective" }
    ]
  }
] as const;

export function SidebarNav() {
  const pathname = usePathname();
  return (
    <nav className="space-y-4">
      {navGroups.map((group) => (
        <div key={group.title} className="space-y-1">
          <p className="px-1 text-xs font-semibold uppercase tracking-wide text-muted">{group.title}</p>
          {group.links.map((link) => {
            const matchable = [link.href, ...(link.aliases ?? [])];
            const active = matchable.some(
              (candidate) => pathname === candidate || pathname.startsWith(`${candidate}/`)
            );
            return (
              <Link
                key={link.href}
                href={link.href}
                className={cn(
                  "block rounded-md border px-3 py-2 text-sm font-medium",
                  active
                    ? "border-active/40 bg-active/20 text-active"
                    : "border-border bg-panel text-foreground hover:bg-elevated"
                )}
              >
                {link.label}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
