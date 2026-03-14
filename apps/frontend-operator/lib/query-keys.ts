export const queryKeys = {
  campaigns: {
    all: ["campaigns"] as const,
    tracked: () => [...queryKeys.campaigns.all, "tracked"] as const,
    detail: (campaignId: string) => [...queryKeys.campaigns.all, "detail", campaignId] as const,
    diagnostics: (campaignId: string) =>
      [...queryKeys.campaigns.all, "diagnostics", campaignId] as const
  },
  findings: {
    all: ["findings"] as const,
    queue: (campaignId?: string) => [...queryKeys.findings.all, "queue", campaignId ?? "all"] as const,
    detail: (findingId: string) => [...queryKeys.findings.all, "detail", findingId] as const,
    exportPreview: (findingId: string, provider: string, draftId?: string) =>
      [...queryKeys.findings.all, "export-preview", findingId, provider, draftId ?? "auto"] as const
  },
  diagnostics: {
    summary: () => ["diagnostics", "summary"] as const,
    health: () => ["diagnostics", "health"] as const,
    ready: () => ["diagnostics", "ready"] as const
  },
  approvals: {
    inferredQueue: (campaignIds: string[]) => ["approvals", "inferred", ...campaignIds] as const
  },
  soc: {
    overview: (campaignIds: string[]) => ["soc", "overview", ...campaignIds] as const,
    attackSurface: (campaignId?: string) =>
      ["soc", "attack-surface", campaignId ?? "all"] as const,
    recon: (campaignIds: string[]) => ["soc", "recon", ...campaignIds] as const,
    triage: (campaignId?: string) => ["soc", "triage", campaignId ?? "all"] as const,
    evidence: (campaignId?: string) => ["soc", "evidence", campaignId ?? "all"] as const,
    threatIntel: (campaignId?: string) => ["soc", "threat-intel", campaignId ?? "all"] as const,
    ioc: (campaignId?: string) => ["soc", "ioc", campaignId ?? "all"] as const,
    timeline: (campaignId?: string, findingId?: string) =>
      ["soc", "timeline", campaignId ?? "none", findingId ?? "none"] as const,
    analytics: (campaignIds: string[]) => ["soc", "analytics", ...campaignIds] as const,
    playbooks: (campaignIds: string[]) => ["soc", "playbooks", ...campaignIds] as const,
    alerts: (campaignIds: string[]) => ["soc", "alerts", ...campaignIds] as const,
    system: (campaignId?: string, findingId?: string) =>
      ["soc", "system", campaignId ?? "none", findingId ?? "none"] as const
  }
};
