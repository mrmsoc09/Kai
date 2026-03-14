import type { SchedulerStatus, ToolHealthDashboard } from "@/lib/types";

import { DataTable } from "@/components/data-display/DataTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { StatusBadge } from "@/components/status/StatusBadge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Td, Th } from "@/components/ui/table";

export function OperationsHealthPanel({
  schedulerStatus,
  toolsHealth
}: {
  schedulerStatus?: SchedulerStatus;
  toolsHealth?: ToolHealthDashboard;
}) {
  const toolRows = Array.isArray(toolsHealth?.tools) ? toolsHealth.tools : [];
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Total Schedules</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{schedulerStatus?.total_schedules ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Due Schedules</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{schedulerStatus?.due_schedules ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Blocked Readiness (24h)</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{schedulerStatus?.blocked_readiness_last_24h ?? 0}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Healthy Tools</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">
            {toolsHealth?.summary?.healthy_tools ?? 0}/{toolsHealth?.summary?.total_tools ?? 0}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Tool Health</CardTitle>
        </CardHeader>
        <CardContent>
          {toolsHealth && toolRows.length > 0 ? (
            <DataTable>
              <thead>
                <tr>
                  <Th>Tool</Th>
                  <Th>Category</Th>
                  <Th>Install</Th>
                  <Th>Credentials</Th>
                  <Th>Smoke Test</Th>
                  <Th>Last Execution</Th>
                  <Th>Last Failure</Th>
                </tr>
              </thead>
              <tbody>
                {toolRows.map((tool) => (
                  <tr key={tool.tool_name}>
                    <Td>{tool.tool_name ?? "unknown-tool"}</Td>
                    <Td>{tool.category ?? "uncategorized"}</Td>
                    <Td>
                      <StatusBadge status={tool.install_verification_status ?? "UNKNOWN"} />
                    </Td>
                    <Td>
                      <StatusBadge status={tool.credential_status ?? "UNKNOWN"} />
                    </Td>
                    <Td>
                      <StatusBadge status={tool.wrapper_smoke_test_status ?? "UNKNOWN"} />
                    </Td>
                    <Td>
                      <StatusBadge status={tool.last_execution_status ?? "UNKNOWN"} />
                    </Td>
                    <Td className="max-w-[320px] text-xs text-muted">{tool.last_failure_reason ?? "n/a"}</Td>
                  </tr>
                ))}
              </tbody>
            </DataTable>
          ) : (
            <EmptyState
              title="No tool health data"
              description="Tool health dashboard is unavailable or returned no records."
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
