import { Input } from "@/components/ui/input";

export function CampaignDiagnosticsLookup({
  campaignId,
  onChange
}: {
  campaignId: string;
  onChange: (campaignId: string) => void;
}) {
  return (
    <Input
      value={campaignId}
      onChange={(event) => onChange(event.target.value.trim())}
      placeholder="campaign UUID for diagnostics lookup"
    />
  );
}
