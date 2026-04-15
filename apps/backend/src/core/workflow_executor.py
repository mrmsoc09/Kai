from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .bugbounty_workflow_engine import STAGES, build_phase_specs_for_template
from .recon_correlation import correlate_observations
from .cve_playbook_selector import CVEPlaybookSelector
from .global_task_queue import GlobalTaskQueue
from .praison_execution_events import MissionEvent, get_event_bus
from .scope_guardrails import (
    ScopePolicy,
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)
from .tool_registry_catalog import get_catalog_entry
from .tools import get_registry, initialize_default_tools
from .tool_adapters.base_adapter import execute_registered_tool
from .workflow_run_service import WorkflowRunService
from .workflow_data_store import WorkflowDataStore
from .workflow_normalizer import correlation_records_from_graph, normalize_tool_output
from ..models.campaign import CampaignRun, ExecutionBranch, Program, ScopeTarget
from ..models.enums import (
    BranchStatusEnum,
    CampaignStatusEnum,
    StageRunStatusEnum,
    ToolExecutionStatusEnum,
    WorkflowRunStatusEnum,
)
from ..schemas.bugbounty import (
    AnalystExport,
    ScopeRule,
    StageRun,
    Target,
    ToolExecution,
    WorkflowRun,
)

logger = logging.getLogger(__name__)


@dataclass
class WorkflowExecutionResult:
    run_id: str
    workflow_template: str
    status: str
    target: str
    manifest_path: str
    summary_path: str
    report_path: str
    stage_results: list[dict[str, Any]]
    prioritized_findings: list[dict[str, Any]]
    metrics: dict[str, Any]
    campaign_id: str | None = None
    workflow_run_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "workflow_template": self.workflow_template,
            "status": self.status,
            "target": self.target,
            "manifest_path": self.manifest_path,
            "summary_path": self.summary_path,
            "report_path": self.report_path,
            "stage_results": self.stage_results,
            "prioritized_findings": self.prioritized_findings,
            "metrics": self.metrics,
            "campaign_id": self.campaign_id,
            "workflow_run_id": self.workflow_run_id,
        }


class WorkflowExecutor:
    def __init__(
        self,
        *,
        output_root: str | None = None,
        db: AsyncSession | None = None,
        trigger_source: str = "CLI",
        actor: str = "workflow.executor",
    ):
        self.output_root = Path(output_root).expanduser().resolve() if output_root else None
        self._seen: dict[str, set[str]] = defaultdict(set)
        self.db = db
        self.trigger_source = trigger_source
        self.actor = actor
        self._task_queue = GlobalTaskQueue(
            max_memory_gb=float(os.getenv("K1_GLOBAL_MEMORY_CAP_GB", "40"))
        )
        self._playbook_selector: CVEPlaybookSelector | None = None
        try:
            self._playbook_selector = CVEPlaybookSelector()
        except Exception as exc:
            logger.warning("CVE/playbook selector unavailable: %s", exc)

    def _store(self, run_id: str) -> WorkflowDataStore:
        root = self.output_root or Path(os.getenv("K1_WORKFLOW_OUTPUT_ROOT", "output")).resolve()
        return WorkflowDataStore(run_id=run_id, root=root)

    def _append_unique(self, store: WorkflowDataStore, model_key: str, payload: dict[str, Any]) -> None:
        fingerprint = json.dumps(payload, sort_keys=True, default=str)
        if fingerprint in self._seen[model_key]:
            return
        self._seen[model_key].add(fingerprint)
        store.append_model(model_key, payload)

    @staticmethod
    def _allowed_tool_params(tool, params: dict[str, Any]) -> dict[str, Any]:
        allowed_names = {param.name for param in getattr(tool, "parameters", [])}
        if not allowed_names:
            return dict(params)
        filtered = {key: value for key, value in params.items() if key in allowed_names}
        canonical_target = params.get("target")
        if "target" in allowed_names and "target" not in filtered and canonical_target:
            filtered["target"] = canonical_target
        if "run_id" in allowed_names and "run_id" not in filtered and params.get("run_id"):
            filtered["run_id"] = params["run_id"]

        # Compatibility bridge for legacy wrappers that predate canonical target naming.
        if canonical_target:
            alias_fields = (
                "domain",
                "host",
                "url",
                "ip",
                "cidr",
                "query",
                "path",
                "repo_path",
                "input",
            )
            for alias in alias_fields:
                if alias in allowed_names and alias not in filtered:
                    filtered[alias] = canonical_target
            if "targets" in allowed_names and "targets" not in filtered:
                filtered["targets"] = [canonical_target]
        return filtered

    async def _execute_tool(self, tool, params: dict[str, Any]):
        # Local workflow executor favors determinism over throughput.
        # Tool wrappers are synchronous; execute directly to avoid threadpool deadlocks in constrained envs.
        return execute_registered_tool(tool, params)

    def _load_manifest(self, store: WorkflowDataStore) -> dict[str, Any] | None:
        path = store.workflow_dir / "manifest.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_manifest(self, store: WorkflowDataStore, manifest: dict[str, Any]) -> str:
        return store.write_workflow_json("manifest.json", manifest)

    def _markdown_report(
        self,
        *,
        run_id: str,
        workflow_template: str,
        target: str,
        stage_results: list[dict[str, Any]],
        prioritized_findings: list[dict[str, Any]],
    ) -> str:
        lines = [
            f"# Kai Workflow Report",
            "",
            f"- Run ID: `{run_id}`",
            f"- Workflow: `{workflow_template}`",
            f"- Target: `{target}`",
            "",
            "## Stage Summary",
            "",
        ]
        for stage in stage_results:
            lines.append(
                f"- `{stage['stage']}`: status={stage['status']} "
                f"tools={stage['tool_count']} success={stage['success_count']} failed={stage['failed_count']}"
            )
        lines.extend(["", "## Prioritized Findings", ""])
        if not prioritized_findings:
            lines.append("- No prioritized findings were generated.")
        else:
            for finding in prioritized_findings[:25]:
                lines.append(
                    f"- `{finding.get('host')}` score={finding.get('priority_score')} "
                    f"severity={finding.get('severity_hint')} reason={finding.get('reason')}"
                )
        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _stage_name_for_phase(phase: Any) -> str:
        if isinstance(getattr(phase, "input_payload_json", None), dict):
            payload = phase.input_payload_json
            return (
                str(payload.get("workflow_stage") or payload.get("stage") or "")
                or str(phase.phase_name).split("__", 1)[0]
            )
        return str(phase.phase_name).split("__", 1)[0]

    @staticmethod
    def _summary_text(value: Any, *, max_len: int = 4000) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, default=str)
        return text[:max_len]

    def _select_playbooks_from_signals(
        self,
        *,
        aggregate_signal_records: list[dict[str, Any]],
        prioritized_findings: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._playbook_selector is None:
            return {}
        try:
            return self._playbook_selector.select_for_signals(
                signals=aggregate_signal_records,
                prioritized_findings=prioritized_findings,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Playbook selection failed: %s", exc)
            return {}

    @staticmethod
    def _emit_active_playbook_events(
        *,
        run_id: str,
        workflow_template: str,
        program_id: UUID | None,
        selection: dict[str, Any],
    ) -> None:
        recommendations = selection.get("playbook_recommendations")
        if not isinstance(recommendations, list) or not recommendations:
            return
        bus = get_event_bus()
        program_ref = str(program_id) if program_id is not None else ""
        for rec in recommendations[:5]:
            if not isinstance(rec, dict):
                continue
            bus.emit(
                MissionEvent(
                    event_type="active_playbook_logic",
                    mission_id=run_id,
                    workflow_id=workflow_template,
                    program_id=program_ref,
                    phase="playbook_selection",
                    detail={
                        "playbook_id": rec.get("playbook_id"),
                        "playbook_name": rec.get("playbook_name"),
                        "path": rec.get("path"),
                        "score": rec.get("score"),
                        "supporting_cves": rec.get("supporting_cves", []),
                    },
                )
            )

    async def _ensure_local_campaign_context(
        self,
        *,
        run_id: str,
        workflow_template: str,
        target: str,
        safe_mode: bool,
        program_id: UUID | None = None,
        scope_target_id: UUID | None = None,
        campaign_name: str | None = None,
        initiated_by: str | None = None,
    ) -> tuple[CampaignRun, ScopeTarget, ExecutionBranch]:
        assert self.db is not None

        if program_id is not None:
            result = await self.db.execute(select(Program).where(Program.id == program_id))
            program = result.scalar_one_or_none()
            if program is None:
                raise ValueError(f"Program not found for workflow execution: {program_id}")
        else:
            program_key = "kai-local-workflows"
            result = await self.db.execute(select(Program).where(Program.program_key == program_key))
            program = result.scalar_one_or_none()
            if program is None:
                program = Program(
                    program_key=program_key,
                    name="Kai Local Workflows",
                    platform="LOCAL",
                    status="ACTIVE",
                    created_by=self.actor,
                    config_json={"owner": "workflow_executor"},
                )
                self.db.add(program)
                await self.db.flush()

        scope_target: ScopeTarget | None
        if scope_target_id is not None:
            result = await self.db.execute(
                select(ScopeTarget).where(
                    ScopeTarget.id == scope_target_id,
                    ScopeTarget.program_id == program.id,
                )
            )
            scope_target = result.scalar_one_or_none()
            if scope_target is None:
                raise ValueError(
                    "Scope target does not exist or does not belong to supplied program"
                )
        else:
            result = await self.db.execute(
                select(ScopeTarget).where(
                    ScopeTarget.program_id == program.id,
                    ScopeTarget.target == target,
                    ScopeTarget.target_type == "domain",
                )
            )
            scope_target = result.scalar_one_or_none()
            if scope_target is None:
                scope_target = ScopeTarget(
                    program_id=program.id,
                    target=target,
                    target_type="domain",
                    is_in_scope=True,
                    details_json={"source": "workflow_executor"},
                )
                self.db.add(scope_target)
                await self.db.flush()

        resolved_campaign_name = campaign_name or f"{workflow_template}:{run_id}"
        resolved_initiated_by = initiated_by or self.actor
        result = await self.db.execute(
            select(CampaignRun).where(CampaignRun.campaign_name == resolved_campaign_name)
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            campaign = CampaignRun(
                program_id=program.id,
                primary_scope_target_id=scope_target.id,
                campaign_name=resolved_campaign_name,
                initiated_by=resolved_initiated_by,
                declared_goal=f"Execute workflow {workflow_template} on target {target}",
                declared_reason="Local workflow execution",
                policy_basis="LOCAL_EXECUTOR",
                approval_required=False,
                status=CampaignStatusEnum.RUNNING,
                run_config_json={
                    "workflow_template": workflow_template,
                    "safe_mode": safe_mode,
                    "trigger_source": self.trigger_source,
                },
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(campaign)
            await self.db.flush()

        branch_key = f"wf-{run_id}"
        result = await self.db.execute(
            select(ExecutionBranch).where(
                ExecutionBranch.campaign_id == campaign.id,
                ExecutionBranch.branch_key == branch_key,
            )
        )
        branch = result.scalar_one_or_none()
        if branch is None:
            branch = ExecutionBranch(
                campaign_id=campaign.id,
                branch_key=branch_key,
                branch_name="workflow_executor",
                status=BranchStatusEnum.RUNNING,
                declared_goal=f"Workflow branch for {workflow_template}",
                approval_required=False,
                branch_config_json={"workflow_run_id": run_id},
                started_at=datetime.now(timezone.utc),
            )
            self.db.add(branch)
            await self.db.flush()
        return campaign, scope_target, branch

    async def execute_template(
        self,
        *,
        workflow_template: str,
        target: str,
        run_id: str | None = None,
        safe_mode: bool = True,
        dry_run: bool = False,
        concurrency_limit: int = 4,
        enable_steps: list[str] | None = None,
        disable_steps: list[str] | None = None,
        scope_policy_path: str | None = None,
        scope_policy_override: ScopePolicy | None = None,
        resume: bool = False,
        program_id: UUID | None = None,
        scope_target_id: UUID | None = None,
        campaign_name: str | None = None,
        initiated_by: str | None = None,
    ) -> WorkflowExecutionResult:
        run_id = run_id or f"wf-{uuid4()}"
        store = self._store(run_id)
        policy: ScopePolicy = scope_policy_override or load_scope_policy(scope_policy_path)
        decision = evaluate_target_scope(target, policy, safe_mode=safe_mode)
        audit_scope_decision(decision)
        if not decision.allowed:
            raise ValueError(f"Target '{target}' rejected by scope policy ({decision.reason})")

        phase_specs, workflow_metadata = build_phase_specs_for_template(
            template_name=workflow_template,
            target=target,
            safe_mode=safe_mode,
            scope_policy=policy,
            enable_steps=enable_steps or [],
            disable_steps=disable_steps or [],
            dry_run=dry_run,
        )
        stage_to_phases: dict[str, list[Any]] = defaultdict(list)
        for phase in phase_specs:
            stage_to_phases[self._stage_name_for_phase(phase)].append(phase)
        for phases in stage_to_phases.values():
            phases.sort(key=lambda item: item.phase_order)

        target_model = Target(target_id=f"target-{run_id}", value=target, target_type="domain")
        self._append_unique(store, "targets", target_model.model_dump())
        for idx, rule in enumerate(policy.allowlist):
            self._append_unique(
                store,
                "scope_rules",
                ScopeRule(rule_id=f"{run_id}-allow-{idx}", rule_type="allow", pattern=rule).model_dump(),
            )
        for idx, rule in enumerate(policy.denylist):
            self._append_unique(
                store,
                "scope_rules",
                ScopeRule(rule_id=f"{run_id}-deny-{idx}", rule_type="deny", pattern=rule).model_dump(),
            )
        for idx, rule in enumerate(policy.cidr_allowlist):
            self._append_unique(
                store,
                "scope_rules",
                ScopeRule(
                    rule_id=f"{run_id}-cidr-{idx}",
                    rule_type="cidr_allow",
                    pattern=rule,
                ).model_dump(),
            )

        workflow_run_payload = WorkflowRun(
            run_id=run_id,
            workflow_name=workflow_template,
            target=target,
            status="DRY_RUN" if dry_run else "RUNNING",
            safe_mode=safe_mode,
            dry_run=dry_run,
            metadata=workflow_metadata,
        )
        self._append_unique(store, "workflow_runs", workflow_run_payload.model_dump())

        workflow_svc: WorkflowRunService | None = None
        db_campaign: CampaignRun | None = None
        db_scope_target: ScopeTarget | None = None
        db_branch: ExecutionBranch | None = None
        db_workflow_run = None
        db_stage_runs: dict[str, Any] = {}
        if self.db is not None:
            workflow_svc = WorkflowRunService(self.db)
            db_campaign, db_scope_target, db_branch = await self._ensure_local_campaign_context(
                run_id=run_id,
                workflow_template=workflow_template,
                target=target,
                safe_mode=safe_mode,
                program_id=program_id,
                scope_target_id=scope_target_id,
                campaign_name=campaign_name,
                initiated_by=initiated_by,
            )
            if resume:
                existing = await workflow_svc.get_workflow_run_by_campaign(db_campaign.id)
                if (
                    existing is not None
                    and existing.template_name == workflow_template
                    and existing.target == target
                ):
                    db_workflow_run = existing
            if db_workflow_run is None:
                db_workflow_run = await workflow_svc.create_workflow_run(
                    campaign_run_id=db_campaign.id,
                    scope_target_id=db_scope_target.id if db_scope_target else None,
                    template_name=workflow_template,
                    target=target,
                    safe_mode=safe_mode,
                    dry_run=dry_run,
                    trigger_source=self.trigger_source,
                    total_phases=len(phase_specs),
                )
            if not dry_run:
                await workflow_svc.transition_workflow_run(
                    db_workflow_run,
                    WorkflowRunStatusEnum.RUNNING,
                )

            existing_stages: dict[str, Any] = {}
            if resume and db_workflow_run is not None:
                for stage_row in await workflow_svc.list_stage_runs(db_workflow_run.id):
                    existing_stages[stage_row.stage_name] = stage_row
            for stage_name, stage_phases in stage_to_phases.items():
                if stage_name in existing_stages:
                    db_stage_runs[stage_name] = existing_stages[stage_name]
                    continue
                stage_order = min(
                    (int(getattr(phase, "phase_order", 0)) for phase in stage_phases),
                    default=0,
                )
                db_stage_runs[stage_name] = await workflow_svc.create_stage_run(
                    workflow_run_id=db_workflow_run.id,
                    campaign_run_id=db_campaign.id,
                    stage_name=stage_name,
                    stage_order=stage_order,
                    phase_count=len(stage_phases),
                )

        now = datetime.now(timezone.utc).isoformat()
        manifest: dict[str, Any] = {
            "run_id": run_id,
            "workflow_template": workflow_template,
            "target": target,
            "safe_mode": safe_mode,
            "dry_run": dry_run,
            "status": "planned" if dry_run else "running",
            "created_at": now,
            "updated_at": now,
            "stages": {},
            "workflow_metadata": workflow_metadata,
        }

        if dry_run:
            manifest["plan"] = [
                {
                    "phase_name": phase.phase_name,
                    "stage": phase.phase_name.split("__", 1)[0],
                    "phase_order": phase.phase_order,
                    "depends_on_phase_name": phase.depends_on_phase_name,
                    "approval_required": phase.approval_required,
                    "queue_name": phase.queue_name,
                    "dispatch": (
                        phase.input_payload_json.get("dispatch")
                        if isinstance(phase.input_payload_json, dict)
                        else {}
                    ),
                }
                for phase in phase_specs
            ]
            manifest["status"] = "dry_run_complete"
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            manifest_path = self._write_manifest(store, manifest)
            summary_path = store.write_workflow_json(
                "summary.json",
                {
                    "run_id": run_id,
                    "workflow_template": workflow_template,
                    "status": manifest["status"],
                    "planned_steps": len(phase_specs),
                },
            )
            report_path = store.write_report_text(
                "report.md",
                self._markdown_report(
                    run_id=run_id,
                    workflow_template=workflow_template,
                    target=target,
                    stage_results=[],
                    prioritized_findings=[],
                ),
            )
            if workflow_svc is not None and db_workflow_run is not None:
                await workflow_svc.transition_workflow_run(
                    db_workflow_run,
                    WorkflowRunStatusEnum.COMPLETED,
                    artifact_manifest_path=manifest_path,
                    summary_artifact_path=summary_path,
                )
                if db_campaign is not None and db_branch is not None:
                    terminal_at = datetime.now(timezone.utc)
                    db_campaign.status = CampaignStatusEnum.COMPLETED
                    db_campaign.ended_at = terminal_at
                    db_branch.status = BranchStatusEnum.COMPLETED
                    db_branch.ended_at = terminal_at
                    await self.db.flush()
            return WorkflowExecutionResult(
                run_id=run_id,
                workflow_template=workflow_template,
                status="DRY_RUN_COMPLETE",
                target=target,
                manifest_path=manifest_path,
                summary_path=summary_path,
                report_path=report_path,
                stage_results=[],
                prioritized_findings=[],
                metrics={"planned_steps": len(phase_specs), "executed_tools": 0},
                campaign_id=str(db_campaign.id) if db_campaign is not None else None,
                workflow_run_id=str(db_workflow_run.id) if db_workflow_run is not None else None,
            )

        initialize_default_tools()
        registry = get_registry()
        loaded_manifest = self._load_manifest(store) if resume else None
        if loaded_manifest:
            manifest.update(loaded_manifest)
            manifest["status"] = "running"
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()

        stage_results: list[dict[str, Any]] = []
        aggregate_signal_records: list[dict[str, Any]] = []
        execution_count = 0

        if concurrency_limit < 1:
            raise ValueError("concurrency_limit must be >= 1")
        # Shared AsyncSession usage is not safe under concurrent stage tool execution.
        effective_concurrency = 1 if self.db is not None else max(1, concurrency_limit)
        manifest["effective_concurrency_limit"] = effective_concurrency

        async def run_phase(stage_name: str, phase, stage_run_id: UUID | None):
            nonlocal execution_count
            dispatch = (
                phase.input_payload_json.get("dispatch")
                if isinstance(phase.input_payload_json, dict)
                else {}
            )
            tool_id = str(dispatch.get("tool_id") or "").strip()
            params = dispatch.get("params") if isinstance(dispatch.get("params"), dict) else {}
            params = dict(params)
            params.setdefault("target", target)
            params.setdefault("run_id", run_id)
            if program_id is not None:
                params.setdefault("program_id", str(program_id))
            if db_workflow_run is not None:
                params.setdefault("workflow_id", str(db_workflow_run.id))

            start_ts = datetime.now(timezone.utc)
            exec_id = f"{run_id}:{stage_name}:{tool_id or phase.phase_name}"
            if tool_id in {"k1_correlation", "k1_priority_ranking"}:
                params.setdefault("signals", aggregate_signal_records)

            tool_execution_row = ToolExecution(
                execution_id=exec_id,
                run_id=run_id,
                stage_name=stage_name,
                tool_name=tool_id or phase.phase_name,
                target=params.get("target"),
                status="RUNNING",
                started_at=start_ts,
                metadata={
                    "phase_name": phase.phase_name,
                    "depends_on_phase_name": phase.depends_on_phase_name,
                    "approval_required": phase.approval_required,
                },
            )
            db_tool_execution = None
            if (
                workflow_svc is not None
                and db_campaign is not None
                and stage_run_id is not None
            ):
                db_tool_execution = await workflow_svc.create_tool_execution(
                    campaign_id=db_campaign.id,
                    stage_run_id=stage_run_id,
                    tool_name=tool_id or phase.phase_name,
                    execution_mode=(
                        str(dispatch.get("execution_mode")) if dispatch.get("execution_mode") else None
                    ),
                    target=params.get("target"),
                )
                db_tool_execution.branch_id = db_branch.id if db_branch is not None else None
                db_tool_execution.input_payload_json = params
                await self.db.flush()
                await workflow_svc.transition_tool_execution(
                    db_tool_execution,
                    ToolExecutionStatusEnum.RUNNING,
                )

            if not tool_id:
                tool_execution_row.status = "SKIPPED"
                tool_execution_row.error = "missing_tool_id"
                tool_execution_row.ended_at = datetime.now(timezone.utc)
                tool_execution_row.duration_ms = (
                    tool_execution_row.ended_at - tool_execution_row.started_at
                ).total_seconds() * 1000
                self._append_unique(store, "tool_executions", tool_execution_row.model_dump())
                if db_tool_execution is not None:
                    await workflow_svc.transition_tool_execution(
                        db_tool_execution,
                        ToolExecutionStatusEnum.FAILED,
                        stderr_summary="missing_tool_id",
                        error_message="missing_tool_id",
                    )
                return tool_execution_row.model_dump(), {}

            tool = registry.get(tool_id)
            if tool is None:
                tool_execution_row.status = "FAILED"
                tool_execution_row.error = f"tool_not_registered:{tool_id}"
                tool_execution_row.ended_at = datetime.now(timezone.utc)
                tool_execution_row.duration_ms = (
                    tool_execution_row.ended_at - tool_execution_row.started_at
                ).total_seconds() * 1000
                self._append_unique(store, "tool_executions", tool_execution_row.model_dump())
                if db_tool_execution is not None:
                    await workflow_svc.transition_tool_execution(
                        db_tool_execution,
                        ToolExecutionStatusEnum.FAILED,
                        stderr_summary=f"tool_not_registered:{tool_id}",
                        error_message=f"tool_not_registered:{tool_id}",
                    )
                return tool_execution_row.model_dump(), {}

            tool_params = self._allowed_tool_params(tool, params)
            result = await self._execute_tool(tool, tool_params)

            result_dict = result.to_dict()
            execution_count += 1
            raw_path = store.write_raw(
                f"{stage_name}/{tool_id}.json",
                {
                    "phase_name": phase.phase_name,
                    "tool_id": tool_id,
                    "params": tool_params,
                    "result": result_dict,
                },
            )
            normalized = normalize_tool_output(
                run_id=run_id,
                tool_name=tool_id,
                target=target,
                output=result_dict.get("output") if isinstance(result_dict.get("output"), dict) else {},
            )
            for model_key, rows in normalized.items():
                for row in rows:
                    self._append_unique(store, model_key, row)
                    if model_key in {
                        "discovered_assets",
                        "dns_records",
                        "live_services",
                        "url_records",
                        "endpoint_records",
                        "parameter_records",
                        "vuln_candidates",
                    }:
                        aggregate_signal_records.append(row)

            tool_execution_row.status = (
                "COMPLETED" if result.status.value == "completed" else "FAILED"
            )
            tool_execution_row.error = result.error
            tool_execution_row.exit_code = result_dict.get("metadata", {}).get("exit_code")
            tool_execution_row.raw_artifact_path = raw_path
            tool_execution_row.ended_at = datetime.now(timezone.utc)
            tool_execution_row.duration_ms = (
                tool_execution_row.ended_at - tool_execution_row.started_at
            ).total_seconds() * 1000
            tool_execution_row.metadata = {
                **tool_execution_row.metadata,
                "result_status": result.status.value,
                "normalized_counts": {key: len(value) for key, value in normalized.items()},
            }
            self._append_unique(store, "tool_executions", tool_execution_row.model_dump())
            
            # Visual Synthesis: Wire to V-RAD event bus
            bus = get_event_bus()
            bus.emit(
                MissionEvent(
                    event_type="tool_execution",
                    mission_id=run_id,
                    workflow_id=workflow_template,
                    phase=stage_name,
                    detail={
                        "tool_id": tool_id,
                        "status": tool_execution_row.status,
                        "findings": tool_execution_row.metadata["normalized_counts"],
                    },
                )
            )

            if db_tool_execution is not None and workflow_svc is not None:
                terminal_status = (
                    ToolExecutionStatusEnum.COMPLETED
                    if tool_execution_row.status == "COMPLETED"
                    else ToolExecutionStatusEnum.FAILED
                )
                await workflow_svc.transition_tool_execution(
                    db_tool_execution,
                    terminal_status,
                    exit_code=tool_execution_row.exit_code,
                    stdout_summary=self._summary_text(result_dict.get("output")),
                    stderr_summary=self._summary_text(result.error),
                    artifact_path=raw_path,
                    error_message=result.error,
                )
                if db_workflow_run is not None and db_campaign is not None:
                    for row in normalized.get("vuln_candidates", []):
                        await workflow_svc.create_workflow_finding(
                            workflow_run_id=db_workflow_run.id,
                            campaign_id=db_campaign.id,
                            stage_run_id=stage_run_id,
                            tool_execution_id=db_tool_execution.id,
                            asset_identifier=str(
                                row.get("target") or row.get("host") or target
                            ),
                            endpoint=row.get("endpoint"),
                            parameter=row.get("parameter_name"),
                            vulnerability_type=str(
                                row.get("title") or row.get("vulnerability_type") or "candidate"
                            ),
                            confidence_score=row.get("confidence"),
                            severity_hint=row.get("severity_hint"),
                            evidence_artifact_path=row.get("evidence_ref") or raw_path,
                            details_json=row,
                        )
            store.append_log(
                {
                    "event": "tool_execution",
                    "run_id": run_id,
                    "stage": stage_name,
                    "tool_id": tool_id,
                    "status": tool_execution_row.status,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            return tool_execution_row.model_dump(), normalized

        for stage in STAGES:
            phases = stage_to_phases.get(stage, [])
            if not phases:
                continue
            if resume and manifest.get("stages", {}).get(stage, {}).get("status") == "COMPLETED":
                stage_results.append(manifest["stages"][stage])
                continue

            stage_run_row = StageRun(
                stage_run_id=f"{run_id}:{stage}",
                run_id=run_id,
                stage_name=stage,
                status="RUNNING",
                tool_count=len(phases),
            )
            self._append_unique(store, "stage_runs", stage_run_row.model_dump())
            db_stage_run = db_stage_runs.get(stage)
            if (
                db_stage_run is not None
                and workflow_svc is not None
                and db_stage_run.status == StageRunStatusEnum.PENDING
            ):
                await workflow_svc.transition_stage_run(
                    db_stage_run,
                    StageRunStatusEnum.RUNNING,
                )

            ordered_phases = self._task_queue.order_stage_phases(
                stage=stage,
                phases=list(phases),
            )
            stage_tool_ids = []
            for phase in ordered_phases:
                dispatch = (
                    phase.input_payload_json.get("dispatch")
                    if isinstance(getattr(phase, "input_payload_json", None), dict)
                    else {}
                )
                stage_tool_ids.append(str(dispatch.get("tool_id") or "").strip())
            stage_concurrency = self._task_queue.suggested_concurrency(
                tool_ids=stage_tool_ids,
                requested=effective_concurrency,
            )

            if stage_concurrency == 1:
                tool_results = []
                for phase in ordered_phases:
                    tool_results.append(
                        await run_phase(
                            stage,
                            phase,
                            db_stage_run.id if db_stage_run is not None else None,
                        )
                    )
            else:
                semaphore = asyncio.Semaphore(stage_concurrency)

                async def run_phase_limited(phase):
                    async with semaphore:
                        return await run_phase(
                            stage,
                            phase,
                            db_stage_run.id if db_stage_run is not None else None,
                        )

                tool_results = list(await asyncio.gather(*(run_phase_limited(phase) for phase in ordered_phases)))
            failures = 0
            successes = 0
            stage_tool_rows: list[dict[str, Any]] = []
            for execution_row, _normalized in tool_results:
                stage_tool_rows.append(execution_row)
                if execution_row.get("status") == "COMPLETED":
                    successes += 1
                else:
                    failures += 1

            stage_status = "COMPLETED" if failures == 0 else "PARTIAL_FAILED"
            stage_summary = {
                "stage": stage,
                "status": stage_status,
                "tool_count": len(phases),
                "success_count": successes,
                "failed_count": failures,
                "concurrency_used": stage_concurrency,
                "execution_order": stage_tool_ids,
                "executions": stage_tool_rows,
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
            manifest.setdefault("stages", {})[stage] = stage_summary
            manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
            self._write_manifest(store, manifest)
            stage_results.append(stage_summary)
            if db_stage_run is not None and workflow_svc is not None:
                db_stage_run.completed_count = len(phases)
                await self.db.flush()
                await workflow_svc.transition_stage_run(
                    db_stage_run,
                    (
                        StageRunStatusEnum.COMPLETED
                        if failures == 0
                        else StageRunStatusEnum.FAILED
                    ),
                    failure_reason=(
                        None if failures == 0 else f"{failures} tool execution(s) failed"
                    ),
                )

        correlation_output = correlate_observations(aggregate_signal_records)
        correlation_rows = correlation_records_from_graph(
            run_id=run_id,
            graph=correlation_output.as_dict(),
        )
        for row in correlation_records_from_graph(
            run_id=run_id,
            graph=correlation_output.as_dict(),
        ):
            self._append_unique(store, "correlation_records", row)

        prioritized = correlation_output.priority_queue
        playbook_selection = self._select_playbooks_from_signals(
            aggregate_signal_records=aggregate_signal_records,
            prioritized_findings=prioritized,
        )
        if playbook_selection:
            self._emit_active_playbook_events(
                run_id=run_id,
                workflow_template=workflow_template,
                program_id=program_id,
                selection=playbook_selection,
            )

        analyst_export = AnalystExport(
            run_id=run_id,
            summary={
                "workflow_template": workflow_template,
                "target": target,
                "stages": len(stage_results),
                "executions": execution_count,
                "playbook_candidates": len(playbook_selection.get("playbook_recommendations", []))
                if playbook_selection
                else 0,
            },
            prioritized_findings=prioritized,
        )
        self._append_unique(store, "analyst_exports", analyst_export.model_dump())

        report = self._markdown_report(
            run_id=run_id,
            workflow_template=workflow_template,
            target=target,
            stage_results=stage_results,
            prioritized_findings=prioritized,
        )
        report_path = store.write_report_text("report.md", report)

        summary_payload = {
            "run_id": run_id,
            "workflow_template": workflow_template,
            "target": target,
            "status": "COMPLETED" if all(s["status"] == "COMPLETED" for s in stage_results) else "COMPLETED_WITH_FAILURES",
            "stage_results": stage_results,
            "prioritized_findings": prioritized,
            "metrics": {
                "stages_total": len(stage_results),
                "tool_executions_total": execution_count,
                "priority_items": len(prioritized),
                "playbook_recommendations_total": len(playbook_selection.get("playbook_recommendations", []))
                if playbook_selection
                else 0,
                "matched_cves_total": len(playbook_selection.get("cve_matches", []))
                if playbook_selection
                else 0,
            },
        }
        if playbook_selection:
            summary_payload["playbook_selection"] = playbook_selection
            manifest["playbook_selection"] = playbook_selection
        summary_path = store.write_workflow_json("summary.json", summary_payload)

        manifest["status"] = summary_payload["status"]
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        manifest_path = self._write_manifest(store, manifest)

        if workflow_svc is not None and db_workflow_run is not None:
            db_workflow_run.completed_phases = min(
                db_workflow_run.total_phases,
                sum(stage.get("tool_count", 0) for stage in stage_results),
            )
            await self.db.flush()
            workflow_terminal_status = (
                WorkflowRunStatusEnum.COMPLETED
                if summary_payload["status"] == "COMPLETED"
                else WorkflowRunStatusEnum.FAILED
            )
            await workflow_svc.transition_workflow_run(
                db_workflow_run,
                workflow_terminal_status,
                artifact_manifest_path=manifest_path,
                summary_artifact_path=summary_path,
            )
            if db_campaign is not None and db_branch is not None:
                terminal_at = datetime.now(timezone.utc)
                if workflow_terminal_status == WorkflowRunStatusEnum.COMPLETED:
                    db_campaign.status = CampaignStatusEnum.COMPLETED
                    db_branch.status = BranchStatusEnum.COMPLETED
                else:
                    db_campaign.status = CampaignStatusEnum.FAILED
                    db_campaign.last_error = "one or more workflow stages failed"
                    db_branch.status = BranchStatusEnum.FAILED
                    db_branch.blocked_reason = "workflow stage failure"
                db_campaign.ended_at = terminal_at
                db_branch.ended_at = terminal_at
                await self.db.flush()

            priority_rank_by_asset: dict[str, int] = {}
            for idx, item in enumerate(prioritized, start=1):
                asset_key = str(item.get("host") or item.get("asset") or "").strip()
                if asset_key and asset_key not in priority_rank_by_asset:
                    priority_rank_by_asset[asset_key] = idx
            for row in correlation_rows:
                asset = str(row.get("host") or "").strip()
                if not asset:
                    continue
                signal_sources: list[str] = []
                for key in ("urls", "endpoints", "parameters", "technologies"):
                    values = row.get(key)
                    if isinstance(values, list):
                        signal_sources.extend(str(item) for item in values if str(item).strip())
                ports = row.get("open_ports")
                if isinstance(ports, list):
                    signal_sources.extend(f"port:{port}" for port in ports)
                signal_sources = list(dict.fromkeys(signal_sources))
                await workflow_svc.create_workflow_correlation_record(
                    workflow_run_id=db_workflow_run.id,
                    campaign_id=db_campaign.id if db_campaign is not None else None,
                    asset_identifier=asset,
                    signal_sources=signal_sources,
                    confidence_score=row.get("confidence"),
                    priority_rank=priority_rank_by_asset.get(asset),
                    explanation=f"workflow correlation graph for {asset}",
                )

        return WorkflowExecutionResult(
            run_id=run_id,
            workflow_template=workflow_template,
            status=summary_payload["status"],
            target=target,
            manifest_path=manifest_path,
            summary_path=summary_path,
            report_path=report_path,
            stage_results=stage_results,
            prioritized_findings=prioritized,
            metrics=summary_payload["metrics"],
            campaign_id=str(db_campaign.id) if db_campaign is not None else None,
            workflow_run_id=str(db_workflow_run.id) if db_workflow_run is not None else None,
        )
