export function Topbar() {
  return (
    <header className="border-b border-border bg-panel px-4 py-3">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-muted">Kai / K1</p>
          <h1 className="text-lg font-semibold text-foreground">Operator Console</h1>
        </div>
        <div className="rounded-md border border-border bg-elevated px-2 py-1 text-xs text-muted">
          API: {process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8080"}
        </div>
      </div>
    </header>
  );
}
