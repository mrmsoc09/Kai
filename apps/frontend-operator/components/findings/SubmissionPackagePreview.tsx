import { JsonViewer } from "@/components/data-display/JsonViewer";
import { EmptyState } from "@/components/data-display/EmptyState";

export function SubmissionPackagePreview({
  packageJson
}: {
  packageJson: Record<string, unknown> | null;
}) {
  if (!packageJson) {
    return (
      <EmptyState
        title="No prepared package"
        description="Prepare submission to generate a package preview."
      />
    );
  }
  return <JsonViewer value={packageJson} />;
}
