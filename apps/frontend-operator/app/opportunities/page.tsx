"use client";

import { useMemo, useState } from "react";

import { useOpportunityRankings } from "@/hooks/useOpportunityRankings";

import { ProgramFilterCard } from "@/components/bugbounty/ProgramFilterCard";
import { OpportunityRankingTable } from "@/components/bugbounty/OpportunityRankingTable";
import { EmptyState } from "@/components/data-display/EmptyState";
import { ErrorState } from "@/components/data-display/ErrorState";
import { LoadingState } from "@/components/data-display/LoadingState";
import { PageHeader } from "@/components/layout/PageHeader";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";

export default function OpportunitiesPage() {
  const [programIdFilter, setProgramIdFilter] = useState("");
  const [subjectTypeFilter, setSubjectTypeFilter] = useState("ALL");
  const [searchText, setSearchText] = useState("");
  const data = useOpportunityRankings(programIdFilter.trim() || undefined);
  const filteredRows = useMemo(() => {
    const term = searchText.trim().toLowerCase();
    return data.rows.filter((row) => {
      if (subjectTypeFilter !== "ALL" && (row.subjectType ?? "UNKNOWN") !== subjectTypeFilter) {
        return false;
      }
      if (!term) {
        return true;
      }
      const haystack = [
        row.subjectType,
        row.subjectKey,
        row.programId,
        row.scopeTargetId,
        row.recommendedWorkflow,
        row.recommendedAction
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return haystack.includes(term);
    });
  }, [data.rows, searchText, subjectTypeFilter]);

  return (
    <div className="operator-grid">
      <PageHeader
        title="Opportunity Rankings"
        description="Phase 7 opportunity scoring with explainable reasoning and next workflow recommendations."
      />

      <ProgramFilterCard value={programIdFilter} onChange={setProgramIdFilter} />

      <Card>
        <CardHeader>
          <CardTitle>Ranked Opportunities</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-2 md:grid-cols-2">
            <Select value={subjectTypeFilter} onChange={(event) => setSubjectTypeFilter(event.target.value)}>
              <option value="ALL">All subject types</option>
              <option value="PROGRAM">PROGRAM</option>
              <option value="TARGET">TARGET</option>
              <option value="CANDIDATE">CANDIDATE</option>
            </Select>
            <Input
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder="search subject, ids, workflow, actions"
            />
          </div>
          <div className="text-xs text-muted">results: {filteredRows.length}</div>
          {data.rankingsQuery.isLoading ? <LoadingState label="Loading opportunity rankings..." /> : null}
          {data.rankingsQuery.isError ? (
            <ErrorState error={data.rankingsQuery.error} title="Opportunity rankings failed" />
          ) : null}
          {data.recommendationsQuery.isError ? (
            <ErrorState error={data.recommendationsQuery.error} title="Recommendations source failed" />
          ) : null}
          {data.predictionsQuery.isError ? (
            <ErrorState error={data.predictionsQuery.error} title="Predictions source failed" />
          ) : null}
          {filteredRows.length > 0 ? (
            <OpportunityRankingTable rows={filteredRows} />
          ) : !data.rankingsQuery.isLoading ? (
            <EmptyState
              title="No opportunities match filters"
              description="No opportunity rankings match the selected subject type and search filters."
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
