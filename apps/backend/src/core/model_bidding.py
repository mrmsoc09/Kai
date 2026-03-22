"""
K1 Intelligent Model Bidding System
Routes tasks to optimal models based on complexity, cost, and OPSEC requirements
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import timezone, datetime
import asyncio
import json
import subprocess
import logging

from .confidence_policy import evaluate_confidence_policy
from .model_decision_observability import emit_model_decision_event

logger = logging.getLogger(__name__)


class ModelFamily(str, Enum):
    """Model families available"""
    CLAUDE = "claude"
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA_LOCAL = "ollama_local"
    GEMMA = "gemma"
    QWEN = "qwen"


class TaskComplexity(str, Enum):
    """Task complexity levels"""
    TRIVIAL = "trivial"  # 1-2: Simple queries
    BASIC = "basic"  # 3-4: Basic tooling
    MODERATE = "moderate"  # 5-6: Complex analysis
    ADVANCED = "advanced"  # 7-8: Reasoning + code
    EXPERT = "expert"  # 9-10: Novel approaches


@dataclass
class ModelMetrics:
    """Performance characteristics of a model"""
    model_id: str
    family: ModelFamily
    local: bool  # Is it a local model?
    available: bool
    cost_per_1m_input: float  # USD per million input tokens
    cost_per_1m_output: float  # USD per million output tokens
    avg_latency_ms: float  # Average response time
    reasoning_quality: float  # 0-1, capability for complex reasoning
    code_quality: float  # 0-1, capability for code generation
    opsec_score: float  # 0-1, privacy/security score (local=1.0, cloud=0.3-0.8)
    supported_complexity: Tuple[int, int]  # Min-max complexity it handles well
    last_checked: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskDefinition:
    """Definition of a task to be executed"""
    task_id: str
    name: str
    description: str
    complexity_estimate: int  # 1-10
    required_capabilities: List[str]  # "reasoning", "code_gen", "tool_use"
    security_sensitive: bool  # Requires OPSEC
    estimated_tokens_input: int
    estimated_tokens_output: int
    max_latency_seconds: Optional[int] = None
    budget_cents: Optional[int] = None  # Max cost in cents


@dataclass
class ModelBid:
    """Bid from a model for a task"""
    model_id: str
    family: ModelFamily
    task_id: str
    estimated_cost_cents: float
    estimated_latency_ms: float
    confidence_score: float  # 0-1, how suitable is this model?
    reasoning: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TaskAssignment:
    """Assignment of task to winning model"""
    task_id: str
    assigned_model: str
    assigned_family: ModelFamily
    bid: ModelBid
    verification_model: Optional[str] = None  # Model to verify result
    verification_family: Optional[ModelFamily] = None
    assigned_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    actual_cost_cents: Optional[float] = None
    actual_latency_ms: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    policy_action: str = "allow"
    policy_reason: str = "confidence_within_policy"


class UniversalModelFactory:
    """Factory for discovering, bidding, and allocating models"""

    def __init__(self):
        self.available_models: Dict[str, ModelMetrics] = {}
        self.task_history: List[TaskAssignment] = []
        self.model_performance: Dict[str, Dict[str, float]] = {}  # model_id -> metrics
        self.local_models_cache: List[str] = []

        # Model configuration
        self.model_configs = {
            "claude-opus-4.5": {
                "family": ModelFamily.CLAUDE,
                "local": False,
                "cost_input": 15.0,  # $15 per 1M input tokens
                "cost_output": 75.0,
                "latency": 2500,
                "reasoning": 0.95,
                "code": 0.93,
                "opsec": 0.6,
                "complexity": (5, 10)
            },
            "claude-3.5-sonnet": {
                "family": ModelFamily.CLAUDE,
                "local": False,
                "cost_input": 3.0,
                "cost_output": 15.0,
                "latency": 1500,
                "reasoning": 0.90,
                "code": 0.92,
                "opsec": 0.5,
                "complexity": (4, 10)
            },
            "gpt-4-turbo": {
                "family": ModelFamily.OPENAI,
                "local": False,
                "cost_input": 10.0,
                "cost_output": 30.0,
                "latency": 3000,
                "reasoning": 0.88,
                "code": 0.90,
                "opsec": 0.5,
                "complexity": (5, 10)
            },
            "gpt-4o": {
                "family": ModelFamily.OPENAI,
                "local": False,
                "cost_input": 5.0,
                "cost_output": 15.0,
                "latency": 2000,
                "reasoning": 0.85,
                "code": 0.88,
                "opsec": 0.5,
                "complexity": (4, 10)
            },
            "gemini-2.0-flash": {
                "family": ModelFamily.GEMINI,
                "local": False,
                "cost_input": 0.075,
                "cost_output": 0.3,
                "latency": 1200,
                "reasoning": 0.80,
                "code": 0.85,
                "opsec": 0.6,
                "complexity": (3, 9)
            },
            "gemma:7b": {
                "family": ModelFamily.GEMMA,
                "local": True,
                "cost_input": 0.0,
                "cost_output": 0.0,
                "latency": 800,
                "reasoning": 0.60,
                "code": 0.70,
                "opsec": 1.0,
                "complexity": (1, 7)
            },
            "qwen2.5-coder:7b": {
                "family": ModelFamily.QWEN,
                "local": True,
                "cost_input": 0.0,
                "cost_output": 0.0,
                "latency": 1200,
                "reasoning": 0.75,
                "code": 0.82,
                "opsec": 1.0,
                "complexity": (2, 8)
            }
        }

    async def discover_models(self) -> Dict[str, ModelMetrics]:
        """Discover available models: local via Ollama + cloud API keys"""

        print("🔍 Discovering available models...")

        # 1. Discover local Ollama models
        local_models = await self._discover_ollama_models()

        # 2. Verify cloud API keys
        cloud_models = await self._verify_cloud_apis()

        # 3. Register all models
        all_available = {}

        for model_id, config in self.model_configs.items():
            if config["local"]:
                # Check exact or prefix match against installed Ollama tags.
                canonical_id = model_id.lower()
                canonical_base = canonical_id.split(":")[0]
                normalized_local = [m.lower() for m in local_models]
                if (
                    canonical_id in normalized_local
                    or any(
                        m.split(":")[0] == canonical_base
                        or m.startswith(canonical_base)
                        for m in normalized_local
                    )
                ):
                    all_available[model_id] = self._create_model_metrics(model_id, config, True)
            else:
                # Check if cloud API is available
                family = config["family"].value
                if family in cloud_models:
                    all_available[model_id] = self._create_model_metrics(model_id, config, True)

        self.available_models = all_available
        print(f"✓ Discovered {len(all_available)} models")
        for model_id in all_available:
            metrics = all_available[model_id]
            opsec_label = "🔒 OPSEC" if metrics.opsec_score > 0.9 else "☁️  Cloud"
            print(f"  - {model_id} ({opsec_label})")

        return all_available

    async def _discover_ollama_models(self) -> List[str]:
        """Discover local Ollama models"""
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                # Parse ollama list output
                models = []
                for line in result.stdout.split('\n')[1:]:  # Skip header
                    if line.strip():
                        model_name = line.split()[0]
                        models.append(model_name)

                self.local_models_cache = models
                print(f"  ✓ Found {len(models)} local Ollama models")
                return models
        except Exception as e:
            print(f"  ⚠ Could not discover Ollama models: {e}")

        return []

    async def _verify_cloud_apis(self) -> List[str]:
        """Verify cloud API keys are available"""
        available = []

        from .secret_manager import get_secret_manager, SecretManagerError

        manager = None
        try:
            manager = get_secret_manager()
        except SecretManagerError:
            manager = None

        def _lookup(name: str) -> str | None:
            if manager:
                try:
                    return manager.get_optional(name)
                except SecretManagerError:
                    pass
            return None

        api_keys = {
            ModelFamily.CLAUDE: _lookup("ANTHROPIC_API_KEY"),
            ModelFamily.OPENAI: _lookup("OPENAI_API_KEY"),
            ModelFamily.GEMINI: _lookup("GOOGLE_API_KEY"),
        }

        for family, key in api_keys.items():
            if key:
                available.append(family.value)
                print(f"  ✓ {family.value.upper()} API key found")

        return available

    def _create_model_metrics(self, model_id: str, config: Dict, available: bool) -> ModelMetrics:
        """Create ModelMetrics from config"""
        return ModelMetrics(
            model_id=model_id,
            family=config["family"],
            local=config["local"],
            available=available,
            cost_per_1m_input=config["cost_input"],
            cost_per_1m_output=config["cost_output"],
            avg_latency_ms=config["latency"],
            reasoning_quality=config["reasoning"],
            code_quality=config["code"],
            opsec_score=config["opsec"],
            supported_complexity=config["complexity"]
        )

    async def analyze_task_complexity(self, task: TaskDefinition) -> int:
        """Analyze task to determine complexity (1-10)"""

        # If user provided estimate, validate it
        if task.complexity_estimate:
            return min(10, max(1, task.complexity_estimate))

        # Auto-analyze based on description and requirements
        complexity = 5  # Baseline

        # Adjust based on requirements
        if "reasoning" in task.required_capabilities:
            complexity += 2
        if "code_generation" in task.required_capabilities:
            complexity += 1
        if "long_context" in task.required_capabilities:
            complexity += 2
        if "novel" in task.description.lower():
            complexity += 2

        return min(10, complexity)

    async def bid_models(self, task: TaskDefinition, budget_cents: Optional[float] = None) -> List[ModelBid]:
        """Get bids from available models with optional budget filtering"""

        complexity = await self.analyze_task_complexity(task)
        bids = []

        # Use task budget if not explicitly provided
        if budget_cents is None:
            budget_cents = task.budget_cents

        for model_id, metrics in self.available_models.items():
            if not metrics.available:
                continue

            # Check if model supports this complexity
            min_complex, max_complex = metrics.supported_complexity
            if complexity < min_complex or complexity > max_complex:
                continue

            # Calculate suitability score
            suitability = self._calculate_suitability(task, metrics, complexity)

            if suitability < 0.3:  # Filter out unsuitable models
                continue

            # Calculate estimated cost
            estimated_cost = self._estimate_cost(
                metrics,
                task.estimated_tokens_input,
                task.estimated_tokens_output
            )

            # Budget-aware filtering: skip models that exceed budget
            if budget_cents is not None and estimated_cost > budget_cents:
                logger.debug(f"Skipping {model_id}: cost ${estimated_cost/100:.4f} exceeds budget ${budget_cents/100:.2f}")
                continue

            # Create bid
            bid = ModelBid(
                model_id=model_id,
                family=metrics.family,
                task_id=task.task_id,
                estimated_cost_cents=estimated_cost,
                estimated_latency_ms=metrics.avg_latency_ms,
                confidence_score=suitability,
                reasoning=self._generate_bid_reasoning(task, metrics, complexity)
            )

            bids.append(bid)

        # Sort by suitability score (highest first), then by cost (lowest first)
        # Prefer local models (cost=0) when suitability is similar
        bids.sort(key=lambda b: (-b.confidence_score, b.estimated_cost_cents))

        return bids

    def _calculate_suitability(self, task: TaskDefinition, metrics: ModelMetrics, complexity: int) -> float:
        """Calculate how suitable a model is for a task (0-1)"""

        score = 0.5  # Baseline

        # Complexity fit (best at center of range)
        min_c, max_c = metrics.supported_complexity
        mid_c = (min_c + max_c) / 2
        complexity_diff = abs(complexity - mid_c)
        complexity_fit = 1.0 - (complexity_diff / max_c)
        score += complexity_fit * 0.3

        # Capability fit
        if "reasoning" in task.required_capabilities:
            score += metrics.reasoning_quality * 0.2
        if "code_generation" in task.required_capabilities:
            score += metrics.code_quality * 0.2

        # OPSEC preference
        if task.security_sensitive:
            score += metrics.opsec_score * 0.2

        # Cost efficiency
        if task.budget_cents:
            estimated_cost = self._estimate_cost(
                metrics,
                task.estimated_tokens_input,
                task.estimated_tokens_output
            )
            if estimated_cost <= task.budget_cents:
                score += 0.1

        return min(1.0, score)

    def _estimate_cost(self, metrics: ModelMetrics, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost in cents"""
        input_cost = (input_tokens / 1_000_000) * metrics.cost_per_1m_input * 100
        output_cost = (output_tokens / 1_000_000) * metrics.cost_per_1m_output * 100
        return input_cost + output_cost

    def _generate_bid_reasoning(self, task: TaskDefinition, metrics: ModelMetrics, complexity: int) -> str:
        """Generate human-readable reasoning for the bid"""
        reasons = []

        if metrics.local:
            reasons.append("Local execution (OPSEC advantage)")

        min_c, max_c = metrics.supported_complexity
        if min_c <= complexity <= max_c:
            reasons.append(f"Optimal complexity range for {metrics.model_id}")

        if metrics.reasoning_quality > 0.8:
            reasons.append("Strong reasoning capability")

        if metrics.code_quality > 0.8:
            reasons.append("Strong code generation capability")

        return " | ".join(reasons)

    async def select_winner(
        self,
        task: TaskDefinition,
        bids: List[ModelBid],
        strategy: str = "balanced"
    ) -> TaskAssignment:
        """Select winning model based on strategy"""

        if not bids:
            raise ValueError(f"No suitable models available for task {task.task_id}")

        if strategy == "cheapest":
            winner = min(bids, key=lambda b: b.estimated_cost_cents)
        elif strategy == "fastest":
            winner = min(bids, key=lambda b: b.estimated_latency_ms)
        elif strategy == "balanced":
            # Balance cost, speed, and quality
            scores = []
            for bid in bids:
                cost_score = 1.0 - (bid.estimated_cost_cents / max(b.estimated_cost_cents for b in bids))
                speed_score = 1.0 - (bid.estimated_latency_ms / max(b.estimated_latency_ms for b in bids))
                quality_score = bid.confidence_score

                combined = (cost_score * 0.3) + (speed_score * 0.2) + (quality_score * 0.5)
                scores.append((bid, combined))

            winner = max(scores, key=lambda x: x[1])[0]
        else:
            winner = bids[0]  # Default to highest confidence

        # Select verification model (different family)
        verifier = self._select_verification_model(winner, task)

        local_fallback = next(
            (b for b in bids if self.available_models.get(b.model_id) and self.available_models[b.model_id].local),
            None,
        )
        decision = evaluate_confidence_policy(
            confidence_score=winner.confidence_score,
            security_sensitive=task.security_sensitive,
            has_local_fallback=local_fallback is not None,
        )
        if decision.action == "stop":
            raise ValueError(
                f"confidence policy stop: {decision.reason} ({winner.confidence_score:.2f} < {decision.threshold:.2f})"
            )
        if decision.action == "fallback_local" and local_fallback is not None:
            winner = local_fallback

        assignment = TaskAssignment(
            task_id=task.task_id,
            assigned_model=winner.model_id,
            assigned_family=winner.family,
            bid=winner,
            verification_model=verifier.model_id if verifier else None,
            verification_family=verifier.family if verifier else None,
            policy_action=decision.action,
            policy_reason=decision.reason,
        )

        emit_model_decision_event(
            {
                "location_id": "model_bidding.select_winner",
                "task_id": task.task_id,
                "strategy": strategy,
                "assigned_model": assignment.assigned_model,
                "assigned_family": assignment.assigned_family.value,
                "verification_model": assignment.verification_model,
                "confidence_score": round(winner.confidence_score, 6),
                "estimated_cost_cents": round(winner.estimated_cost_cents, 6),
                "estimated_latency_ms": round(winner.estimated_latency_ms, 6),
                "policy_action": assignment.policy_action,
                "policy_reason": assignment.policy_reason,
                "security_sensitive": bool(task.security_sensitive),
            }
        )

        self.task_history.append(assignment)
        return assignment

    def _select_verification_model(self, primary_bid: ModelBid, task: TaskDefinition) -> Optional[ModelBid]:
        """Select a different model family for verification"""

        # Get models from different families
        other_family_models = [
            m for m in self.available_models.values()
            if m.family != primary_bid.family and m.available
        ]

        if not other_family_models:
            return None

        # Prefer local models for verification (OPSEC)
        local_models = [m for m in other_family_models if m.local]
        if local_models:
            verifier = max(local_models, key=lambda m: m.reasoning_quality)
        else:
            verifier = max(other_family_models, key=lambda m: m.reasoning_quality)

        return ModelBid(
            model_id=verifier.model_id,
            family=verifier.family,
            task_id=task.task_id,
            estimated_cost_cents=0,  # Verification cost is secondary
            estimated_latency_ms=verifier.avg_latency_ms,
            confidence_score=verifier.reasoning_quality,
            reasoning="Cross-model verification"
        )

    def get_model_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics for all models"""

        summary = {}

        for model_id, metrics in self.available_models.items():
            tasks_using = len([t for t in self.task_history if t.assigned_model == model_id])

            if tasks_using == 0:
                continue

            actual_costs = [t.actual_cost_cents for t in self.task_history if t.assigned_model == model_id and t.actual_cost_cents]
            actual_latencies = [t.actual_latency_ms for t in self.task_history if t.assigned_model == model_id and t.actual_latency_ms]

            summary[model_id] = {
                "family": metrics.family.value,
                "local": metrics.local,
                "tasks_assigned": tasks_using,
                "avg_actual_cost": sum(actual_costs) / len(actual_costs) if actual_costs else 0,
                "avg_actual_latency": sum(actual_latencies) / len(actual_latencies) if actual_latencies else 0,
                "opsec_score": metrics.opsec_score,
                "reasoning_quality": metrics.reasoning_quality,
                "code_quality": metrics.code_quality
            }

        return summary

    async def auto_bid_and_select(
        self,
        task: TaskDefinition,
        strategy: str = "balanced"
    ) -> TaskAssignment:
        """Complete auto-bidding workflow"""

        # Analyze complexity
        complexity = await self.analyze_task_complexity(task)
        print(f"📊 Task '{task.name}' complexity: {complexity}/10")

        # Get bids
        bids = await self.bid_models(task)

        if not bids:
            raise ValueError(f"No suitable models for task: {task.name}")

        print(f"💰 Received {len(bids)} bids:")
        for bid in bids[:3]:  # Show top 3
            cost_label = f"${bid.estimated_cost_cents / 100:.4f}" if bid.estimated_cost_cents > 0 else "Free"
            print(f"  - {bid.model_id}: {cost_label}, {bid.confidence_score:.0%} suitable")

        # Select winner
        assignment = await self.select_winner(task, bids, strategy)

        print(f"✅ Assigned to: {assignment.assigned_model}")
        if assignment.verification_model:
            print(f"🔍 Verification by: {assignment.verification_model}")

        return assignment

    def to_dict(self) -> Dict[str, Any]:
        """Export state for persistence"""
        return {
            "available_models": {k: vars(v) for k, v in self.available_models.items()},
            "task_history": [vars(t) for t in self.task_history],
            "total_tasks": len(self.task_history),
            "total_cost_cents": sum(t.actual_cost_cents or 0 for t in self.task_history)
        }


# Global instance
model_factory = None


def initialize_model_factory() -> UniversalModelFactory:
    """Initialize the model bidding factory"""
    global model_factory

    model_factory = UniversalModelFactory()
    print("✓ Model bidding factory initialized")

    return model_factory
