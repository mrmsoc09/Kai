export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="rounded-md border border-border bg-panel p-6 text-sm text-muted">
      <p className="font-semibold text-foreground">{title}</p>
      <p className="mt-1">{description}</p>
    </div>
  );
}
