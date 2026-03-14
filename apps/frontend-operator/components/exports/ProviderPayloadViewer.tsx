import { JsonViewer } from "@/components/data-display/JsonViewer";

export function ProviderPayloadViewer({ payload }: { payload: Record<string, unknown> }) {
  return <JsonViewer value={payload} />;
}
