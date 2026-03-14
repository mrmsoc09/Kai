import { PageContainer } from "@/components/layout/PageContainer";
import { SidebarNav } from "@/components/layout/SidebarNav";
import { Topbar } from "@/components/layout/Topbar";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="operator-shell bg-background text-foreground">
      <Topbar />
      <div className="grid min-h-[calc(100vh-72px)] grid-cols-1 lg:grid-cols-[220px_1fr]">
        <aside className="border-r border-border bg-panel p-3">
          <SidebarNav />
        </aside>
        <main>
          <PageContainer>{children}</PageContainer>
        </main>
      </div>
    </div>
  );
}
