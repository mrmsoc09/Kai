from __future__ import annotations

import collections
import logging
import time
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .storage_manager import StorageManager
from .praison_execution_events import MissionEvent, get_event_bus

logger = logging.getLogger(__name__)

class ExperienceEngine:
    """
    K1 Hybrid Experience & Reflex Engine.
    Dual-layer memory: LRU Hot-Cache (Tactical) + ChromaDB (Persistent).
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ExperienceEngine, cls).__new__(cls)
            cls._instance._hot_cache = collections.OrderedDict()
            cls._instance._cache_limit = 1000
            cls._instance._storage = StorageManager()
            cls._instance._strategy_weights = collections.defaultdict(dict)
            cls._instance._variant_outcomes = {}
        return cls._instance

    @classmethod
    def get_instance(cls) -> ExperienceEngine:
        return cls()

    def _emit_vrad_telemetry(self, event_type: str, detail: Dict[str, Any]):
        try:
            get_event_bus().emit(
                MissionEvent(
                    event_type=event_type,
                    phase="reflex_engine",
                    detail=detail
                )
            )
        except Exception:
            pass

    def recommend_tactical_action(self, target_fingerprint: Dict[str, Any], playbook_id: str) -> Dict[str, Any]:
        """
        Pre-Execution Logic: Request tactical recommendation based on target vector.
        Goal: Sub-5ms lookup for hot targets.
        """
        start_time = time.perf_counter()
        
        # 1. Target Vector Construction
        target_key = f"{target_fingerprint.get('service')}:{target_fingerprint.get('version')}:{target_fingerprint.get('waf')}:{playbook_id}"
        
        # 2. Hot-Cache Layer (LRU)
        if target_key in self._hot_cache:
            self._hot_cache.move_to_end(target_key)
            latency = (time.perf_counter() - start_time) * 1000
            recommendation = self._hot_cache[target_key]
            
            self._emit_vrad_telemetry("CACHE_HIT_REFLEX", {
                "signal": "CACHE_HIT_REFLEX",
                "latency_ms": round(latency, 2),
                "playbook_id": playbook_id,
                "mutation": recommendation.get("suggested_mutation")
            })
            return recommendation

        # 3. Persistent Layer (ChromaDB)
        query_doc = f"service={target_fingerprint.get('service')} version={target_fingerprint.get('version')} waf={target_fingerprint.get('waf')} playbook={playbook_id}"
        similar = self._storage.query_similar_experiences(query_doc, n_results=5)
        
        latency = (time.perf_counter() - start_time) * 1000
        
        if not similar:
            return {"score": 0.0, "suggested_mutation": "default", "reason": "no_experience"}

        # Calculate result weight based on history
        total_weight = 0.0
        mutations = collections.Counter()
        
        for exp in similar:
            md = exp["metadata"]
            weight = float(md.get("result_weight", 0.0))
            total_weight += weight
            if weight > 0:
                mutations[md.get("mutation_used", "default")] += 1

        avg_weight = total_weight / len(similar)
        best_mutation = mutations.most_common(1)[0][0] if mutations else "default"

        target_class = self._derive_target_class(target_fingerprint)
        strategy_weights = self._strategy_weights.get(target_class, {})
        ast_weight = float(strategy_weights.get("AST Mutation", 0.0))
        if ast_weight > 0.0 and best_mutation in {"default", "user_agent_spoofing"}:
            best_mutation = "ast_mutation"

        recommendation = {
            "score": avg_weight,
            "suggested_mutation": best_mutation,
            "reason": "historical_recall",
            "recall_latency_ms": latency,
            "target_class": target_class,
            "strategy_weights": strategy_weights,
        }

        # Update Hot-Cache
        self._hot_cache[target_key] = recommendation
        if len(self._hot_cache) > self._cache_limit:
            self._hot_cache.popitem(last=False)

        self._emit_vrad_telemetry("VECTOR_DEEP_RECALL", {
            "signal": "VECTOR_DEEP_RECALL",
            "latency_ms": round(latency, 2),
            "avg_weight": avg_weight,
            "supporting_lessons": len(similar)
        })

        return recommendation

    def learn_from_outcome(
        self, 
        target_fingerprint: Dict[str, Any], 
        playbook_id: str, 
        mutation_used: str, 
        outcome: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Post-Execution Learning: Record experience in both layers.
        Schema result weights: Success (+1.0), WAF_Block (-1.0), Timeout (-0.5).
        """
        weight = 0.0
        if outcome == "Success":
            weight = 1.0
        elif outcome == "WAF_Trigger":
            weight = -1.0
        elif outcome in ("Timeout", "Rate_Limit"):
            weight = -0.5

        experience_id = str(uuid4())
        document = f"service={target_fingerprint.get('service')} version={target_fingerprint.get('version')} waf={target_fingerprint.get('waf')} playbook={playbook_id} outcome={outcome} mutation={mutation_used}"
        
        metadata = {
            "service": target_fingerprint.get("service"),
            "version": target_fingerprint.get("version"),
            "waf": target_fingerprint.get("waf"),
            "playbook_id": playbook_id,
            "mutation_used": mutation_used,
            "outcome": outcome,
            "result_weight": weight,
            "timestamp": datetime.now(UTC).isoformat(),
            **(metadata or {}),
        }

        # 1. Update Persistent Storage
        self._storage.persist_experience(experience_id, document, metadata)

        # 2. Update Hot-Cache (Invalidate or Update)
        target_key = f"{target_fingerprint.get('service')}:{target_fingerprint.get('version')}:{target_fingerprint.get('waf')}:{playbook_id}"
        self._hot_cache[target_key] = {
            "score": weight,
            "suggested_mutation": mutation_used if weight > 0 else "default",
            "reason": "latest_outcome"
        }
        self._hot_cache.move_to_end(target_key)

        logger.info(f"Experience Engine: Learned from {outcome} (weight: {weight}) for {playbook_id}")
        
        self._emit_vrad_telemetry("EXPERIENCE_LEARNED", {
            "playbook_id": playbook_id,
            "outcome": outcome,
            "weight": weight
        })
        self._update_variant_strategy_weights(
            target_fingerprint=target_fingerprint,
            playbook_id=playbook_id,
            mutation_used=mutation_used,
            outcome=outcome,
            metadata=metadata or {},
        )

    def _derive_target_class(self, target_fingerprint: Dict[str, Any]) -> str:
        service = str(target_fingerprint.get("service") or "unknown_service").strip().lower()
        waf = str(target_fingerprint.get("waf") or "unknown_waf").strip().lower()
        return f"{service}:{waf}"

    def promote_strategy_for_target_class(
        self,
        target_class: str,
        strategy: str,
        *,
        delta: float,
        reason: str,
    ) -> None:
        current = float(self._strategy_weights[target_class].get(strategy, 0.0))
        updated = max(-2.0, min(2.0, current + delta))
        self._strategy_weights[target_class][strategy] = updated
        self._emit_vrad_telemetry(
            "RL_POLICY_WEIGHT_UPDATED",
            {
                "target_class": target_class,
                "strategy": strategy,
                "previous_weight": round(current, 4),
                "new_weight": round(updated, 4),
                "delta": round(delta, 4),
                "reason": reason,
            },
        )

    def get_strategy_weights(self, target_class: str) -> Dict[str, float]:
        return dict(self._strategy_weights.get(target_class, {}))

    def _update_variant_strategy_weights(
        self,
        *,
        target_fingerprint: Dict[str, Any],
        playbook_id: str,
        mutation_used: str,
        outcome: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        RL consistency rule:
        If Polymorphic Variant C succeeds where Standard Variant A failed,
        increase AST Mutation strategy weight for the same target class.
        """
        target_class = str(metadata.get("target_class") or self._derive_target_class(target_fingerprint))
        variant_label = str(metadata.get("variant_label") or mutation_used).strip().lower()
        key = f"{target_class}:{playbook_id}"
        bucket = self._variant_outcomes.setdefault(key, {})

        if "standard variant a" in variant_label:
            bucket["standard_variant_a_outcome"] = outcome
            return

        if "polymorphic variant c" in variant_label and outcome == "Success":
            standard_outcome = str(bucket.get("standard_variant_a_outcome") or "")
            if standard_outcome in {"WAF_Trigger", "Timeout", "Rate_Limit", "Silence"}:
                self.promote_strategy_for_target_class(
                    target_class,
                    "AST Mutation",
                    delta=0.35,
                    reason="Polymorphic Variant C succeeded after Standard Variant A failed",
                )
