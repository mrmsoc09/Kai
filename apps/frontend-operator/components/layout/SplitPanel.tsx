export function SplitPanel({
  left,
  right
}: {
  left: React.ReactNode;
  right: React.ReactNode;
}) {
  return <div className="grid gap-4 xl:grid-cols-2">{left}{right}</div>;
}
