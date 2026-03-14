"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const navGroups = [
  {
    title: "Core Operations",
    links: [
      { href: "/overview", label: "Overview" },
      { href: "/campaigns", label: "Campaigns" },
      { href: "/recon", label: "Recon" },
      { href: "/triage", label: "Findings / Triage" },
      { href: "/approvals", label: "Approvals" },
      { href: "/exports", label: "Exports" }
    ]
  },
  {
    title: "SOC Intelligence",
    links: [
      { href: "/attack-surface", label: "Attack Surface" },
      { href: "/evidence", label: "Evidence" },
      { href: "/threat-intel", label: "Threat Intel" },
      { href: "/ioc", label: "IOC" },
      { href: "/timeline", label: "Timeline" },
      { href: "/analytics", label: "Analytics" },
      { href: "/playbooks", label: "Playbooks" },
      { href: "/alerts", label: "Alerts" },
      { href: "/system", label: "System" },
      { href: "/diagnostics", label: "Diagnostics (Legacy)" }
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
            const active = pathname === link.href || pathname.startsWith(`${link.href}/`);
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
