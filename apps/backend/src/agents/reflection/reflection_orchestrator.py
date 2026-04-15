from __future__ import annotations

import logging
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .adversarial_critic import AdversarialCritic
from .mutation_logic import MutationGenerator
from .obfuscation.payload_transformer import PayloadTransformer
from ...core.attack_surface_graph import AttackSurfaceGraph
from ...core.praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)

class ReflectionOrchestrator:
    """
    Orchestrates the pre-execution audit and post-execution reflection loops.
    """

    def __init__(
        self,
        graph: Optional[AttackSurfaceGraph] = None,
        max_mutation_attempts: int = 3,
    ) -> None:
        self.critic = AdversarialCritic()
        self.mutator = MutationGenerator()
        self.transformer = PayloadTransformer()
        self.graph = graph or AttackSurfaceGraph()
        self.history_path = Path("artifacts/reflection/reflection_history.json")
        self.retry_counts: Dict[str, int] = {}
        self.max_mutation_attempts = max_mutation_attempts
        self.critic.hard_block_threshold = max(1, max_mutation_attempts)

    def pre_execution_audit(self, instruction: Dict[str, Any], target: str) -> Dict[str, Any]:
        return self.critic.audit_instruction(instruction, target)

    def post_execution_reflection(
        self,
        playbook_id: str,
        result: Dict[str, Any],
        target: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze execution failures and generate mutations.
        Enforces at least 3 mutation attempts before hard-blocking a node.
        """
        key = f"{target}:{playbook_id}"
        attempt = self.retry_counts.get(key, 0) + 1
        self.retry_counts[key] = attempt

        target_fingerprint = dict(result.get("target_fingerprint") or {})
        error = result.get("error", "")
        output = str(result.get("output", ""))
        reflection = self.critic.reflect_on_failure(
            playbook_id=playbook_id,
            raw_output=output,
            error=error,
            target_fingerprint=target_fingerprint,
        )

        if not reflection:
            return None

        failure_type = reflection.get("detected_block") or "UNKNOWN"

        if not self.critic.allow_mutation_attempt(attempt):
            self._mark_hard_blocked(
                node_id=target,
                playbook_id=playbook_id,
                attempts=attempt - 1,
                reason=str(reflection.get("reflection") or failure_type),
            )
            logger.warning("Hard Blocked: %s after %d mutation attempts", key, attempt - 1)
            self._log_reflection(playbook_id, "HARD_BLOCKED", {"attempts": attempt - 1, "target": target})
            return {
                "mutation": "hard_blocked",
                "hard_blocked": True,
                "attempts": attempt - 1,
                "reason": str(reflection.get("reflection") or "Retry limit reached"),
            }

        mutation: Dict[str, Any]
        if failure_type == "WAF_BLOCK":
            target_context = self._derive_target_context(target_fingerprint, result)
            self._emit_vrad_phase("AMBER_PULSE", target, playbook_id, attempt, target_context)
            raw_payload = str(result.get("payload") or result.get("raw_payload") or "SAFE_PROBE")
            payload_type = str(result.get("payload_type") or "python")
            self._emit_vrad_phase("WHITE_FLARE", target, playbook_id, attempt, target_context)
            mutated_payload = self.transformer.generate_polymorphic_variant(
                raw_payload=raw_payload,
                payload_type=payload_type,
                target_context=target_context,
                strategy_hint="AST Mutation",
            )
            mutation = {
                "mutation": "ast_mutation",
                "strategy": "AST Mutation",
                "target_context": target_context,
                "mutated_payload": mutated_payload,
                "attempt": attempt,
                "hard_blocked": False,
                "reason": reflection.get("reflection"),
            }
        else:
            mutation = self.mutator.generate_retry_mutation(failure_type, {})
            mutation["attempt"] = attempt
            mutation["hard_blocked"] = False

        self._log_reflection(playbook_id, failure_type, mutation)
        return mutation

    def _derive_target_context(self, target_fingerprint: Dict[str, Any], result: Dict[str, Any]) -> str:
        explicit = str(result.get("target_context") or "").strip()
        if explicit:
            return explicit
        service = str(target_fingerprint.get("service") or result.get("service") or "UnknownService").strip()
        waf = str(target_fingerprint.get("waf") or result.get("waf") or "UnknownWAF").strip()
        return f"{service}/{waf}"

    def _mark_hard_blocked(self, node_id: str, playbook_id: str, attempts: int, reason: str) -> None:
        try:
            self.graph.mark_node_hard_blocked(
                node_id,
                playbook_id=playbook_id,
                reason=reason,
                attempts=attempts,
            )
        except Exception:
            pass

    def _emit_vrad_phase(
        self,
        visual: str,
        node_id: str,
        playbook_id: str,
        attempt: int,
        target_context: str,
    ) -> None:
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type="REFLECTION_PHASE_SIGNAL",
                    phase="reflection_loop",
                    node_id=node_id,
                    detail={
                        "playbook_id": playbook_id,
                        "attempt": attempt,
                        "target_context": target_context,
                        "v-rad_visual": visual,
                    },
                )
            )
        except Exception:
            pass

    def get_retry_count(self, playbook_id: str, target: str) -> int:
        return self.retry_counts.get(f"{target}:{playbook_id}", 0)

    def reset_retry_count(self, playbook_id: str, target: str) -> None:
        self.retry_counts.pop(f"{target}:{playbook_id}", None)

    def mark_success(self, playbook_id: str, target: str) -> None:
        self.reset_retry_count(playbook_id=playbook_id, target=target)

    def get_max_mutation_attempts(self) -> int:
        return self.max_mutation_attempts

    def set_max_mutation_attempts(self, value: int) -> None:
        self.max_mutation_attempts = max(1, int(value))

    def get_critic_threshold(self) -> int:
        return self.critic.hard_block_threshold

    def set_critic_threshold(self, value: int) -> None:
        self.critic.hard_block_threshold = max(1, int(value))

    def is_hard_blocked(self, playbook_id: str, target: str) -> bool:
        return self.get_retry_count(playbook_id, target) > self.critic.hard_block_threshold

    def clear_history(self) -> None:
        if self.history_path.exists():
            self.history_path.unlink()

    def load_history(self) -> Dict[str, Any]:
        if not self.history_path.exists():
            return {"reflections": []}
        return json.loads(self.history_path.read_text())

    def get_recent_reflections(self, limit: int = 20) -> Dict[str, Any]:
        history = self.load_history()
        reflections = history.get("reflections", [])
        return {"reflections": reflections[-max(1, limit):]}

    def replay_reflections(self) -> Dict[str, Any]:
        history = self.load_history()
        return {"count": len(history.get("reflections", [])), "history": history}

    def hard_block_reason(self, playbook_id: str, target: str) -> Optional[str]:
        history = self.load_history().get("reflections", [])
        key = f"{target}:{playbook_id}"
        for row in reversed(history):
            if row.get("playbook_id") == playbook_id and row.get("mutation", {}).get("target") == target:
                return row.get("failure_type")
        if self.get_retry_count(playbook_id, target) > self.critic.hard_block_threshold:
            return f"Retry threshold exceeded for {key}"
        return None

    def _log_reflection(self, playbook_id: str, failure_type: str, mutation: Dict[str, Any]):
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        history = json.loads(self.history_path.read_text()) if self.history_path.exists() else {"reflections": []}
        history["reflections"].append({
            "playbook_id": playbook_id,
            "failure_type": failure_type,
            "mutation": mutation,
            "timestamp": datetime.now(UTC).isoformat()
        })
        self.history_path.write_text(json.dumps(history, indent=2))
