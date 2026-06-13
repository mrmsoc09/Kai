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
    <html lang="en" data-theme="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function () {
                try {
                  var mode = localStorage.getItem('k1-operator-theme');
                  if (mode !== 'light' && mode !== 'dark') {
                    mode = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
                  }
                  document.documentElement.dataset.theme = mode;
                  document.documentElement.style.colorScheme = mode;
                } catch (e) {}
              })();
            `,
          }}
        />
      </head>
      <body>
        <AppProviders>
          <AppShell>{children}</AppShell>
        </AppProviders>
      </body>
    </html>
  );
}
