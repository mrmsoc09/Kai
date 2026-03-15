"""
Hybrid Model Router for Kaison K1 Platform
Intelligent routing between local Ollama models and paid APIs with budget awareness

Routing Rules:
- Complexity 1-4 (TRIVIAL/BASIC) → Ollama local models (cost = $0)
- Complexity 5-10 (MODERATE/ADVANCED/EXPERT) → Paid APIs with budget check
- Budget exceeded → Automatic fallback to local with degradation warning
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import timezone, datetime
from enum import Enum

from .budget_tracker import BudgetTracker, BudgetDecision, get_budget_tracker
from .model_bidding import (
    UniversalModelFactory,
    TaskDefinition,
    ModelBid,
    TaskAssignment,
    ModelFamily
)

logger = logging.getLogger(__name__)


class RoutingStrategy(str, Enum):
    """Model routing strategy"""
    COST_OPTIMIZED = "cost_optimized"  # Prefer local, use paid only when needed
    BALANCED = "balanced"  # Balance cost and quality
    QUALITY_FIRST = "quality_first"  # Prefer best model within budget
    LOCAL_ONLY = "local_only"  # Never use paid APIs


class FallbackReason(str, Enum):
    """Reasons for falling back to local models"""
    BUDGET_EXCEEDED = "budget_exceeded"
    SESSION_LIMIT = "session_limit"
    DAILY_LIMIT = "daily_limit"
    COST_OPTIMIZATION = "cost_optimization"
    OPSEC_REQUIRED = "opsec_required"
    USER_PREFERENCE = "user_preference"


@dataclass
class RoutingDecision:
    """Result of routing decision"""
    model_id: str
    model_family: ModelFamily
    is_local: bool
    estimated_cost_cents: float
    complexity: int
    routing_strategy: RoutingStrategy
    fallback_applied: bool = False
    fallback_reason: Optional[FallbackReason] = None
    warning_message: Optional[str] = None
    budget_status: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ComplexityAnalysis:
    """Task complexity analysis result"""
    complexity_score: int  # 1-10
    reasoning: str
    deterministic_subtasks: List[str] = field(default_factory=list)
    reasoning_subtasks: List[str] = field(default_factory=list)
    can_optimize: bool = False


class HybridModelRouter:
    """
    Enhanced model routing with cost-awareness and budget management.
    Extends existing model_bidding.py with strict cost controls.
    """

    def __init__(
        self,
        budget_tracker: Optional[BudgetTracker] = None,
        model_factory: Optional[UniversalModelFactory] = None,
        default_strategy: RoutingStrategy = RoutingStrategy.COST_OPTIMIZED
    ):
        """Initialize hybrid router"""
        self.budget_tracker = budget_tracker or get_budget_tracker()
        self.model_factory = model_factory or UniversalModelFactory()
        self.default_strategy = default_strategy

        # Complexity thresholds
        self.local_complexity_threshold = 4  # 1-4 use local
        self.paid_complexity_threshold = 5  # 5-10 may use paid

        # Model tier mapping (complexity -> preferred local models)
        self.local_model_tiers = {
            1: ["tinyllama:1.1b", "gemma-2-2b"],  # Trivial
            2: ["gemma-2-9b", "mistral:7b"],  # Basic
            3: ["llama3:8b", "qwen-2.5-14b"],  # Moderate-low
            4: ["qwen-2.5-32b", "llama3:70b"],  # Moderate-high
        }

        # Paid model preferences by complexity
        self.paid_model_tiers = {
            5: ["gemini-2.0-flash", "gpt-4o-mini"],  # Moderate
            6: ["gpt-4o", "claude-3.5-sonnet"],  # Advanced-low
            7: ["claude-3.5-sonnet", "gpt-4o"],  # Advanced
            8: ["claude-opus-4.5", "gpt-4-turbo"],  # Expert-low
            9: ["claude-opus-4.5"],  # Expert
            10: ["claude-opus-4.5"],  # Expert-max
        }

        logger.info(f"✓ HybridModelRouter initialized with strategy: {default_strategy.value}")

    async def route_task(
        self,
        task: TaskDefinition,
        session_id: str,
        strategy: Optional[RoutingStrategy] = None
    ) -> RoutingDecision:
        """
        Main routing logic with budget gates.

        Returns RoutingDecision with selected model and metadata.
        """
        strategy = strategy or self.default_strategy

        # Step 1: Analyze complexity
        complexity = await self._analyze_complexity(task)
        logger.info(f"Task '{task.name}' complexity: {complexity}/10")

        # Step 2: Check if local-only strategy
        if strategy == RoutingStrategy.LOCAL_ONLY:
            return await self._route_to_ollama(task, complexity, FallbackReason.USER_PREFERENCE)

        # Step 3: RULE 1 - Always use local for simple tasks (1-4)
        if complexity <= self.local_complexity_threshold:
            logger.info(f"✓ Routing to local model (complexity {complexity} <= {self.local_complexity_threshold})")
            return await self._route_to_ollama(task, complexity, FallbackReason.COST_OPTIMIZATION)

        # Step 4: RULE 2 - Check budget before using paid APIs
        estimated_cost = await self._estimate_cost(task, complexity)
        remaining_budget = self.budget_tracker.get_remaining(session_id)

        logger.info(f"Estimated cost: ${estimated_cost/100:.4f}, Remaining: ${remaining_budget/100:.2f}")

        if estimated_cost > remaining_budget:
            logger.warning(f"⚠️ Budget exceeded: ${estimated_cost/100:.4f} > ${remaining_budget/100:.2f}")
            return await self._fallback_to_local(
                task,
                complexity,
                FallbackReason.BUDGET_EXCEEDED,
                f"Estimated cost ${estimated_cost/100:.4f} exceeds remaining ${remaining_budget/100:.2f}"
            )

        # Step 5: Check budget approval
        approved, decision, message = await self.budget_tracker.check_budget_approval(
            session_id, estimated_cost, task.task_id
        )

        if not approved or decision == BudgetDecision.BLOCK:
            logger.warning(f"⚠️ Budget check failed: {message}")
            return await self._fallback_to_local(task, complexity, FallbackReason.BUDGET_EXCEEDED, message)

        if decision == BudgetDecision.FALLBACK_LOCAL:
            return await self._fallback_to_local(task, complexity, FallbackReason.SESSION_LIMIT, message)

        # Step 6: RULE 3 - Use optimal paid model within budget
        if decision == BudgetDecision.DOWNGRADE:
            logger.info(f"Budget suggests downgrade: {message}")
            # Try cheaper paid models first
            return await self._route_to_paid_api(
                task, complexity, remaining_budget, prefer_cheaper=True
            )

        # Full budget available - use optimal model
        return await self._route_to_paid_api(task, complexity, remaining_budget)

    async def _analyze_complexity(self, task: TaskDefinition) -> int:
        """Analyze task complexity (1-10)"""
        # Use existing model factory analysis
        complexity = await self.model_factory.analyze_task_complexity(task)
        return complexity

    async def _estimate_cost(self, task: TaskDefinition, complexity: int) -> float:
        """Estimate cost for a task based on complexity and model choice"""
        # Get likely model for this complexity
        if complexity <= 4:
            return 0.0  # Local models are free

        # Estimate tokens based on complexity
        if not task.estimated_tokens_input:
            # Default estimates by complexity
            token_estimates = {
                5: (1000, 500),
                6: (2000, 1000),
                7: (4000, 2000),
                8: (8000, 4000),
                9: (12000, 6000),
                10: (16000, 8000)
            }
            input_tokens, output_tokens = token_estimates.get(complexity, (4000, 2000))
        else:
            input_tokens = task.estimated_tokens_input
            output_tokens = task.estimated_tokens_output

        # Get cheapest suitable model
        preferred_models = self.paid_model_tiers.get(complexity, ["claude-3.5-sonnet"])
        cheapest_model = preferred_models[0]  # Already sorted by preference

        # Cost calculation (using model_bidding metrics)
        model_costs = {
            "gemini-2.0-flash": (0.075, 0.3),
            "gpt-4o-mini": (0.15, 0.6),
            "gpt-4o": (5.0, 15.0),
            "claude-3.5-sonnet": (3.0, 15.0),
            "claude-opus-4.5": (15.0, 75.0),
            "gpt-4-turbo": (10.0, 30.0)
        }

        input_cost_per_1m, output_cost_per_1m = model_costs.get(cheapest_model, (3.0, 15.0))

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m * 100  # in cents
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m * 100

        return input_cost + output_cost

    async def _route_to_ollama(
        self,
        task: TaskDefinition,
        complexity: int,
        reason: FallbackReason
    ) -> RoutingDecision:
        """Route to local Ollama model based on complexity"""
        # Select best local model for complexity
        preferred_models = self.local_model_tiers.get(
            min(complexity, 4),  # Cap at 4 for local
            ["qwen-2.5-32b", "llama3:8b"]
        )

        # Use first available model
        selected_model = preferred_models[0]

        # Check if model is available
        available_models = await self.model_factory.discover_models()
        if selected_model not in available_models:
            # Fallback to any available local model
            local_available = [m for m, metrics in available_models.items() if metrics.local]
            if local_available:
                selected_model = local_available[0]
            else:
                logger.error("No local models available!")
                selected_model = "qwen-2.5-32b"  # Default

        return RoutingDecision(
            model_id=selected_model,
            model_family=ModelFamily.OLLAMA_LOCAL,
            is_local=True,
            estimated_cost_cents=0.0,
            complexity=complexity,
            routing_strategy=self.default_strategy,
            fallback_applied=(reason != FallbackReason.COST_OPTIMIZATION),
            fallback_reason=reason,
            budget_status="local_execution"
        )

    async def _route_to_paid_api(
        self,
        task: TaskDefinition,
        complexity: int,
        remaining_budget: float,
        prefer_cheaper: bool = False
    ) -> RoutingDecision:
        """Route to paid API model with budget constraints"""
        # Get preferred models for this complexity
        preferred_models = self.paid_model_tiers.get(complexity, ["claude-3.5-sonnet"])

        # If preferring cheaper, sort by cost
        if prefer_cheaper:
            model_costs = {
                "gemini-2.0-flash": 0.075,
                "gpt-4o-mini": 0.15,
                "gpt-4o": 5.0,
                "claude-3.5-sonnet": 3.0,
                "claude-opus-4.5": 15.0,
                "gpt-4-turbo": 10.0
            }
            preferred_models = sorted(preferred_models, key=lambda m: model_costs.get(m, 10.0))

        # Try to use model bidding system
        try:
            # Set budget constraint on task
            task.budget_cents = int(remaining_budget)

            # Get bids from available models
            bids = await self.model_factory.bid_models(task)

            # Filter to only paid models and within budget
            affordable_bids = [
                b for b in bids
                if b.estimated_cost_cents <= remaining_budget
                and b.model_id in preferred_models
            ]

            if not affordable_bids:
                # No affordable paid models - fallback to local
                logger.warning("⚠️ No affordable paid models available")
                return await self._fallback_to_local(
                    task, complexity, FallbackReason.BUDGET_EXCEEDED,
                    f"No paid models within budget of ${remaining_budget/100:.2f}"
                )

            # Select best bid
            winning_bid = affordable_bids[0]  # Already sorted by confidence

            logger.info(f"✓ Selected paid model: {winning_bid.model_id} "
                       f"(${winning_bid.estimated_cost_cents/100:.4f})")

            return RoutingDecision(
                model_id=winning_bid.model_id,
                model_family=winning_bid.family,
                is_local=False,
                estimated_cost_cents=winning_bid.estimated_cost_cents,
                complexity=complexity,
                routing_strategy=self.default_strategy,
                fallback_applied=False,
                budget_status="approved"
            )

        except Exception as e:
            logger.error(f"Error in paid API routing: {str(e)}")
            # Fallback to local on error
            return await self._fallback_to_local(
                task, complexity, FallbackReason.BUDGET_EXCEEDED,
                f"Routing error: {str(e)}"
            )

    async def _fallback_to_local(
        self,
        task: TaskDefinition,
        complexity: int,
        reason: FallbackReason,
        message: str = ""
    ) -> RoutingDecision:
        """Graceful degradation to local model with warning"""
        logger.warning(f"⚠️ Falling back to local model: {reason.value}")

        # Route to best available local model
        decision = await self._route_to_ollama(task, complexity, reason)

        # Add warning message
        decision.warning_message = message or f"Fallback to local: {reason.value}"
        decision.fallback_applied = True
        decision.fallback_reason = reason

        return decision

    async def optimize_task_for_cost(
        self,
        task: TaskDefinition,
        max_budget: float
    ) -> Tuple[List[TaskDefinition], ComplexityAnalysis]:
        """
        Split complex task into deterministic (local) and reasoning (paid) subtasks.

        Returns:
            (subtasks, analysis)
        """
        # Analyze task to identify subtasks
        complexity = await self._analyze_complexity(task)

        # Simple heuristic: split by capability requirements
        deterministic_subtasks = []
        reasoning_subtasks = []

        description_lower = task.description.lower()

        # Patterns for deterministic work
        deterministic_patterns = [
            "parse", "extract", "format", "validate", "check",
            "count", "list", "enumerate", "calculate"
        ]

        # Patterns for reasoning work
        reasoning_patterns = [
            "analyze", "evaluate", "recommend", "decide", "plan",
            "design", "reason", "explain", "assess"
        ]

        # Classify based on patterns
        is_deterministic = any(p in description_lower for p in deterministic_patterns)
        is_reasoning = any(p in description_lower for p in reasoning_patterns)

        analysis = ComplexityAnalysis(
            complexity_score=complexity,
            reasoning=f"Task complexity {complexity}/10",
            can_optimize=(complexity >= 5 and (is_deterministic or is_reasoning))
        )

        if not analysis.can_optimize:
            # Can't split - return original task
            return [task], analysis

        # Split into subtasks
        subtasks = []

        if is_deterministic:
            # Create local subtask
            deterministic_task = TaskDefinition(
                task_id=f"{task.task_id}_deterministic",
                name=f"{task.name} (Deterministic)",
                description=f"Deterministic processing: {task.description}",
                complexity_estimate=min(4, complexity),
                required_capabilities=["tool_use"],
                security_sensitive=task.security_sensitive,
                estimated_tokens_input=task.estimated_tokens_input // 2,
                estimated_tokens_output=task.estimated_tokens_output // 2
            )
            subtasks.append(deterministic_task)
            analysis.deterministic_subtasks.append(deterministic_task.name)

        if is_reasoning:
            # Create reasoning subtask
            reasoning_task = TaskDefinition(
                task_id=f"{task.task_id}_reasoning",
                name=f"{task.name} (Reasoning)",
                description=f"Reasoning/analysis: {task.description}",
                complexity_estimate=complexity,
                required_capabilities=["reasoning"],
                security_sensitive=task.security_sensitive,
                estimated_tokens_input=task.estimated_tokens_input // 2,
                estimated_tokens_output=task.estimated_tokens_output // 2,
                budget_cents=int(max_budget)
            )
            subtasks.append(reasoning_task)
            analysis.reasoning_subtasks.append(reasoning_task.name)

        if not subtasks:
            subtasks = [task]

        logger.info(f"Task optimization: {len(analysis.deterministic_subtasks)} deterministic, "
                   f"{len(analysis.reasoning_subtasks)} reasoning subtasks")

        return subtasks, analysis

    async def get_routing_analytics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get routing analytics and cost breakdown"""
        budget_analytics = await self.budget_tracker.get_budget_analytics()

        # Add routing-specific metrics
        routing_analytics = {
            "budget": budget_analytics,
            "routing": {
                "local_complexity_threshold": self.local_complexity_threshold,
                "paid_complexity_threshold": self.paid_complexity_threshold,
                "default_strategy": self.default_strategy.value,
                "available_local_models": len(self.local_model_tiers),
                "available_paid_models": len(self.paid_model_tiers)
            }
        }

        return routing_analytics


# Global instance
_hybrid_router: Optional[HybridModelRouter] = None


def get_hybrid_router() -> HybridModelRouter:
    """Get global hybrid router instance"""
    global _hybrid_router
    if _hybrid_router is None:
        _hybrid_router = HybridModelRouter()
    return _hybrid_router


def initialize_hybrid_router(
    budget_tracker: Optional[BudgetTracker] = None,
    model_factory: Optional[UniversalModelFactory] = None
) -> HybridModelRouter:
    """Initialize global hybrid router"""
    global _hybrid_router
    _hybrid_router = HybridModelRouter(
        budget_tracker=budget_tracker,
        model_factory=model_factory
    )
    logger.info("✓ Global hybrid router initialized")
    return _hybrid_router
