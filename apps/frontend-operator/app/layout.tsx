import type { Metadata } from "next";

import { AppShell } from "@/components/layout/AppShell";

import { AppProviders } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "KAI / K1 — Operator Console",
  description:
    "Autonomous bug bounty hunting platform — operator control plane for missions, targets, findings, triage, approvals, and threat intelligence.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
