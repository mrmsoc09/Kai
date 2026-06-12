"use client";

import { MatrixRain } from "@/components/effects/MatrixRain";
import { PageContainer } from "@/components/layout/PageContainer";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { Topbar } from "@/components/layout/Topbar";
import { useOperatorTheme } from "@/lib/theme";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { colors } = useOperatorTheme();
  return (
    <div className="operator-shell bg-background text-foreground" style={{ position: "relative", background: colors.shellBg, color: colors.text }}>
      <MatrixRain />

      {/* ── CRT scanline overlay ── */}
      <div className="scanline-overlay" style={{ opacity: colors.mode === "dark" ? 1 : 0.12 }} />
      <div className="crt-vignette" style={{ opacity: colors.mode === "dark" ? 1 : 0.18 }} />

      {/* ── UI chrome (above canvas, z-index: auto) ── */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <Topbar />
        <div className="grid min-h-[calc(100vh-72px)] grid-cols-1 lg:grid-cols-[220px_1fr]">
          <aside
            className="border-r border-border p-3"
            style={{ background: colors.panelSoft, borderRightColor: colors.border }}
          >
            <SidebarNav />
          </aside>
          <main style={{ background: colors.pageBg }}>
            <PageContainer>{children}</PageContainer>
          </main>
        </div>
      </div>
    </div>
  );
}
