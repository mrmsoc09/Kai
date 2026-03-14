import type { AuditEvent, CampaignDiagnosticsResponse, CampaignStatusResponse, FindingQueueItem } from "@/lib/types";

export type SocSeverity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";

export type SocAlert = {
  id: string;
  severity: SocSeverity;
  category: "APPROVAL" | "EXECUTION" | "EXPORT" | "CAMPAIGN" | "SYSTEM";
  title: string;
  description: string;
  campaignId?: string;
  findingId?: string;
  happenedAt?: string | null;
  sourceEventType?: string;
};

export type SocAssetRow = {
  key: string;
  asset: string;
  program: string;
  campaignId: string;
  findings: number;
  evidenceCount: number;
  readinessStates: string[];
  technologies: string[];
  source: "canonical_findings_queue" | "derived_observation_text";
};

export type SocReconPhaseRow = {
  campaignId: string;
  phaseJobId: string;
  phaseName: string;
  status: string;
  approvalRequired: boolean;
  dependsOnJobId: string | null;
  workerTaskId: string | null;
};

export type SocTimelineItem = {
  id: string;
  happenedAt: string | null;
  eventType: string;
  actor: string | null;
  message: string | null;
  campaignId?: string;
  findingId?: string;
  payload: Record<string, unknown>;
};

export type SocIocType = "IP" | "DOMAIN" | "URL" | "SHA256";

export type SocIocRow = {
  key: string;
  indicator: string;
  type: SocIocType;
  confidence: "derived";
  source: "observation" | "audit" | "finding_asset";
  campaignId?: string;
  findingId?: string;
  artifactId?: string;
};

export type SocPlaybookRow = {
  key: string;
  phaseName: string;
  campaigns: number;
  pending: number;
  running: number;
  blocked: number;
  completed: number;
  support: "backed" | "pending";
};

export type SocCampaignBundle = {
  campaign: CampaignStatusResponse;
  diagnostics: CampaignDiagnosticsResponse;
};

export type SocOverviewData = {
  campaigns: CampaignStatusResponse[];
  diagnostics: CampaignDiagnosticsResponse[];
  findingsQueue: FindingQueueItem[];
  alerts: SocAlert[];
  recentAuditEvents: AuditEvent[];
};
