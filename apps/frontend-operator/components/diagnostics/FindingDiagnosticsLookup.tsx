import { Input } from "@/components/ui/input";

export function FindingDiagnosticsLookup({
  findingId,
  onChange
}: {
  findingId: string;
  onChange: (findingId: string) => void;
}) {
  return (
    <Input
      value={findingId}
      onChange={(event) => onChange(event.target.value.trim())}
      placeholder="finding UUID for diagnostics lookup"
    />
  );
}
