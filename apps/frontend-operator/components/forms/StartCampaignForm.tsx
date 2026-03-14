import { useState } from "react";

import type { CampaignStartRequest } from "@/lib/types";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

type StartCampaignFormProps = {
  onSubmit: (request: CampaignStartRequest) => void;
  loading?: boolean;
};

const defaults: CampaignStartRequest = {
  initiated_by: "operator.console",
  declared_goal: ""
};

export function StartCampaignForm({ onSubmit, loading = false }: StartCampaignFormProps) {
  const [form, setForm] = useState<CampaignStartRequest>(defaults);

  return (
    <form
      className="grid gap-3 md:grid-cols-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          initiated_by: form.initiated_by,
          declared_goal: form.declared_goal,
          declared_reason: form.declared_reason || undefined,
          campaign_name: form.campaign_name || undefined,
          program_name: form.program_name || undefined,
          target: form.target || undefined
        });
      }}
    >
      <Input
        required
        value={form.initiated_by}
        onChange={(event) => setForm((prev) => ({ ...prev, initiated_by: event.target.value }))}
        placeholder="initiated_by"
      />
      <Input
        value={form.campaign_name ?? ""}
        onChange={(event) => setForm((prev) => ({ ...prev, campaign_name: event.target.value }))}
        placeholder="campaign_name (optional)"
      />
      <Input
        value={form.program_name ?? ""}
        onChange={(event) => setForm((prev) => ({ ...prev, program_name: event.target.value }))}
        placeholder="program_name (optional)"
      />
      <Input
        value={form.target ?? ""}
        onChange={(event) => setForm((prev) => ({ ...prev, target: event.target.value }))}
        placeholder="target (optional)"
      />
      <div className="md:col-span-2">
        <Textarea
          required
          value={form.declared_goal}
          onChange={(event) => setForm((prev) => ({ ...prev, declared_goal: event.target.value }))}
          placeholder="declared_goal"
        />
      </div>
      <div className="md:col-span-2">
        <Textarea
          value={form.declared_reason ?? ""}
          onChange={(event) => setForm((prev) => ({ ...prev, declared_reason: event.target.value }))}
          placeholder="declared_reason (optional)"
        />
      </div>
      <div className="md:col-span-2">
        <Button type="submit" disabled={loading}>
          {loading ? "Starting..." : "Start Campaign"}
        </Button>
      </div>
    </form>
  );
}
