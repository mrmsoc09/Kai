import type { CampaignStartRequest } from "@/lib/types";

import { ErrorState } from "@/components/data-display/ErrorState";
import { StartCampaignForm } from "@/components/forms/StartCampaignForm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function StartCampaignDialog({
  onSubmit,
  loading = false,
  error
}: {
  onSubmit: (request: CampaignStartRequest) => void;
  loading?: boolean;
  error?: unknown;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Start Campaign</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <StartCampaignForm onSubmit={onSubmit} loading={loading} />
        {error ? <ErrorState error={error} title="Campaign start failed" /> : null}
      </CardContent>
    </Card>
  );
}
