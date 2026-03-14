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
  },
  bugBounty: {
    all: ["bug-bounty"] as const,
    programs: () => [...queryKeys.bugBounty.all, "programs"] as const,
    targets: (programId?: string) => [...queryKeys.bugBounty.all, "targets", programId ?? "all"] as const,
    schedules: (programId?: string, status?: string) =>
      [...queryKeys.bugBounty.all, "schedules", programId ?? "all", status ?? "all"] as const,
    schedulerStatus: (programId?: string) =>
      [...queryKeys.bugBounty.all, "scheduler-status", programId ?? "all"] as const,
    readiness: (programId?: string, decisionStatus?: string) =>
      [...queryKeys.bugBounty.all, "readiness", programId ?? "all", decisionStatus ?? "all"] as const,
    deltas: (programId?: string, scopeTargetId?: string) =>
      [...queryKeys.bugBounty.all, "deltas", programId ?? "all", scopeTargetId ?? "all"] as const,
    candidates: (programId?: string, status?: string) =>
      [...queryKeys.bugBounty.all, "candidates", programId ?? "all", status ?? "all"] as const,
    alerts: (programId?: string, status?: string, severity?: string) =>
      [...queryKeys.bugBounty.all, "alerts", programId ?? "all", status ?? "all", severity ?? "all"] as const,
    alertsSummary: (programId?: string) =>
      [...queryKeys.bugBounty.all, "alerts-summary", programId ?? "all"] as const,
    cases: (programId?: string, status?: string, priority?: string, owner?: string) =>
      [
        ...queryKeys.bugBounty.all,
        "cases",
        programId ?? "all",
        status ?? "all",
        priority ?? "all",
        owner ?? "all"
      ] as const,
    caseDetail: (caseId: string) => [...queryKeys.bugBounty.all, "case", caseId] as const,
    signals: (programId?: string, scopeTargetId?: string) =>
      [...queryKeys.bugBounty.all, "signals", programId ?? "all", scopeTargetId ?? "all"] as const,
    scores: (programId?: string, scopeTargetId?: string) =>
      [...queryKeys.bugBounty.all, "scores", programId ?? "all", scopeTargetId ?? "all"] as const,
    adaptiveActions: (programId?: string, actionStatus?: string) =>
      [...queryKeys.bugBounty.all, "adaptive", programId ?? "all", actionStatus ?? "all"] as const,
    analystBriefing: (programId?: string) =>
      [...queryKeys.bugBounty.all, "analyst-briefing", programId ?? "all"] as const,
    phase7: {
      run: () => [...queryKeys.bugBounty.all, "phase7-run"] as const,
      predictions: (programId?: string, scopeTargetId?: string) =>
        [...queryKeys.bugBounty.all, "phase7", "predictions", programId ?? "all", scopeTargetId ?? "all"] as const,
      rankings: (programId?: string, subjectType?: string) =>
        [...queryKeys.bugBounty.all, "phase7", "rankings", programId ?? "all", subjectType ?? "all"] as const,
      yields: (programId?: string, scopeTargetId?: string) =>
        [...queryKeys.bugBounty.all, "phase7", "yields", programId ?? "all", scopeTargetId ?? "all"] as const,
      duplicateRisk: (programId?: string, riskBand?: string) =>
        [...queryKeys.bugBounty.all, "phase7", "duplicate-risk", programId ?? "all", riskBand ?? "all"] as const,
      evidenceCompleteness: (programId?: string, readinessState?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase7",
          "evidence-completeness",
          programId ?? "all",
          readinessState ?? "all"
        ] as const,
      recommendations: (programId?: string, recommendationStatus?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase7",
          "recommendations",
          programId ?? "all",
          recommendationStatus ?? "all"
        ] as const,
      analystSupport: (programId?: string) =>
        [...queryKeys.bugBounty.all, "phase7", "analyst-support", programId ?? "all"] as const
    },
    retrospective: {
      run: () => [...queryKeys.bugBounty.all, "phase10-run"] as const,
      summary: (programId?: string, windowDays?: number) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10",
          "summary",
          programId ?? "all",
          windowDays ?? 30
        ] as const,
      workflows: (programId?: string) =>
        [...queryKeys.bugBounty.all, "phase10", "workflows", programId ?? "all"] as const,
      targets: (programId?: string, scopeTargetId?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10",
          "targets",
          programId ?? "all",
          scopeTargetId ?? "all"
        ] as const,
      recommendations: (programId?: string, outcomeStatus?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10",
          "recommendations",
          programId ?? "all",
          outcomeStatus ?? "all"
        ] as const,
      alerts: (programId?: string, outcomeStatus?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10",
          "alerts",
          programId ?? "all",
          outcomeStatus ?? "all"
        ] as const
    },
    agents: {
      registry: (enabledOnly?: boolean, category?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10_5",
          "agents",
          enabledOnly ? "enabled" : "all",
          category ?? "all"
        ] as const,
      executions: (programId?: string, agentId?: string, executionStatus?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10_5",
          "agent-executions",
          programId ?? "all",
          agentId ?? "all",
          executionStatus ?? "all"
        ] as const,
      evaluations: (agentId?: string, status?: string) =>
        [
          ...queryKeys.bugBounty.all,
          "phase10_5",
          "agent-evaluations",
          agentId ?? "all",
          status ?? "all"
        ] as const
    },
    toolsHealth: () => [...queryKeys.bugBounty.all, "tools-health"] as const
  }
};
