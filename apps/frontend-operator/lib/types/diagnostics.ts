export type DiagnosticsBucket = {
  total: number;
  by_status: Record<string, number>;
};

export type DiagnosticsSummaryResponse = {
  generated_at: string;
  campaigns: DiagnosticsBucket;
  branches: DiagnosticsBucket;
  phase_jobs: DiagnosticsBucket;
  approval_gates: DiagnosticsBucket;
  tool_executions: DiagnosticsBucket;
  findings: DiagnosticsBucket;
  submission_drafts: DiagnosticsBucket;
};
