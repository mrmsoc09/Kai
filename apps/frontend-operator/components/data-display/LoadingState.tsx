export function LoadingState({ label = "Loading..." }: { label?: string }) {
  return <div className="rounded-md border border-border bg-panel p-6 text-sm text-muted">{label}</div>;
}
