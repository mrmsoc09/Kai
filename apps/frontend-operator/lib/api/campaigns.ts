import { requestJson } from "@/lib/api/client";
import type {
  CampaignApprovalDecisionResponse,
  CampaignCorrelationResponse,
  CampaignDiagnosticsResponse,
  CampaignScheduleSummary,
  CampaignStartRequest,
  CampaignStartResponse,
  CampaignStatusResponse
} from "@/lib/types";

export function startCampaign(body: CampaignStartRequest) {
  return requestJson<CampaignStartResponse>("/api/v1/campaigns/start", { method: "POST", body });
}

export function getCampaign(campaignId: string, signal?: AbortSignal) {
  return requestJson<CampaignStatusResponse>(`/api/v1/campaigns/${campaignId}`, { signal });
}

export function scheduleCampaign(campaignId: string) {
  return requestJson<CampaignScheduleSummary>(`/api/v1/campaigns/${campaignId}/schedule`, {
    method: "POST"
  });
}

export function correlateCampaign(campaignId: string) {
  return requestJson<CampaignCorrelationResponse>(`/api/v1/campaigns/${campaignId}/correlate`, {
    method: "POST"
  });
}

export function getCampaignDiagnostics(campaignId: string, signal?: AbortSignal) {
  return requestJson<CampaignDiagnosticsResponse>(`/api/v1/campaigns/${campaignId}/diagnostics`, {
    signal
  });
}

export function decideApprovalGate(
  gateId: string,
  body: {
    status: string;
    decided_by: string;
    operator_notes?: string;
    decision_payload_json?: Record<string, unknown>;
    intention_id?: string;
    trigger_scheduler?: boolean;
  }
) {
  return requestJson<CampaignApprovalDecisionResponse>(`/api/v1/campaigns/approvals/${gateId}/decision`, {
    method: "POST",
    body
  });
}
