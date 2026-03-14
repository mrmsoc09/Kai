import { Alert } from "@/components/ui/alert";

export function BackendSupportPending({
  title,
  description
}: {
  title: string;
  description: string;
}) {
  return (
    <Alert className="border-review/40 bg-review/10">
      <p className="text-sm font-semibold text-foreground">{title}</p>
      <p className="mt-1 text-sm text-muted">{description}</p>
    </Alert>
  );
}
