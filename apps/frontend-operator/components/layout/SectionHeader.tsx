export function SectionHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div className="mb-3">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-muted">{title}</h3>
      {subtitle ? <p className="text-xs text-muted">{subtitle}</p> : null}
    </div>
  );
}
