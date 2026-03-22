"""
Fallback Orchestrator
Manages automatic fallback chain when models fail or budget is exceeded
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from .model_bidding import TaskDefinition, ModelFamily

logger = logging.getLogger(__name__)


class FallbackReason(str, Enum):
    """Reasons for fallback"""
    BUDGET_EXCEEDED = "budget_exceeded"
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMIT = "rate_limit"
    API_ERROR = "api_error"
    QUALITY_DOWNGRADE = "quality_downgrade"


@dataclass
class FallbackAttempt:
    """Single attempt in fallback chain"""
    model_id: str
    model_family: ModelFamily
    estimated_cost_cents: float
    reason_for_fallback: Optional[FallbackReason] = None
    success: bool = False
    error: Optional[str] = None


@dataclass
class FallbackResult:
    """Result after fallback chain execution"""
    final_model: str
    attempts: List[FallbackAttempt]
    total_attempts: int
    success: bool
    final_cost_cents: float
    quality_degradation: str  # "none", "minimal", "moderate", "significant"


class FallbackOrchestrator:
    """
    Manage automatic fallback chain when models fail or budget exceeded.

    Fallback Chain (Quality → Cost):
    1. Claude Opus 4.5 ($15/1M) - Expert reasoning
    2. Claude 3.5 Sonnet ($3/1M) - Advanced reasoning
    3. GPT-4o ($5/1M) - Strong reasoning
    4. Gemini 2.0 Flash ($0.075/1M) - Basic reasoning
    5. Llama3.1:8b (local, $0) - Local fallback
    6. Qwen2.5-Coder:7b (local, $0) - Final fallback

    Strategy:
    - Try each model in order until one succeeds
    - Skip models that exceed remaining budget
    - Track quality degradation at each step
    - Always have local fallback available
    """

    def __init__(self):
        """Initialize fallback orchestrator"""

        # Define fallback chain (ordered by quality/cost)
        self.fallback_chain = [
            {
                "model_id": "claude-opus-4.5",
                "family": ModelFamily.ANTHROPIC_CLAUDE,
                "cost_multiplier": 15.0,
                "quality": "expert",
                "min_complexity": 8
            },
            {
                "model_id": "gpt-4-turbo",
                "family": ModelFamily.OPENAI_GPT,
                "cost_multiplier": 10.0,
                "quality": "expert",
                "min_complexity": 7
            },
            {
                "model_id": "claude-3.5-sonnet",
                "family": ModelFamily.ANTHROPIC_CLAUDE,
                "cost_multiplier": 3.0,
                "quality": "advanced",
                "min_complexity": 5
            },
            {
                "model_id": "gpt-4o",
                "family": ModelFamily.OPENAI_GPT,
                "cost_multiplier": 5.0,
                "quality": "advanced",
                "min_complexity": 5
            },
            {
                "model_id": "gemini-2.0-flash",
                "family": ModelFamily.GOOGLE_GEMINI,
                "cost_multiplier": 0.075,
                "quality": "basic",
                "min_complexity": 3
            },
            {
                "model_id": "llama3.1:8b",
                "family": ModelFamily.OLLAMA_LOCAL,
                "cost_multiplier": 0.0,
                "quality": "local_advanced",
                "min_complexity": 1
            },
            {
                "model_id": "qwen2.5-coder:7b",
                "family": ModelFamily.OLLAMA_LOCAL,
                "cost_multiplier": 0.0,
                "quality": "local_moderate",
                "min_complexity": 1
            }
        ]

        logger.info("✓ FallbackOrchestrator initialized with 7-tier fallback chain")

    async def execute_with_fallback(
        self,
        task: TaskDefinition,
        preferred_model: str,
        remaining_budget_cents: float,
        session_id: str
    ) -> FallbackResult:
        """
        Execute task with automatic fallback chain.

        Args:
            task: Task to execute
            preferred_model: Initially preferred model
            remaining_budget_cents: Available budget
            session_id: Session ID for tracking

        Returns:
            FallbackResult with execution details
        """

        logger.info(f"Executing task with fallback: {task.name}")
        logger.info(f"Preferred model: {preferred_model}, Budget: ${remaining_budget_cents/100:.2f}")

        attempts: List[FallbackAttempt] = []
        complexity = task.complexity_estimate or 5

        # Build ordered fallback list starting with preferred
        fallback_order = self._build_fallback_order(preferred_model, complexity)

        # Try each model in order
        for model_config in fallback_order:
            model_id = model_config["model_id"]
            cost = self._estimate_model_cost(task, model_config)

            # Skip if exceeds budget (unless it's local/free)
            if cost > remaining_budget_cents and cost > 0:
                attempt = FallbackAttempt(
                    model_id=model_id,
                    model_family=model_config["family"],
                    estimated_cost_cents=cost,
                    reason_for_fallback=FallbackReason.BUDGET_EXCEEDED,
                    success=False,
                    error=f"Cost ${cost/100:.2f} exceeds budget ${remaining_budget_cents/100:.2f}"
                )
                attempts.append(attempt)
                logger.info(f"Skipping {model_id}: budget exceeded")
                continue

            # Try execution
            logger.info(f"Attempting execution with {model_id} (${cost/100:.4f})...")

            try:
                # Simulate execution (in production, call actual model)
                success = await self._execute_with_model(task, model_id, session_id)

                if success:
                    attempt = FallbackAttempt(
                        model_id=model_id,
                        model_family=model_config["family"],
                        estimated_cost_cents=cost,
                        success=True
                    )
                    attempts.append(attempt)

                    # Calculate quality degradation
                    quality_degradation = self._calculate_quality_degradation(
                        preferred_model, model_id
                    )

                    logger.info(f"✓ Success with {model_id} (quality: {quality_degradation})")

                    return FallbackResult(
                        final_model=model_id,
                        attempts=attempts,
                        total_attempts=len(attempts),
                        success=True,
                        final_cost_cents=cost,
                        quality_degradation=quality_degradation
                    )

            except Exception as e:
                attempt = FallbackAttempt(
                    model_id=model_id,
                    model_family=model_config["family"],
                    estimated_cost_cents=cost,
                    reason_for_fallback=FallbackReason.API_ERROR,
                    success=False,
                    error=str(e)
                )
                attempts.append(attempt)
                logger.warning(f"Failed with {model_id}: {str(e)}")
                continue

        # If we get here, all models failed
        logger.error("All fallback attempts exhausted")

        return FallbackResult(
            final_model="none",
            attempts=attempts,
            total_attempts=len(attempts),
            success=False,
            final_cost_cents=0.0,
            quality_degradation="significant"
        )

    def _build_fallback_order(
        self,
        preferred_model: str,
        complexity: int
    ) -> List[Dict[str, Any]]:
        """Build ordered list of models to try"""

        # Start with preferred model if in chain
        ordered = []
        preferred_config = None

        for config in self.fallback_chain:
            if config["model_id"] == preferred_model:
                preferred_config = config
                break

        if preferred_config:
            ordered.append(preferred_config)

        # Add remaining models that meet complexity requirement
        for config in self.fallback_chain:
            if config not in ordered and complexity >= config["min_complexity"]:
                ordered.append(config)

        # Always ensure local fallback at end
        local_models = [c for c in self.fallback_chain if c["cost_multiplier"] == 0.0]
        for local_config in local_models:
            if local_config not in ordered:
                ordered.append(local_config)

        return ordered

    def _estimate_model_cost(
        self,
        task: TaskDefinition,
        model_config: Dict[str, Any]
    ) -> float:
        """Estimate cost for specific model"""

        if model_config["cost_multiplier"] == 0.0:
            return 0.0  # Local model

        input_tokens = task.estimated_tokens_input or 4000
        output_tokens = task.estimated_tokens_output or 2000

        # Base cost calculation
        cost_multiplier = model_config["cost_multiplier"]
        input_cost = (input_tokens / 1_000_000) * cost_multiplier * 100
        output_cost = (output_tokens / 1_000_000) * cost_multiplier * 100

        return input_cost + output_cost

    async def _execute_with_model(
        self,
        task: TaskDefinition,
        model_id: str,
        session_id: str
    ) -> bool:
        """Execute task with specific model (simulated)"""

        # In production: call actual model API
        # For now, simulate success

        # Simulate occasional failures for paid models.
        local_markers = ("llama", "qwen", "gemma", "mistral", "tinyllama", "codellama")
        if not any(marker in model_id.lower() for marker in local_markers):
            import random
            return random.random() > 0.1  # 90% success rate

        return True  # Local models always succeed

    def _calculate_quality_degradation(
        self,
        preferred_model: str,
        actual_model: str
    ) -> str:
        """Calculate quality degradation from fallback"""

        # Get quality levels
        preferred_quality = None
        actual_quality = None

        for config in self.fallback_chain:
            if config["model_id"] == preferred_model:
                preferred_quality = config["quality"]
            if config["model_id"] == actual_model:
                actual_quality = config["quality"]

        if preferred_quality == actual_quality:
            return "none"

        # Quality hierarchy
        quality_tiers = {
            "expert": 4,
            "advanced": 3,
            "basic": 2,
            "local_advanced": 1,
            "local_moderate": 0
        }

        preferred_tier = quality_tiers.get(preferred_quality, 2)
        actual_tier = quality_tiers.get(actual_quality, 2)

        diff = preferred_tier - actual_tier

        if diff == 0:
            return "none"
        elif diff == 1:
            return "minimal"
        elif diff == 2:
            return "moderate"
        else:
            return "significant"

    def get_fallback_chain_info(self) -> List[Dict[str, Any]]:
        """Get information about fallback chain"""

        return [
            {
                "model_id": config["model_id"],
                "family": config["family"].value,
                "quality": config["quality"],
                "cost_indicator": "free" if config["cost_multiplier"] == 0.0
                                  else f"${config['cost_multiplier']}/1M tokens",
                "min_complexity": config["min_complexity"]
            }
            for config in self.fallback_chain
        ]


# Global instance
_fallback_orchestrator: Optional[FallbackOrchestrator] = None


def get_fallback_orchestrator() -> FallbackOrchestrator:
    """Get global fallback orchestrator"""
    global _fallback_orchestrator
    if _fallback_orchestrator is None:
        _fallback_orchestrator = FallbackOrchestrator()
    return _fallback_orchestrator
