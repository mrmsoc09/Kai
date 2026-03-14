"use client";

import { useMemo, useState } from "react";

import { useAgentFramework } from "@/hooks/useAgentFramework";

import { AgentEvaluationTable } from "@/components/bugbounty/AgentEvaluationTable";
import { AgentExecutionTable } from "@/components/bugbounty/AgentExecutionTable";
import { AgentRegistryTable } from "@/components/bugbounty/AgentRegistryTable";
import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { ScoreBadge } from "@/components/status/ScoreBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default function AgentsPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [targetIdentifier, setTargetIdentifier] = useState("example.org");

  const trimmedProgramId = programIdFilter.trim();
  const programId =
    trimmedProgramId.length === 0 || UUID_PATTERN.test(trimmedProgramId)
      ? trimmedProgramId || undefined
      : undefined;

  const data = useAgentFramework(programId);

  const sortedAgents = useMemo(
    () => [...(data.agentsQuery.data ?? [])].sort((a, b) => a.agent_name.localeCompare(b.agent_name)),
    [data.agentsQuery.data]
  );
  const selected = sortedAgents.find((item) => item.agent_id === selectedAgentId);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Specialized Agents"
        description="Phase 10.5 agent registry, execution telemetry, confidence/escalation behavior, and benchmark quality summaries."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />
      {trimmedProgramId && !programId ? (
        <p className="text-xs text-danger">Program filter must be a valid UUID.</p>
      ) : null}

      <div className="grid gap-3 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Registered Agents</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{data.summary.agents}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Executions (Recent)</CardTitle>
          </CardHeader>
          <CardContent className="text-2xl font-semibold">{data.summary.executions}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted">Evaluation Success</CardTitle>
          </CardHeader>
          <CardContent>
            <ScoreBadge value={data.summary.averageSuccessRate} label="success rate" />
            <p className="mt-2 text-xs text-muted">passing evaluations: {data.summary.passingEvaluations}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Agent Control</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1fr_1fr_auto_auto]">
          <Select value={selectedAgentId} onChange={(event) => setSelectedAgentId(event.target.value)}>
            <option value="">Select an agent...</option>
            {sortedAgents.map((agent) => (
              <option key={agent.id} value={agent.agent_id}>
                {agent.agent_name}
              </option>
            ))}
          </Select>
          <Input
            value={targetIdentifier}
            onChange={(event) => setTargetIdentifier(event.target.value)}
            placeholder="target identifier (for scope parsing)"
          />
          <Button onClick={() => data.syncMutation.mutate()} disabled={data.syncMutation.isPending}>
            Sync Registry
          </Button>
          <div className="flex gap-2">
            <Button
              onClick={() =>
                selected &&
                data.runMutation.mutate({
                  agentId: selected.agent_id,
                  inputPayload: { target_identifier: targetIdentifier }
                })
              }
              disabled={!selected || data.runMutation.isPending}
            >
              Run Agent
            </Button>
            <Button
              onClick={() => selected && data.evaluateMutation.mutate({ agentId: selected.agent_id })}
              disabled={!selected || data.evaluateMutation.isPending}
              variant="outline"
            >
              Evaluate
            </Button>
          </div>
        </CardContent>
      </Card>

      {data.agentsQuery.isLoading ? <LoadingState label="Loading agent registry..." /> : null}
      {data.executionsQuery.isLoading ? <LoadingState label="Loading agent executions..." /> : null}
      {data.evaluationsQuery.isLoading ? <LoadingState label="Loading agent evaluations..." /> : null}
      {data.agentsQuery.isError ? <ErrorState error={data.agentsQuery.error} title="Agent registry failed" /> : null}
      {data.executionsQuery.isError ? (
        <ErrorState error={data.executionsQuery.error} title="Agent execution telemetry failed" />
      ) : null}
      {data.evaluationsQuery.isError ? (
        <ErrorState error={data.evaluationsQuery.error} title="Agent evaluation telemetry failed" />
      ) : null}
      {data.runMutation.isError ? <ErrorState error={data.runMutation.error} title="Agent run failed" /> : null}
      {data.evaluateMutation.isError ? (
        <ErrorState error={data.evaluateMutation.error} title="Agent evaluation failed" />
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Registry</CardTitle>
        </CardHeader>
        <CardContent>
          <AgentRegistryTable rows={sortedAgents} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Execution History</CardTitle>
        </CardHeader>
        <CardContent>
          <AgentExecutionTable rows={data.executionsQuery.data ?? []} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Evaluation History</CardTitle>
        </CardHeader>
        <CardContent>
          <AgentEvaluationTable rows={data.evaluationsQuery.data ?? []} />
          {(data.evaluationsQuery.data?.length ?? 0) === 0 ? (
            <div className="mt-3">
              <EmptyState
                title="No evaluation baseline"
                description="Run evaluations to establish confidence and routing regression baselines."
              />
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
