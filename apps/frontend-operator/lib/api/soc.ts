import { getCampaign, getCampaignDiagnostics } from "@/lib/api/campaigns";
import { getHealth, getReadiness, getDiagnosticsSummary } from "@/lib/api/diagnostics";
import { getFindingDiagnostics, getFindingsReviewQueue } from "@/lib/api/findings";

export const socApi = {
  getCampaign,
  getCampaignDiagnostics,
  getDiagnosticsSummary,
  getHealth,
  getReadiness,
  getFindingsReviewQueue,
  getFindingDiagnostics
};
