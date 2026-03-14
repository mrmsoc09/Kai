import type { Metadata } from "next";

import { AppShell } from "@/components/layout/AppShell";

import { AppProviders } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kai Operator Console",
  description: "Operator control plane for campaign execution, review, approvals, and diagnostics."
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
