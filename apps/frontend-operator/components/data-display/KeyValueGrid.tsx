export function KeyValueGrid({
  items
}: {
  items: Array<{ key: string; value: React.ReactNode }>;
}) {
  return (
    <dl className="grid gap-2 md:grid-cols-2">
      {items.map((item) => (
        <div key={item.key} className="rounded-md border border-border bg-elevated p-2">
          <dt className="text-xs uppercase tracking-wide text-muted">{item.key}</dt>
          <dd className="mt-1 text-sm text-foreground">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
