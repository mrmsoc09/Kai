import type { ExportProvider } from "@/lib/api/exports";

import { Select } from "@/components/ui/select";

export function ProviderSelector({
  provider,
  onChange
}: {
  provider: ExportProvider;
  onChange: (provider: ExportProvider) => void;
}) {
  return (
    <Select value={provider} onChange={(event) => onChange(event.target.value as ExportProvider)}>
      <option value="hackerone">hackerone</option>
      <option value="bugcrowd">bugcrowd</option>
      <option value="intigriti">intigriti</option>
    </Select>
  );
}
