import { MatrixRain } from "@/components/effects/MatrixRain";
import { PageContainer } from "@/components/layout/PageContainer";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="operator-shell bg-background text-foreground" style={{ position: "relative" }}>
      {/* ── Matrix rain canvas (behind everything) ── */}
      <MatrixRain />

      {/* ── CRT scanline overlay ── */}
      <div className="scanline-overlay" />
      <div className="crt-vignette" />

      {/* ── UI chrome (above canvas, z-index: auto) ── */}
      <div style={{ position: "relative", zIndex: 1 }}>
        <Topbar />
        <div className="grid min-h-[calc(100vh-72px)] grid-cols-1 lg:grid-cols-[220px_1fr]">
          <aside
            className="border-r border-border p-3"
            style={{ background: "rgba(0,0,0,0.88)" }}
          >
            <SidebarNav />
          </aside>
          <main style={{ background: "rgba(0,0,0,0.72)" }}>
            <PageContainer>{children}</PageContainer>
          </main>
        </div>
      </div>
    </div>
  );
}
