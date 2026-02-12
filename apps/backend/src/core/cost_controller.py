"""
Cost Controller for Kaison K1 Platform
Comprehensive cost control and optimization strategies
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from enum import Enum

from .budget_tracker import BudgetTracker, BudgetDecision, get_budget_tracker
from .model_bidding import TaskDefinition, UniversalModelFactory

logger = logging.getLogger(__name__)


class CostOptimizationStrategy(str, Enum):
    """Cost optimization strategies"""
    HYBRID_SPLIT = "hybrid_split"  # Split into local + paid subtasks
    DOWNGRADE_MODEL = "downgrade_model"  # Use cheaper paid model
    BATCH_PROCESSING = "batch_processing"  # Combine multiple tasks
    CACHE_RESULTS = "cache_results"  # Reuse previous results
    LOCAL_ONLY = "local_only"  # Force local execution


@dataclass
class CostOptimizationResult:
    """Result of cost optimization"""
    original_cost_cents: float
    optimized_cost_cents: float
    savings_cents: float
    savings_percent: float
    strategy_applied: CostOptimizationStrategy
    details: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class BudgetEnforcementResult:
    """Result of budget enforcement check"""
    decision: BudgetDecision
    approved: bool
    message: str
    session_budget_remaining: float
    daily_budget_remaining: float
    estimated_cost: float
    suggested_action: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class CostController:
    """
    Comprehensive cost control and optimization.

    Features:
    - Budget enforcement with multiple decision levels
    - Task optimization strategies
    - Cost forecasting
    - Emergency budget management
    """

    def __init__(
        self,
        budget_tracker: Optional[BudgetTracker] = None,
        model_factory: Optional[UniversalModelFactory] = None,
        enable_auto_optimization: bool = True
    ):
        """Initialize cost controller"""
        self.budget_tracker = budget_tracker or get_budget_tracker()
        self.model_factory = model_factory or UniversalModelFactory()
        self.enable_auto_optimization = enable_auto_optimization

        # Optimization thresholds
        self.min_cost_for_optimization_cents = 10  # $0.10
        self.high_cost_threshold_cents = 100  # $1.00

        # Cache for results (simple in-memory for now)
        self.result_cache: Dict[str, Any] = {}

        logger.info("✓ CostController initialized with auto-optimization: "
                   f"{enable_auto_optimization}")

    async def enforce_budget(
        self,
        task: TaskDefinition,
        session_id: str,
        user_id: str,
        estimated_cost_cents: float
    ) -> BudgetEnforcementResult:
        """
        Enforce budget constraints and return decision.

        Returns BudgetEnforcementResult with:
        - APPROVED: Proceed with paid API
        - DOWNGRADE: Use cheaper model
        - FALLBACK_LOCAL: Use local only
        - BLOCK: Budget exhausted
        """
        # Get current budget status
        session_budget = self.budget_tracker.get_session_budget(session_id)
        daily_budget = self.budget_tracker.get_daily_budget()

        session_remaining = session_budget.remaining_cents
        daily_remaining = daily_budget.remaining_cents

        # Check budget approval
        approved, decision, message = await self.budget_tracker.check_budget_approval(
            session_id, estimated_cost_cents, task.task_id
        )

        # Determine suggested action
        suggested_action = None
        if decision == BudgetDecision.FALLBACK_LOCAL:
            suggested_action = "Use local Ollama model (free) instead of paid API"
        elif decision == BudgetDecision.DOWNGRADE:
            suggested_action = "Use cheaper model (e.g., Gemini 2.0 Flash instead of Claude)"
        elif decision == BudgetDecision.BLOCK:
            suggested_action = "Request emergency budget increase or wait for daily reset"

        result = BudgetEnforcementResult(
            decision=decision,
            approved=approved,
            message=message,
            session_budget_remaining=session_remaining,
            daily_budget_remaining=daily_remaining,
            estimated_cost=estimated_cost_cents,
            suggested_action=suggested_action
        )

        logger.info(f"Budget enforcement: {decision.value} - {message}")
        return result

    async def optimize_task_for_cost(
        self,
        task: TaskDefinition,
        max_budget_cents: float,
        session_id: str
    ) -> CostOptimizationResult:
        """
        Optimize task to reduce cost while maintaining quality.

        Strategies:
        1. Split into deterministic (local) + reasoning (paid) subtasks
        2. Use cheaper models for appropriate complexity
        3. Cache and reuse results
        4. Batch similar tasks
        """
        # Estimate original cost
        original_cost = await self._estimate_task_cost(task)

        # If already cheap, no optimization needed
        if original_cost < self.min_cost_for_optimization_cents:
            return CostOptimizationResult(
                original_cost_cents=original_cost,
                optimized_cost_cents=original_cost,
                savings_cents=0.0,
                savings_percent=0.0,
                strategy_applied=CostOptimizationStrategy.LOCAL_ONLY,
                details="Task already cost-optimized (uses local models)"
            )

        # Try optimization strategies
        best_optimization = None
        best_savings = 0.0

        # Strategy 1: Hybrid split
        if self.enable_auto_optimization:
            hybrid_result = await self._try_hybrid_split(task, original_cost)
            if hybrid_result and hybrid_result.savings_cents > best_savings:
                best_optimization = hybrid_result
                best_savings = hybrid_result.savings_cents

        # Strategy 2: Model downgrade
        downgrade_result = await self._try_model_downgrade(task, original_cost, max_budget_cents)
        if downgrade_result and downgrade_result.savings_cents > best_savings:
            best_optimization = downgrade_result
            best_savings = downgrade_result.savings_cents

        # Strategy 3: Check cache
        cache_result = await self._try_cache_reuse(task)
        if cache_result and cache_result.savings_cents > best_savings:
            best_optimization = cache_result
            best_savings = cache_result.savings_cents

        # Return best optimization or original
        if best_optimization:
            logger.info(f"✓ Cost optimization: ${original_cost/100:.4f} -> "
                       f"${best_optimization.optimized_cost_cents/100:.4f} "
                       f"(${best_savings/100:.4f} saved, {best_optimization.savings_percent:.1f}%)")
            return best_optimization

        return CostOptimizationResult(
            original_cost_cents=original_cost,
            optimized_cost_cents=original_cost,
            savings_cents=0.0,
            savings_percent=0.0,
            strategy_applied=CostOptimizationStrategy.LOCAL_ONLY,
            details="No optimization available"
        )

    async def forecast_session_cost(
        self,
        session_id: str,
        pending_tasks: List[TaskDefinition]
    ) -> Dict[str, Any]:
        """
        Forecast total cost for pending tasks in session.

        Returns:
            {
                "total_estimated_cents": float,
                "tasks_breakdown": List[Dict],
                "budget_sufficient": bool,
                "recommendations": List[str]
            }
        """
        session_budget = self.budget_tracker.get_session_budget(session_id)
        remaining = session_budget.remaining_cents

        # Estimate each task
        task_estimates = []
        total_estimated = 0.0

        for task in pending_tasks:
            cost = await self._estimate_task_cost(task)
            task_estimates.append({
                "task_id": task.task_id,
                "task_name": task.name,
                "estimated_cost_cents": cost,
                "complexity": task.complexity_estimate
            })
            total_estimated += cost

        # Check if budget sufficient
        budget_sufficient = total_estimated <= remaining

        # Generate recommendations
        recommendations = []
        if not budget_sufficient:
            shortage = total_estimated - remaining
            recommendations.append(
                f"Budget shortage: ${shortage/100:.2f}. Consider:"
            )
            recommendations.append("- Use local models for lower complexity tasks")
            recommendations.append("- Split complex tasks into subtasks")
            recommendations.append("- Request emergency budget increase")

        if session_budget.utilization_percent > 80:
            recommendations.append(
                f"Session budget at {session_budget.utilization_percent:.1f}% - "
                "monitor spending closely"
            )

        forecast = {
            "session_id": session_id,
            "current_spent_cents": session_budget.spent_cents,
            "current_remaining_cents": remaining,
            "total_estimated_cents": total_estimated,
            "budget_after_tasks_cents": remaining - total_estimated,
            "tasks_breakdown": task_estimates,
            "budget_sufficient": budget_sufficient,
            "recommendations": recommendations
        }

        logger.info(f"Cost forecast for {session_id}: ${total_estimated/100:.2f} estimated "
                   f"(${remaining/100:.2f} remaining)")

        return forecast

    async def request_emergency_budget(
        self,
        session_id: str,
        additional_cents: int,
        justification: str,
        user_id: str
    ) -> Tuple[bool, str]:
        """
        Request emergency budget increase.

        In production, this would trigger approval workflow.
        For now, auto-approve small increases.
        """
        session_budget = self.budget_tracker.get_session_budget(session_id)

        # Auto-approve small increases (< $5)
        if additional_cents <= 500:
            success, message = await self.budget_tracker.increase_session_budget(
                session_id, additional_cents, approved_by=f"auto_approved_{user_id}"
            )

            if success:
                logger.warning(f"⚠️ Emergency budget increase: +${additional_cents/100:.2f} "
                              f"for {session_id} - {justification}")
            return success, message

        # Larger increases require manual approval
        logger.critical(f"🚨 Emergency budget request requires approval: "
                       f"+${additional_cents/100:.2f} for {session_id} - {justification}")

        return False, (
            f"Budget increase of ${additional_cents/100:.2f} requires admin approval. "
            "Contact administrator."
        )

    async def get_cost_summary(
        self,
        session_id: Optional[str] = None,
        timeframe: str = "session"  # "session" or "daily"
    ) -> Dict[str, Any]:
        """Get comprehensive cost summary"""
        if timeframe == "session" and session_id:
            session_budget = self.budget_tracker.get_session_budget(session_id)

            summary = {
                "timeframe": "session",
                "session_id": session_id,
                "budget_cents": session_budget.initial_budget_cents,
                "spent_cents": session_budget.spent_cents,
                "remaining_cents": session_budget.remaining_cents,
                "utilization_percent": session_budget.utilization_percent,
                "status": session_budget.status.value,
                "transaction_count": session_budget.transaction_count,
                "created_at": session_budget.created_at.isoformat()
            }

        elif timeframe == "daily":
            daily_budget = self.budget_tracker.get_daily_budget()

            summary = {
                "timeframe": "daily",
                "date": daily_budget.date,
                "budget_cents": daily_budget.total_budget_cents,
                "spent_cents": daily_budget.spent_cents,
                "remaining_cents": daily_budget.remaining_cents,
                "utilization_percent": daily_budget.utilization_percent,
                "status": daily_budget.status.value,
                "transaction_count": daily_budget.transaction_count,
                "session_count": daily_budget.session_count
            }

        else:
            # Get full analytics
            summary = await self.budget_tracker.get_budget_analytics()

        return summary

    # ========================================================================
    # Internal Optimization Methods
    # ========================================================================

    async def _estimate_task_cost(self, task: TaskDefinition) -> float:
        """Estimate cost for a task"""
        # Use model factory's estimation
        complexity = task.complexity_estimate or 5

        # Token estimates by complexity
        if not task.estimated_tokens_input:
            token_map = {
                1: (500, 200), 2: (1000, 400), 3: (2000, 800),
                4: (3000, 1200), 5: (4000, 2000), 6: (6000, 3000),
                7: (8000, 4000), 8: (10000, 5000), 9: (12000, 6000),
                10: (16000, 8000)
            }
            input_tokens, output_tokens = token_map.get(complexity, (4000, 2000))
        else:
            input_tokens = task.estimated_tokens_input
            output_tokens = task.estimated_tokens_output

        # Cost by complexity (assuming optimal model selection)
        if complexity <= 4:
            return 0.0  # Local models

        # Paid model costs (per 1M tokens)
        model_costs = {
            5: (0.075, 0.3),  # Gemini Flash
            6: (3.0, 15.0),  # Claude Sonnet
            7: (3.0, 15.0),  # Claude Sonnet
            8: (15.0, 75.0),  # Claude Opus
            9: (15.0, 75.0),  # Claude Opus
            10: (15.0, 75.0)  # Claude Opus
        }

        input_cost_per_1m, output_cost_per_1m = model_costs.get(complexity, (3.0, 15.0))

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m * 100
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m * 100

        return input_cost + output_cost

    async def _try_hybrid_split(
        self,
        task: TaskDefinition,
        original_cost: float
    ) -> Optional[CostOptimizationResult]:
        """Try splitting task into local + paid subtasks"""
        description = task.description.lower()

        # Patterns for splittable tasks
        deterministic_keywords = ["parse", "extract", "format", "validate", "count"]
        reasoning_keywords = ["analyze", "evaluate", "recommend", "plan"]

        has_deterministic = any(kw in description for kw in deterministic_keywords)
        has_reasoning = any(kw in description for kw in reasoning_keywords)

        if not (has_deterministic and has_reasoning):
            return None  # Can't split

        # Estimate: 50% deterministic (free), 50% reasoning (paid)
        optimized_cost = original_cost * 0.5
        savings = original_cost - optimized_cost

        return CostOptimizationResult(
            original_cost_cents=original_cost,
            optimized_cost_cents=optimized_cost,
            savings_cents=savings,
            savings_percent=(savings / original_cost * 100) if original_cost > 0 else 0,
            strategy_applied=CostOptimizationStrategy.HYBRID_SPLIT,
            details=f"Split into local deterministic + paid reasoning subtasks (50% savings)"
        )

    async def _try_model_downgrade(
        self,
        task: TaskDefinition,
        original_cost: float,
        max_budget: float
    ) -> Optional[CostOptimizationResult]:
        """Try using cheaper model"""
        complexity = task.complexity_estimate or 5

        # Can't downgrade low complexity (already using cheapest)
        if complexity < 6:
            return None

        # Model pricing tiers
        model_prices = {
            "claude-opus-4.5": 15.0,
            "gpt-4-turbo": 10.0,
            "gpt-4o": 5.0,
            "claude-3.5-sonnet": 3.0,
            "gemini-2.0-flash": 0.075
        }

        # For complexity 6-7, try downgrading Opus/GPT-4 to Sonnet/GPT-4o
        if complexity <= 7 and original_cost > 50:  # > $0.50
            # Estimate downgrade to mid-tier
            optimized_cost = original_cost * 0.3  # ~70% savings
            savings = original_cost - optimized_cost

            return CostOptimizationResult(
                original_cost_cents=original_cost,
                optimized_cost_cents=optimized_cost,
                savings_cents=savings,
                savings_percent=(savings / original_cost * 100) if original_cost > 0 else 0,
                strategy_applied=CostOptimizationStrategy.DOWNGRADE_MODEL,
                details="Downgrade to mid-tier model (Claude Sonnet / GPT-4o)"
            )

        return None

    async def _try_cache_reuse(self, task: TaskDefinition) -> Optional[CostOptimizationResult]:
        """Try reusing cached results"""
        # Simple cache key based on task description
        cache_key = f"{task.name}:{hash(task.description)}"

        if cache_key in self.result_cache:
            # Full cost savings
            original_cost = await self._estimate_task_cost(task)

            logger.info(f"✓ Cache hit for task: {task.name}")

            return CostOptimizationResult(
                original_cost_cents=original_cost,
                optimized_cost_cents=0.0,
                savings_cents=original_cost,
                savings_percent=100.0,
                strategy_applied=CostOptimizationStrategy.CACHE_RESULTS,
                details="Reused cached result (100% savings)"
            )

        return None


# Global instance
_cost_controller: Optional[CostController] = None


def get_cost_controller() -> CostController:
    """Get global cost controller instance"""
    global _cost_controller
    if _cost_controller is None:
        _cost_controller = CostController()
    return _cost_controller


def initialize_cost_controller(
    budget_tracker: Optional[BudgetTracker] = None,
    model_factory: Optional[UniversalModelFactory] = None
) -> CostController:
    """Initialize global cost controller"""
    global _cost_controller
    _cost_controller = CostController(
        budget_tracker=budget_tracker,
        model_factory=model_factory
    )
    logger.info("✓ Global cost controller initialized")
    return _cost_controller
