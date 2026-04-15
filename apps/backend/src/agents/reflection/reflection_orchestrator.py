from __future__ import annotations

import logging
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .adversarial_critic import AdversarialCritic
from .mutation_logic import MutationGenerator
from ..core.praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)

class ReflectionOrchestrator:
    """
    Orchestrates the pre-execution audit and post-execution reflection loops.
    """

    def __init__(self) -> None:
        self.critic = AdversarialCritic()
        self.mutator = MutationGenerator()
        self.history_path = Path("artifacts/reflection/reflection_history.json")
        self.retry_counts: Dict[str, int] = {}

    def pre_execution_audit(self, instruction: Dict[str, Any], target: str) -> Dict[str, Any]:
        return self.critic.audit_instruction(instruction, target)

    def post_execution_reflection(self, playbook_id: str, result: Dict[str, Any], target: str) -> Optional[Dict[str, Any]]:
        """Analyzes failures and generates mutations with a 3-retry limit."""
        key = f"{target}:{playbook_id}"
        self.retry_counts[key] = self.retry_counts.get(key, 0) + 1
        
        if self.retry_counts[key] > 3:
            logger.warning(f"Hard Block: {key} reached max retry limit.")
            return None

        error = result.get("error", "")
        output = str(result.get("output", ""))
        
        failure_type = None
        if "403" in error or "WAF" in output:
            failure_type = "WAF_BLOCK"
        elif "429" in error:
            failure_type = "RATE_LIMIT"
            
        if failure_type:
            mutation = self.mutator.generate_retry_mutation(failure_type, {})
            self._log_reflection(playbook_id, failure_type, mutation)
            return mutation
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
