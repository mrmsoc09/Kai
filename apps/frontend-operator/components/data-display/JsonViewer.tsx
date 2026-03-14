export function JsonViewer({
  value,
  heightClass = "max-h-72"
}: {
  value: unknown;
  heightClass?: string;
}) {
  return (
    <pre className={`${heightClass} overflow-auto rounded-md border border-border bg-background p-2 text-[11px] text-foreground`}>
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
