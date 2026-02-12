"""
Cost Optimizer
Advanced cost optimization strategies for task execution
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum

from .model_bidding import TaskDefinition

logger = logging.getLogger(__name__)


class OptimizationStrategy(str, Enum):
    """Available optimization strategies"""
    TASK_SPLITTING = "task_splitting"
    BATCH_PROCESSING = "batch_processing"
    RESULT_CACHING = "result_caching"
    MODEL_DOWNGRADE = "model_downgrade"
    PARALLEL_EXECUTION = "parallel_execution"


@dataclass
class OptimizationResult:
    """Result of cost optimization"""
    strategy: OptimizationStrategy
    original_cost_cents: float
    optimized_cost_cents: float
    savings_cents: float
    savings_percent: float
    execution_plan: Dict[str, Any]
    estimated_quality_impact: str  # "none", "minimal", "moderate"


class CostOptimizer:
    """
    Advanced cost optimization strategies.

    Strategies:
    1. Task Splitting - Split complex tasks into deterministic (local) + reasoning (paid)
    2. Batch Processing - Combine similar tasks to reduce overhead
    3. Result Caching - Reuse previous results for identical queries
    4. Model Downgrade - Use cheaper models when quality impact is minimal
    5. Parallel Execution - Run independent tasks concurrently
    """

    def __init__(self):
        """Initialize cost optimizer"""
        self.cache: Dict[str, Any] = {}
        logger.info("✓ CostOptimizer initialized")

    async def optimize_task_for_cost(
        self,
        task: TaskDefinition,
        max_budget_cents: float
    ) -> OptimizationResult:
        """
        Apply best optimization strategy for a task.

        Returns:
            OptimizationResult with optimized execution plan
        """

        logger.info(f"Optimizing task: {task.name}")

        # Estimate original cost
        original_cost = await self._estimate_task_cost(task)

        # Try optimization strategies in order of effectiveness
        strategies = [
            self._optimize_via_caching,
            self._optimize_via_task_splitting,
            self._optimize_via_model_downgrade,
            self._optimize_via_batch_processing
        ]

        best_result = None
        best_savings = 0.0

        for strategy_func in strategies:
            result = await strategy_func(task, original_cost, max_budget_cents)

            if result and result.savings_cents > best_savings:
                best_result = result
                best_savings = result.savings_cents

        # If no optimization found, return original
        if not best_result:
            return OptimizationResult(
                strategy=OptimizationStrategy.TASK_SPLITTING,
                original_cost_cents=original_cost,
                optimized_cost_cents=original_cost,
                savings_cents=0.0,
                savings_percent=0.0,
                execution_plan={"use_original_plan": True},
                estimated_quality_impact="none"
            )

        logger.info(f"✓ Optimization: ${original_cost/100:.4f} → ${best_result.optimized_cost_cents/100:.4f} "
                   f"({best_result.savings_percent:.1f}% savings)")

        return best_result

    async def _optimize_via_caching(
        self,
        task: TaskDefinition,
        original_cost: float,
        max_budget: float
    ) -> Optional[OptimizationResult]:
        """Strategy: Check cache for identical previous results"""

        # Generate cache key
        cache_key = self._generate_cache_key(task)

        if cache_key in self.cache:
            logger.info("✓ Cache hit - reusing previous result")

            return OptimizationResult(
                strategy=OptimizationStrategy.RESULT_CACHING,
                original_cost_cents=original_cost,
                optimized_cost_cents=0.0,
                savings_cents=original_cost,
                savings_percent=100.0,
                execution_plan={
                    "use_cached_result": True,
                    "cache_key": cache_key
                },
                estimated_quality_impact="none"
            )

        return None

    async def _optimize_via_task_splitting(
        self,
        task: TaskDefinition,
        original_cost: float,
        max_budget: float
    ) -> Optional[OptimizationResult]:
        """
        Strategy: Split task into deterministic (local, $0) + reasoning (paid) subtasks.

        Example:
        - Original: Complex analysis (all paid, $2.00)
        - Optimized: Data extraction (local, $0) + Analysis (paid, $1.00) = $1.00 savings
        """

        description = task.description.lower()

        # Check if task can be split
        deterministic_keywords = ["parse", "extract", "format", "count", "list"]
        reasoning_keywords = ["analyze", "evaluate", "recommend", "assess"]

        has_deterministic = any(kw in description for kw in deterministic_keywords)
        has_reasoning = any(kw in description for kw in reasoning_keywords)

        if not (has_deterministic and has_reasoning):
            return None  # Can't split

        # Estimate split costs
        # Assume 60% deterministic (free), 40% reasoning (paid)
        optimized_cost = original_cost * 0.4
        savings = original_cost - optimized_cost

        return OptimizationResult(
            strategy=OptimizationStrategy.TASK_SPLITTING,
            original_cost_cents=original_cost,
            optimized_cost_cents=optimized_cost,
            savings_cents=savings,
            savings_percent=(savings / original_cost * 100) if original_cost > 0 else 0,
            execution_plan={
                "subtasks": [
                    {
                        "type": "deterministic",
                        "description": "Extract and parse data",
                        "model": "qwen-2.5-32b",
                        "cost_cents": 0.0
                    },
                    {
                        "type": "reasoning",
                        "description": "Analyze and recommend",
                        "model": "claude-3.5-sonnet",
                        "cost_cents": optimized_cost
                    }
                ]
            },
            estimated_quality_impact="minimal"
        )

    async def _optimize_via_model_downgrade(
        self,
        task: TaskDefinition,
        original_cost: float,
        max_budget: float
    ) -> Optional[OptimizationResult]:
        """
        Strategy: Use cheaper model when quality impact is acceptable.

        Downgrade paths:
        - Claude Opus → Claude Sonnet (80% cost reduction)
        - GPT-4 → GPT-4o (60% cost reduction)
        - Claude Sonnet → Gemini Flash (97% cost reduction)
        """

        complexity = task.complexity_estimate or 5

        # Only downgrade for moderate complexity (5-7)
        if complexity < 5 or complexity > 7:
            return None

        # Estimate downgrade savings
        # Typical: Claude Opus ($15/1M) → Sonnet ($3/1M) = 80% savings
        downgrade_factor = 0.2  # 80% savings
        optimized_cost = original_cost * downgrade_factor
        savings = original_cost - optimized_cost

        return OptimizationResult(
            strategy=OptimizationStrategy.MODEL_DOWNGRADE,
            original_cost_cents=original_cost,
            optimized_cost_cents=optimized_cost,
            savings_cents=savings,
            savings_percent=(savings / original_cost * 100) if original_cost > 0 else 0,
            execution_plan={
                "original_model": "claude-opus-4.5",
                "downgraded_model": "claude-3.5-sonnet",
                "quality_impact": "minimal for moderate complexity tasks"
            },
            estimated_quality_impact="minimal"
        )

    async def _optimize_via_batch_processing(
        self,
        task: TaskDefinition,
        original_cost: float,
        max_budget: float
    ) -> Optional[OptimizationResult]:
        """
        Strategy: Combine with similar pending tasks to reduce overhead.

        Batch processing reduces:
        - Token overhead (system prompts, context loading)
        - API call overhead
        - Processing time
        """

        # Check if task is batchable
        if task.complexity_estimate and task.complexity_estimate < 3:
            # Simple tasks benefit from batching
            # Estimate 30% overhead savings
            savings_factor = 0.3
            optimized_cost = original_cost * (1 - savings_factor)
            savings = original_cost - optimized_cost

            return OptimizationResult(
                strategy=OptimizationStrategy.BATCH_PROCESSING,
                original_cost_cents=original_cost,
                optimized_cost_cents=optimized_cost,
                savings_cents=savings,
                savings_percent=(savings / original_cost * 100) if original_cost > 0 else 0,
                execution_plan={
                    "batch_size": 5,
                    "overhead_savings": "30%",
                    "note": "Combine with similar tasks in queue"
                },
                estimated_quality_impact="none"
            )

        return None

    async def _estimate_task_cost(self, task: TaskDefinition) -> float:
        """Estimate cost for a task"""

        complexity = task.complexity_estimate or 5

        # Token estimates by complexity
        token_map = {
            1: (500, 200), 2: (1000, 400), 3: (2000, 800),
            4: (3000, 1200), 5: (4000, 2000), 6: (6000, 3000),
            7: (8000, 4000), 8: (10000, 5000), 9: (12000, 6000),
            10: (16000, 8000)
        }

        input_tokens = task.estimated_tokens_input or token_map[complexity][0]
        output_tokens = task.estimated_tokens_output or token_map[complexity][1]

        # Cost by complexity (using optimal model)
        if complexity <= 4:
            return 0.0  # Local models

        # Paid model costs (per 1M tokens)
        model_costs = {
            5: (0.075, 0.3),  # Gemini Flash
            6: (3.0, 15.0),   # Claude Sonnet
            7: (3.0, 15.0),   # Claude Sonnet
            8: (15.0, 75.0),  # Claude Opus
            9: (15.0, 75.0),  # Claude Opus
            10: (15.0, 75.0)  # Claude Opus
        }

        input_cost_per_1m, output_cost_per_1m = model_costs.get(complexity, (3.0, 15.0))

        input_cost = (input_tokens / 1_000_000) * input_cost_per_1m * 100
        output_cost = (output_tokens / 1_000_000) * output_cost_per_1m * 100

        return input_cost + output_cost

    def _generate_cache_key(self, task: TaskDefinition) -> str:
        """Generate cache key for task"""
        return f"{task.name}:{hash(task.description)}:{task.complexity_estimate}"

    def store_result(self, task: TaskDefinition, result: Any):
        """Store result in cache"""
        cache_key = self._generate_cache_key(task)
        self.cache[cache_key] = result
        logger.info(f"Cached result for: {task.name}")

    def clear_cache(self):
        """Clear result cache"""
        self.cache.clear()
        logger.info("Cache cleared")


# Global instance
_cost_optimizer: Optional[CostOptimizer] = None


def get_cost_optimizer() -> CostOptimizer:
    """Get global cost optimizer"""
    global _cost_optimizer
    if _cost_optimizer is None:
        _cost_optimizer = CostOptimizer()
    return _cost_optimizer
