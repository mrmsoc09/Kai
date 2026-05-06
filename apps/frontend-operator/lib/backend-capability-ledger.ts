export type BackendCoverageStatus = "FULL_UI" | "LINKED_UI" | "API_ONLY" | "OPTIONAL" | "UNMAPPED";

export type BackendRouterCapability = {
  id: string;
  includeExpr: string;
  prefix: string;
  endpointCount: number;
  status: BackendCoverageStatus;
  frontendSurface: string;
  note: string;
};

export type BackendMiddlewareCapability = {
  id: string;
  layer: string;
  frontendSurface: string;
  note: string;
};

const BACKEND_ROUTER_INDEX = [
  { id: "state", includeExpr: "state.router", prefix: "/state", endpointCount: 5 },
  { id: "metrics", includeExpr: "metrics.router", prefix: "/metrics", endpointCount: 3 },
  { id: "governance", includeExpr: "governance.router", prefix: "/governance", endpointCount: 2 },
  { id: "auth_routes", includeExpr: "auth_routes.router", prefix: "", endpointCount: 0 },
  { id: "auth", includeExpr: "auth.router", prefix: "/auth", endpointCount: 5 },
  { id: "scope", includeExpr: "scope.router", prefix: "/scope", endpointCount: 2 },
  { id: "safety", includeExpr: "safety.router", prefix: "/api/v1/safety", endpointCount: 4 },
  { id: "key_management", includeExpr: "key_management.router", prefix: "/api/keys", endpointCount: 16 },
  { id: "keys", includeExpr: "keys.router", prefix: "/keys", endpointCount: 1 },
  { id: "approvals", includeExpr: "approvals.router", prefix: "/approvals", endpointCount: 5 },
  { id: "hil_approval", includeExpr: "hil_approval.router", prefix: "/api/v1/approval", endpointCount: 8 },
  { id: "hil_findings", includeExpr: "hil_findings_router.router", prefix: "/findings", endpointCount: 4 },
  { id: "hil_workflow", includeExpr: "hil_workflow_router.router", prefix: "/hil", endpointCount: 3 },
  { id: "hil_scopes", includeExpr: "hil_scopes_router.router", prefix: "/scopes", endpointCount: 2 },
  { id: "hil_providers", includeExpr: "hil_providers_router.router", prefix: "/providers", endpointCount: 4 },
  { id: "hil_embeddings", includeExpr: "hil_embeddings_router.router", prefix: "/embeddings", endpointCount: 2 },
  { id: "artifact_signing", includeExpr: "artifact_signing.router", prefix: "/api/artifacts", endpointCount: 10 },
  { id: "dorks", includeExpr: "dorks.router", prefix: "/dorks", endpointCount: 3 },
  { id: "knowledge", includeExpr: "knowledge.router", prefix: "/knowledge", endpointCount: 4 },
  { id: "graph", includeExpr: "graph.router", prefix: "/api/v1/graph", endpointCount: 9 },
  { id: "persona_garden", includeExpr: "persona_garden.router", prefix: "/personas", endpointCount: 4 },
  { id: "tools", includeExpr: "tools", prefix: "/api/v1/tools", endpointCount: 16 },
  { id: "tasks", includeExpr: "tasks", prefix: "/api/v1/tasks", endpointCount: 2 },
  { id: "orchestrator", includeExpr: "orchestrator.router", prefix: "/orchestrator", endpointCount: 10 },
  { id: "planner", includeExpr: "planner.router", prefix: "/planner", endpointCount: 2 },
  { id: "chains", includeExpr: "chains.router", prefix: "/chains", endpointCount: 4 },
  { id: "embeddings", includeExpr: "embeddings.router", prefix: "/embeddings", endpointCount: 2 },
  { id: "intel", includeExpr: "intel.router", prefix: "/intel", endpointCount: 5 },
  { id: "mcp", includeExpr: "mcp.router", prefix: "/mcp", endpointCount: 1 },
  { id: "realtime", includeExpr: "realtime.router", prefix: "", endpointCount: 2 },
  { id: "terminal_chat", includeExpr: "terminal_chat.router", prefix: "", endpointCount: 3 },
  { id: "mission_control", includeExpr: "mission_control.router", prefix: "/missions", endpointCount: 7 },
  { id: "artifacts", includeExpr: "artifacts.router", prefix: "/artifacts", endpointCount: 3 },
  { id: "events", includeExpr: "events.router", prefix: "/events", endpointCount: 2 },
  { id: "simulation", includeExpr: "simulation.router", prefix: "/simulation", endpointCount: 3 },
  { id: "system", includeExpr: "system.router", prefix: "/system", endpointCount: 2 },
  { id: "vault", includeExpr: "vault.router", prefix: "/vault", endpointCount: 11 },
  { id: "credentials", includeExpr: "credentials.router", prefix: "/api/v1/credentials", endpointCount: 8 },
  { id: "model_bidding", includeExpr: "model_bidding.router", prefix: "/api/models", endpointCount: 5 },
  { id: "orchestration", includeExpr: "orchestration.router", prefix: "/api/orchestration", endpointCount: 16 },
  { id: "orchestration_v1", includeExpr: "orchestration_v1.router", prefix: "/api/v1/orchestration", endpointCount: 15 },
  { id: "autonomous", includeExpr: "autonomous.router", prefix: "/api/autonomous", endpointCount: 15 },
  { id: "agent_training", includeExpr: "agent_training.router", prefix: "/api/agents", endpointCount: 18 },
  { id: "finding_validation", includeExpr: "finding_validation.router", prefix: "/api/findings", endpointCount: 11 },
  { id: "validation", includeExpr: "validation.router", prefix: "/api/v1/validation", endpointCount: 4 },
  { id: "opportunities", includeExpr: "opportunities.router", prefix: "/opportunities", endpointCount: 13 },
  { id: "workflows", includeExpr: "workflows.router", prefix: "/workflows", endpointCount: 10 },
  { id: "campaigns", includeExpr: "campaigns.router", prefix: "", endpointCount: 23 },
  { id: "bug_bounty", includeExpr: "bug_bounty.router", prefix: "/api/v1/bug-bounty", endpointCount: 58 },
  { id: "platform_settings", includeExpr: "platform_settings_router.router", prefix: "/settings", endpointCount: 3 },
  { id: "scan_pool", includeExpr: "scan_pool_router.router", prefix: "/api/v1/scan-pool", endpointCount: 13 },
  { id: "visualization", includeExpr: "visualization_router.router", prefix: "/api/v1/analytics", endpointCount: 2 },
  { id: "structured_evidence", includeExpr: "structured_evidence_router.router", prefix: "/evidence/structured", endpointCount: 7 },
  { id: "attack_paths", includeExpr: "attack_paths_router.router", prefix: "/attack-paths", endpointCount: 3 },
  { id: "signal_scores", includeExpr: "signal_scores_router.router", prefix: "/signal-scores", endpointCount: 2 },
  { id: "evidence_validations", includeExpr: "evidence_validations_router.router", prefix: "/evidence/validations", endpointCount: 2 },
  { id: "approval_evidence", includeExpr: "approval_evidence_router.router", prefix: "/approval-evidence", endpointCount: 2 },
  { id: "evidence", includeExpr: "evidence.router", prefix: "/evidence", endpointCount: 3 },
  { id: "findings", includeExpr: "findings.router", prefix: "/findings", endpointCount: 40 },
  { id: "recordings", includeExpr: "recordings.router", prefix: "/recordings", endpointCount: 4 },
  { id: "reports", includeExpr: "reports.router", prefix: "/reports", endpointCount: 21 },
  { id: "export", includeExpr: "export.router", prefix: "/export", endpointCount: 1 },
  { id: "programs", includeExpr: "programs.router", prefix: "/programs", endpointCount: 24 },
  { id: "programs_discovery", includeExpr: "programs_discovery.router", prefix: "/api/v1/programs", endpointCount: 10 },
  { id: "runs", includeExpr: "runs.router", prefix: "/runs", endpointCount: 3 },
  { id: "runs_api", includeExpr: "runs_api.router", prefix: "/api/v1/runs", endpointCount: 3 },
  { id: "submissions", includeExpr: "submissions.router", prefix: "/submissions", endpointCount: 8 },
  { id: "comms", includeExpr: "comms.router", prefix: "/comms", endpointCount: 3 },
  { id: "payouts", includeExpr: "payouts.router", prefix: "/payouts", endpointCount: 3 },
  { id: "mailer", includeExpr: "mailer.router", prefix: "/mailer", endpointCount: 3 },
  { id: "logs", includeExpr: "logs.router", prefix: "/logs", endpointCount: 5 },
  { id: "logs_api", includeExpr: "logs_api.router", prefix: "/api/v1/logs", endpointCount: 5 },
  { id: "docs", includeExpr: "docs.router", prefix: "", endpointCount: 2 },
  { id: "triage", includeExpr: "triage.router", prefix: "/triage", endpointCount: 1 },
  { id: "kai_authorized_scanning", includeExpr: "kai_authorized_scanning.router", prefix: "/kai", endpointCount: 4 },
  { id: "_vector_mod", includeExpr: "_vector_mod.router", prefix: "", endpointCount: 0 },
  { id: "billing_router", includeExpr: "billing_router", prefix: "", endpointCount: 0 },
  { id: "prometheus_router", includeExpr: "prometheus_router", prefix: "", endpointCount: 0 },
  { id: "ws_router", includeExpr: "ws_router.router", prefix: "", endpointCount: 0 }
] as const;

const FULL_UI_IDS = new Set<string>(["campaigns", "bug_bounty", "terminal_chat"]);

const LINKED_UI_IDS = new Set<string>([
  "state",
  "metrics",
  "governance",
  "scope",
  "safety",
  "approvals",
  "mission_control",
  "tools",
  "events",
  "system",
  "logs",
  "logs_api",
  "opportunities",
  "workflows",
  "findings",
  "evidence",
  "reports",
  "export",
  "programs",
  "programs_discovery",
  "scan_pool",
  "structured_evidence",
  "attack_paths",
  "signal_scores",
  "evidence_validations",
  "approval_evidence",
  "agent_training",
  "autonomous",
  "orchestration",
  "orchestration_v1",
  "finding_validation",
  "validation",
  "triage",
  "artifacts",
  "recordings",
  "realtime",
  "kai_authorized_scanning"
]);

const API_ONLY_IDS = new Set<string>([
  "auth_routes",
  "auth",
  "key_management",
  "keys",
  "hil_approval",
  "hil_findings",
  "hil_workflow",
  "hil_scopes",
  "hil_providers",
  "hil_embeddings",
  "artifact_signing",
  "dorks",
  "knowledge",
  "graph",
  "persona_garden",
  "tasks",
  "orchestrator",
  "planner",
  "chains",
  "embeddings",
  "intel",
  "mcp",
  "simulation",
  "vault",
  "credentials",
  "model_bidding",
  "platform_settings",
  "runs",
  "runs_api",
  "submissions",
  "comms",
  "payouts",
  "mailer",
  "docs"
]);

const OPTIONAL_IDS = new Set<string>(["_vector_mod", "billing_router", "prometheus_router", "ws_router"]);

const FRONTEND_SURFACES: Record<string, string> = {
  campaigns: "/missions, /mission-control",
  bug_bounty: "/overview + extended surfaces",
  terminal_chat: "/terminal",
  approvals: "/approvals",
  opportunities: "/opportunities",
  workflows: "/mission-control",
  findings: "/findings",
  evidence: "/evidence",
  reports: "/reports",
  export: "/exports",
  programs: "/programs",
  mission_control: "/mission-control",
  logs: "/system",
  logs_api: "/system",
  tools: "/system",
  safety: "/overview + approvals",
  scope: "/overview + mission-control",
  scan_pool: "/overview (linked via mission pressure)",
  attack_paths: "/overview hotspots + evidence",
  signal_scores: "/predictions + opportunities",
  evidence_validations: "/evidence + findings readiness",
  approval_evidence: "/approvals + evidence",
  agent_training: "/agents",
  autonomous: "/mission-control autonomous lane",
  orchestration: "/mission-control + timeline",
  orchestration_v1: "/mission-control + timeline",
  finding_validation: "/findings review actions",
  validation: "/findings + evidence quality",
  triage: "/triage alias in findings center",
  kai_authorized_scanning: "/terminal + mission-control safety cues",
  state: "/system",
  metrics: "/analytics + system",
  governance: "/approvals + reports"
};

const STATUS_NOTE: Record<BackendCoverageStatus, string> = {
  FULL_UI: "Direct frontend API calls and dedicated cockpit surfaces are active.",
  LINKED_UI: "Capability is represented in cockpit UX via aggregated or adjacent workflows.",
  API_ONLY: "Capability exists in backend/middleware but currently has no dedicated operator GUI flow.",
  OPTIONAL: "Optional backend module; availability depends on deployment and startup checks.",
  UNMAPPED: "No frontend representation metadata found. This is a true coverage gap."
};

function resolveStatus(id: string): BackendCoverageStatus {
  if (FULL_UI_IDS.has(id)) {
    return "FULL_UI";
  }
  if (LINKED_UI_IDS.has(id)) {
    return "LINKED_UI";
  }
  if (API_ONLY_IDS.has(id)) {
    return "API_ONLY";
  }
  if (OPTIONAL_IDS.has(id)) {
    return "OPTIONAL";
  }
  return "UNMAPPED";
}

export const BACKEND_CAPABILITY_LEDGER: BackendRouterCapability[] = BACKEND_ROUTER_INDEX.map((entry) => {
  const status = resolveStatus(entry.id);
  return {
    ...entry,
    status,
    frontendSurface: FRONTEND_SURFACES[entry.id] ?? "No dedicated surface",
    note: STATUS_NOTE[status]
  };
});

export const BACKEND_MIDDLEWARE_LEDGER: BackendMiddlewareCapability[] = [
  {
    id: "security_headers",
    layer: "SecurityHeadersMiddleware",
    frontendSurface: "Global (all pages)",
    note: "Backend enforces strict security headers; UI assumes CSP/safe framing from server."
  },
  {
    id: "correlation_id",
    layer: "CorrelationIdMiddleware",
    frontendSurface: "/system + audit trails",
    note: "Request correlation IDs support reproducible incident traces in mission/system workflows."
  },
  {
    id: "csrf",
    layer: "CSRFProtectionMiddleware",
    frontendSurface: "Mutating actions across cockpit",
    note: "All mutation paths in frontend operate under CSRF-protected session contract."
  },
  {
    id: "rate_limit",
    layer: "RateLimitMiddleware",
    frontendSurface: "Operator and terminal actions",
    note: "Action pacing is backend-governed; frontend should treat spikes as controlled safety behavior."
  },
  {
    id: "cors",
    layer: "CORSMiddleware",
    frontendSurface: "Browser connectivity",
    note: "Cross-origin policy is backend-managed and required for frontend runtime reachability."
  },
  {
    id: "startup_dependency_validation",
    layer: "Startup dependency checks",
    frontendSurface: "/health and /readyz",
    note: "Frontend diagnostics surfaces expose degraded readiness when startup contracts fail."
  },
  {
    id: "startup_secrets_toolpacks_validation",
    layer: "Startup secret + toolpack checks",
    frontendSurface: "/system + mission execution",
    note: "Tool/secret readiness drives autonomous scheduling fidelity and should be monitored by operators."
  }
];

export const BACKEND_COVERAGE_SUMMARY = {
  totalRouters: BACKEND_CAPABILITY_LEDGER.length,
  fullUi: BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === "FULL_UI").length,
  linkedUi: BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === "LINKED_UI").length,
  apiOnly: BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === "API_ONLY").length,
  optional: BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === "OPTIONAL").length,
  unmapped: BACKEND_CAPABILITY_LEDGER.filter((row) => row.status === "UNMAPPED").length,
  middleware: BACKEND_MIDDLEWARE_LEDGER.length
};
