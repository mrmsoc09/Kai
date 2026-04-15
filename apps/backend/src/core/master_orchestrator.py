from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .cve_playbook_selector import CVEPlaybookSelector
from .experience_memory import ExperienceMemory
from .experience_engine import ExperienceEngine
from .adversarial_critic import AdversarialCritic
from .mutation_generator import MutationGenerator
from .orchestrator_dispatcher import OrchestratorDispatcher
from .playbook_memory import PlaybookMemory
from .workflow_executor import WorkflowExecutionResult, WorkflowExecutor


@dataclass
class PlaybookSelectionResult:
    matched_cves: list[dict[str, Any]]
    recommendations: list[dict[str, Any]]
    chain_plan: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched_cves": self.matched_cves,
            "recommendations": self.recommendations,
            "chain_plan": self.chain_plan,
        }


class MasterOrchestrator:
    """
    High-level orchestrator bridge used to wire CVE playbook selection into execution.

    This class keeps orchestration deterministic:
    - runs workflows through WorkflowExecutor
    - queries the local CVE KB + playbook registry for discovered tech/service signals
    - prioritizes chainable playbooks (information disclosure -> auth bypass -> impact)
    """

    def __init__(
        self,
        workflow_executor: WorkflowExecutor | None = None,
        *,
        enable_watcher: bool = False,
    ) -> None:
        self.workflow_executor = workflow_executor or WorkflowExecutor()
        self._selector = CVEPlaybookSelector()
        self.playbook_memory = PlaybookMemory.get_instance()
        self.experience_memory = ExperienceMemory.get_instance()
        self.experience_engine = ExperienceEngine.get_instance()
        self.critic = AdversarialCritic(self.experience_memory)
        self.mutator = MutationGenerator()
        self.dispatcher = OrchestratorDispatcher(playbook_memory=self.playbook_memory)
        if enable_watcher:
            self.playbook_memory.start_watcher()

    async def execute_workflow(
        self,
        *,
        workflow_template: str,
        target: str,
        run_id: str | None = None,
        safe_mode: bool = True,
        dry_run: bool = False,
        concurrency_limit: int = 4,
    ) -> WorkflowExecutionResult:
        return await self.workflow_executor.execute_template(
            workflow_template=workflow_template,
            target=target,
            run_id=run_id,
            safe_mode=safe_mode,
            dry_run=dry_run,
            concurrency_limit=concurrency_limit,
        )

    def select_playbooks_for_discovery(
        self,
        *,
        service_findings: list[dict[str, Any]],
        prioritized_findings: list[dict[str, Any]] | None = None,
    ) -> PlaybookSelectionResult:
        """
        Query local CVE Library + Playbook Index upon discovery of new services/versions.
        Prioritizes chainable logic (e.g. Info Leak -> Auth Bypass).
        """
        selection = self._selector.select_for_signals(
            signals=service_findings,
            prioritized_findings=prioritized_findings or [],
        )
        
        # High-velocity cross-reference hook
        recommendations = selection.get("playbook_recommendations", [])
        
        return PlaybookSelectionResult(
            matched_cves=selection.get("cve_matches", []),
            recommendations=recommendations,
            chain_plan=selection.get("chain_plan", []),
        )

    def match_target_to_playbook(
        self,
        *,
        cve_id: str,
        tech_stack: list[str] | tuple[str, ...] | None = None,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        return self.dispatcher.match_target_to_playbook(cve_id, tech_stack, top_k=top_k)

    def validate_handoff(self, *, output_schema: str, input_schema: str) -> bool:
        return self.dispatcher.validate_handoff(output_schema, input_schema)

    def dispatch_instruction_tuples(
        self,
        instructions: list[list[Any] | tuple[Any, ...]],
        *,
        target: str,
        target_fingerprint: dict[str, Any] | None = None,
        fallback_list: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        fp = dict(target_fingerprint or {})
        if "service" not in fp:
            fp["service"] = target
            
        adapted_base = self._apply_memory_strategy(
            instructions=instructions,
            target_fingerprint=fp,
            fallback_list=fallback_list or [],
        )

        final_instructions: list[list[Any]] = []
        for raw in adapted_base:
            step, playbook, params, timing, fallback = self._as_instruction(raw)
            
            # Pre-Flight Critic Audit
            decision, reason = self.critic.audit_instruction(playbook, params, fp)
            
            if decision == "DENY":
                logger.warning(f"Instruction blocked by critic: {playbook}. Reason: {reason}")
                continue
            elif decision == "MUTATE":
                logger.info(f"Instruction mutated by critic: {playbook}. Reason: {reason}")
                # We need a mutation type; for now, derive from playbook or critic reason
                mutation = "hex_encoding" if "sqli" in playbook.lower() else "user_agent_spoofing"
                params, timing = self.mutator.mutate_instruction(playbook, params, timing, mutation)
            
            final_instructions.append([step, playbook, params, timing, fallback])

        results = self.dispatcher.dispatch_instruction_tuples(final_instructions, target=target)
        self._ingest_execution_feedback(
            instructions=final_instructions,
            results=results,
            target_fingerprint=fp,
        )
        return results

    def dispatch_cached_plan(
        self,
        *,
        key: str,
        target: str,
        target_fingerprint: dict[str, Any] | None = None,
        fallback_list: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        plan = self.dispatcher.memory.get_index("execution_plan_cache", {})
        instructions = plan.get(key, []) if isinstance(plan, dict) else []
        return self.dispatch_instruction_tuples(
            instructions,
            target=target,
            target_fingerprint=target_fingerprint,
            fallback_list=fallback_list,
        )

    @staticmethod
    def _as_instruction(raw: list[Any] | tuple[Any, ...]) -> tuple[int, str, dict[str, Any], dict[str, Any], Any]:
        if not isinstance(raw, (list, tuple)) or len(raw) < 5:
            return 0, "", {}, {}, None
        step_n, playbook_name, params, timing, fallback = raw[:5]
        step = int(step_n) if str(step_n).isdigit() else 0
        params_dict = params if isinstance(params, dict) else {}
        timing_dict = timing if isinstance(timing, dict) else {}
        return step, str(playbook_name), dict(params_dict), dict(timing_dict), fallback

    def _apply_memory_strategy(
        self,
        *,
        instructions: list[list[Any] | tuple[Any, ...]],
        target_fingerprint: dict[str, Any],
        fallback_list: list[str],
    ) -> list[list[Any]]:
        adapted: list[list[Any]] = []
        for raw in instructions:
            step, playbook, params, timing, fallback = self._as_instruction(raw)
            if not playbook:
                continue
            mutation_fallbacks: list[str] = list(fallback_list)
            if isinstance(fallback, list):
                mutation_fallbacks.extend(str(x) for x in fallback if str(x).strip())
            elif isinstance(fallback, str) and fallback.strip():
                mutation_fallbacks.append(fallback.strip())

            # Legacy ExperienceMemory logic
            strategy = self.experience_memory.recommend_strategy(
                target_fingerprint=target_fingerprint,
                attempted_cve=playbook,
                fallback_list=mutation_fallbacks,
            )
            
            # New Hybrid Experience Engine logic (Reflex Engine)
            tactical = self.experience_engine.recommend_tactical_action(
                target_fingerprint=target_fingerprint,
                playbook_id=playbook
            )
            
            # Mutation Override Logic: If tactical score is negative, force mutation
            if tactical.get("score", 0.0) < 0:
                params["mutation"] = tactical.get("suggested_mutation", "hex_encoding")
                params["mutation_reason"] = tactical.get("reason", "reflex_override")
                timing.setdefault("profile", "stealth") # Force stealth on negative results
            elif tactical.get("suggested_mutation") and tactical["suggested_mutation"] != "default":
                params["mutation"] = tactical["suggested_mutation"]

            if strategy.get("selected_mutation") and not params.get("mutation"):
                params["mutation"] = strategy["selected_mutation"]
            if strategy.get("low_slow"):
                timing.setdefault("profile", "low_slow")
                timing.setdefault("delay_ms", 1500)
                params.setdefault("request_rate", 1)
                params.setdefault("max_retries", 1)
            
            params["_memory_strategy"] = strategy
            params["_tactical_recommendation"] = tactical
            adapted.append([step, playbook, params, timing, fallback])
        return adapted

    @staticmethod
    def _infer_outcome(result: dict[str, Any]) -> str:
        text = " ".join(
            [
                str(result.get("status") or ""),
                str(result.get("error") or ""),
                json_dumps_safe(result.get("output")),
            ]
        ).lower()
        if "waf" in text or "cloudflare" in text or "akamai" in text:
            return "WAF_Trigger"
        if "rate" in text and "limit" in text:
            return "Rate_Limit"
        status = str(result.get("status") or "").lower()
        if status in {"completed", "success"}:
            return "Success"
        return "Silence"

    def _ingest_execution_feedback(
        self,
        *,
        instructions: list[list[Any]],
        results: list[dict[str, Any]],
        target_fingerprint: dict[str, Any],
    ) -> None:
        by_step: dict[int, dict[str, Any]] = {}
        for row in results:
            try:
                by_step[int(row.get("step") or 0)] = row
            except Exception:
                continue

        for raw in instructions:
            step, playbook, params, _timing, _fallback = self._as_instruction(raw)
            result = by_step.get(step, {})
            outcome = self._infer_outcome(result)
            mutation = str(params.get("mutation") or "default")
            extra = {
                "tool_id": result.get("tool_id"),
                "status": result.get("status"),
                "error": result.get("error"),
            }
            # Update legacy memory
            self.experience_memory.record_lesson(
                target_fingerprint=target_fingerprint,
                attempted_cve=playbook,
                outcome=outcome,
                mutation_used=mutation,
                metadata=extra,
            )
            
            # Update Hybrid Experience Engine (Hot-Cache + Persistent)
            self.experience_engine.learn_from_outcome(
                target_fingerprint=target_fingerprint,
                playbook_id=playbook,
                mutation_used=mutation,
                outcome=outcome
            )

            # Failure Reflector Logic
            if outcome in ("WAF_Trigger", "Rate_Limit", "Timeout"):
                reflection = self.critic.reflect_on_failure(
                    playbook_id=playbook,
                    raw_output=str(result.get("output", "")),
                    error=str(result.get("error", "")),
                    target_fingerprint=target_fingerprint
                )
                if reflection:
                    # Log to reflection_history.json
                    history_path = Path("artifacts/reflection/reflection_history.json")
                    history_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        history = json.loads(history_path.read_text()) if history_path.exists() else {"reflections": []}
                        history["reflections"].append({
                            **reflection,
                            "timestamp": datetime.now(UTC).isoformat()
                        })
                        history_path.write_text(json.dumps(history, indent=2))
                    except Exception as e:
                        logger.error(f"Failed to log reflection: {e}")


def json_dumps_safe(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)
