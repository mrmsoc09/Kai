from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .exploit_graph import (
    ExploitEdgeType,
    build_exploit_chains,
    build_exploit_graph,
)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _severity_score(value: str | None) -> float:
    raw = str(value or "").strip().lower()
    mapping = {
        "critical": 1.0,
        "high": 0.85,
        "medium": 0.65,
        "low": 0.35,
        "info": 0.2,
        "informational": 0.2,
    }
    return mapping.get(raw, 0.5)


class AttackGraphSummary(BaseModel):
    node_count: int
    edge_count: int
    dependency_count: int
    validated_chain_count: int
    top_chain_score: float = Field(ge=0.0, le=1.0)
    impact_score: float = Field(ge=0.0, le=1.0)
    prioritization_score: float = Field(ge=0.0, le=1.0)


class AttackGraphResult(BaseModel):
    graph_id: str
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    dependencies: list[dict[str, Any]]
    chains: list[dict[str, Any]]
    summary: AttackGraphSummary
    explanation: str

    def persistence_record(self, *, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "graph_id": self.graph_id,
            "summary": self.summary.model_dump(),
            "explanation": self.explanation,
            "nodes": self.nodes,
            "edges": self.edges,
            "dependencies": self.dependencies,
            "chains": self.chains,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }


class AttackGraphService:
    """
    Builds chain-aware attack graph and dependency views from findings.
    Non-destructive: additive output only.
    """

    def build_attack_graph(
        self,
        *,
        run_id: str,
        findings: list[dict[str, Any]],
    ) -> AttackGraphResult:
        safe_findings = [row for row in findings if isinstance(row, dict)]
        artifacts = self._artifact_rows_from_findings(safe_findings)
        graph = build_exploit_graph(safe_findings, memory=[], artifacts=artifacts)
        chains = build_exploit_chains(safe_findings, memory=[], artifacts=artifacts, max_depth=6, max_chains=30)
        dependencies = self._dependency_rows(graph)
        chain_rows = [self._chain_row(row.to_dict()) for row in chains]

        top_chain_score = max((row["score"] for row in chain_rows), default=0.0)
        validated_chain_count = sum(1 for row in chain_rows if row["validated_chain"])
        impact_score = self._impact_score(safe_findings, chain_rows)
        prioritization = self._prioritization_score(safe_findings, chain_rows, dependencies)
        summary = AttackGraphSummary(
            node_count=len(graph.nodes),
            edge_count=len(graph.edges),
            dependency_count=len(dependencies),
            validated_chain_count=validated_chain_count,
            top_chain_score=round(_clamp01(top_chain_score), 4),
            impact_score=round(_clamp01(impact_score), 4),
            prioritization_score=round(_clamp01(prioritization), 4),
        )
        explanation = (
            f"attack_graph nodes={summary.node_count} edges={summary.edge_count} "
            f"dependencies={summary.dependency_count} validated_chains={summary.validated_chain_count}"
        )
        graph_id = f"attack-graph:{run_id}:{summary.node_count}:{summary.edge_count}"
        return AttackGraphResult(
            graph_id=graph_id,
            nodes=[node.to_dict() for node in graph.nodes.values()],
            edges=[edge.to_dict() for edge in graph.edges.values()],
            dependencies=dependencies,
            chains=chain_rows,
            summary=summary,
            explanation=explanation,
        )

    def enrich_findings_with_graph_context(
        self,
        *,
        run_id: str,
        findings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], AttackGraphResult]:
        result = self.build_attack_graph(run_id=run_id, findings=findings)
        chain_priority_by_finding: dict[str, float] = {}
        for chain in result.chains:
            chain_priority = float(chain.get("chain_priority") or 0.0)
            nodes = chain.get("nodes") if isinstance(chain.get("nodes"), list) else []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                if str(node.get("node_type") or "") != "finding_id":
                    continue
                raw_value = str(node.get("value") or "").strip()
                if not raw_value:
                    continue
                chain_priority_by_finding[raw_value] = max(
                    chain_priority,
                    chain_priority_by_finding.get(raw_value, 0.0),
                )

        enriched: list[dict[str, Any]] = []
        for idx, raw in enumerate(findings, start=1):
            row = dict(raw)
            finding_id = str(row.get("finding_id") or row.get("id") or "").strip()
            fallback_key = str(row.get("title") or f"finding-{idx}")
            chain_priority = chain_priority_by_finding.get(finding_id, 0.0)
            if chain_priority <= 0.0:
                chain_priority = chain_priority_by_finding.get(fallback_key, 0.0)
            row["graph_chain_priority"] = round(_clamp01(chain_priority), 4)
            row["graph_impact_score"] = result.summary.impact_score
            row["graph_prioritization_score"] = result.summary.prioritization_score
            row["graph_validated_chain_count"] = result.summary.validated_chain_count
            base_conf = float(row.get("final_confidence") or row.get("confidence_score") or row.get("confidence") or 0.0)
            row["graph_adjusted_priority"] = round(
                _clamp01((0.55 * base_conf) + (0.45 * row["graph_chain_priority"])),
                4,
            )
            enriched.append(row)
        return enriched, result

    @staticmethod
    def _artifact_rows_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for idx, finding in enumerate(findings, start=1):
            target = str(finding.get("target") or finding.get("host") or "")
            finding_id = str(finding.get("finding_id") or finding.get("id") or f"finding-{idx}")
            recording = str(finding.get("recording_path") or "").strip()
            if recording:
                rows.append(
                    {
                        "artifact_id": f"recording:{idx}",
                        "finding_id": finding_id,
                        "target": target,
                        "path": recording,
                    }
                )
            screenshots = finding.get("screenshots")
            if isinstance(screenshots, list):
                for s_idx, shot in enumerate(screenshots, start=1):
                    shot_path = str(shot).strip()
                    if not shot_path:
                        continue
                    rows.append(
                        {
                            "artifact_id": f"screenshot:{idx}:{s_idx}",
                            "finding_id": finding_id,
                            "target": target,
                            "path": shot_path,
                        }
                    )
        return rows

    @staticmethod
    def _dependency_rows(graph) -> list[dict[str, Any]]:  # noqa: ANN001
        rows: list[dict[str, Any]] = []
        for edge in graph.edges.values():
            if edge.edge_type not in {ExploitEdgeType.REQUIRES, ExploitEdgeType.LEADS_TO, ExploitEdgeType.BYPASSES}:
                continue
            rows.append(
                {
                    "dependency_id": edge.edge_id,
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "dependency_type": edge.edge_type.value,
                    "weight": round(edge.weight, 4),
                    "reason": edge.reason,
                }
            )
        return rows

    @staticmethod
    def _chain_row(chain: dict[str, Any]) -> dict[str, Any]:
        nodes = chain.get("nodes") if isinstance(chain.get("nodes"), list) else []
        validated = any(bool(node.get("validated")) for node in nodes if isinstance(node, dict))
        return {
            **chain,
            "validated_chain": validated,
            "chain_priority": round(
                _clamp01(
                    (0.45 * float(chain.get("score") or 0.0))
                    + (0.35 * float(chain.get("confidence_score") or 0.0))
                    + (0.20 * (1.0 if validated else 0.0))
                ),
                4,
            ),
        }

    @staticmethod
    def _impact_score(findings: list[dict[str, Any]], chains: list[dict[str, Any]]) -> float:
        if not findings:
            return 0.0
        severity = sum(_severity_score(str(row.get("severity_hint") or row.get("severity"))) for row in findings) / len(findings)
        chain_strength = max((float(row.get("score") or 0.0) for row in chains), default=0.0)
        confirmation = sum(
            1.0 for row in findings if str(row.get("final_verdict") or "").lower() == "confirmed"
        ) / max(1, len(findings))
        return _clamp01((0.45 * severity) + (0.35 * chain_strength) + (0.20 * confirmation))

    @staticmethod
    def _prioritization_score(
        findings: list[dict[str, Any]],
        chains: list[dict[str, Any]],
        dependencies: list[dict[str, Any]],
    ) -> float:
        if not findings:
            return 0.0
        confidence = sum(float(row.get("final_confidence") or row.get("confidence_score") or 0.0) for row in findings) / len(findings)
        chain_priority = max((float(row.get("chain_priority") or 0.0) for row in chains), default=0.0)
        dependency_pressure = min(1.0, len(dependencies) / max(1.0, len(findings) * 2.0))
        return _clamp01((0.50 * confidence) + (0.35 * chain_priority) + (0.15 * dependency_pressure))
