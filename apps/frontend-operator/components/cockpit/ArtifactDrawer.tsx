import { EmptyState } from "@/components/data-display/EmptyState";
import { Drawer } from "@/components/ui/drawer";

export type ArtifactReference = {
  id: string;
  label: string;
  uri: string;
  source?: string;
};

export function ArtifactDrawer({
  title = "Artifacts",
  items
}: {
  title?: string;
  items: ArtifactReference[];
}) {
  return (
    <Drawer className="space-y-3">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      {items.length === 0 ? (
        <EmptyState
          title="No linked artifacts"
          description="Artifact list is currently empty for this mission context."
        />
      ) : (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id} className="rounded-md border border-border bg-elevated p-2">
              <p className="text-xs font-medium text-foreground">{item.label}</p>
              <a
                href={item.uri}
                className="break-all font-mono text-xs text-active hover:underline"
                target="_blank"
                rel="noreferrer"
              >
                {item.uri}
              </a>
              {item.source ? <p className="mt-1 text-xs text-muted">source: {item.source}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </Drawer>
  );
}
