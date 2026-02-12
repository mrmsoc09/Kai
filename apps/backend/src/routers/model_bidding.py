"""
Model Bidding API Router
Exposes intelligent model selection and task routing endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
import asyncio

router = APIRouter(prefix="/api/models", tags=["model-bidding"])

# Module-level cache for systems
_model_factory = None
_orchestration_graph = None


def set_systems(model_factory, orchestration_graph):
    """Set system references from main.py"""
    global _model_factory, _orchestration_graph
    _model_factory = model_factory
    _orchestration_graph = orchestration_graph


def get_systems():
    """Get system references with fallback import"""
    global _model_factory, _orchestration_graph

    if _model_factory is None:
        try:
            from apps.backend.src.core.model_bidding import model_factory
            _model_factory = model_factory
        except:
            raise HTTPException(status_code=500, detail="Model factory not initialized")

    if _orchestration_graph is None:
        try:
            from apps.backend.src.core.orchestration_graph import orchestration_graph
            _orchestration_graph = orchestration_graph
        except:
            raise HTTPException(status_code=500, detail="Orchestration graph not initialized")

    return _model_factory, _orchestration_graph


# ==================== Request/Response Models ====================

class TaskDefinitionRequest(BaseModel):
    """Request for model bidding on a task"""
    task_id: str
    task_type: str  # reconnaissance, analysis, exploitation, validation, reporting
    description: str
    requires_reasoning: bool = False
    opsec_critical: bool = True
    target_domain: str
    data_required: Optional[Dict[str, Any]] = None


class ModelBidResponse(BaseModel):
    """Model bid response"""
    model_id: str
    model_name: str
    estimated_cost: float
    estimated_latency_seconds: float
    confidence_score: float
    suitability_score: float
    reasoning: str


class TaskAssignmentResponse(BaseModel):
    """Model assignment result"""
    task_id: str
    assigned_model: str
    backup_model: str
    verification_model: str
    total_cost_estimate: float
    strategy: str
    reasoning: str


class DiscoveryResponse(BaseModel):
    """Model discovery results"""
    local_models: List[Dict[str, Any]]
    cloud_models: List[Dict[str, Any]]
    available_providers: List[str]
    timestamp: str


# ==================== Endpoints ====================

@router.post("/discover", response_model=DiscoveryResponse)
async def discover_available_models():
    """Discover all available models (local Ollama + cloud APIs)"""
    factory, _ = get_systems()

    try:
        discovery = await asyncio.to_thread(factory.discover_models)
        return discovery
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.post("/bid", response_model=List[ModelBidResponse])
async def get_model_bids(task: TaskDefinitionRequest):
    """Get bids from available models for a task"""
    factory, _ = get_systems()

    try:
        # Import TaskDefinition from model_bidding
        from apps.backend.src.core.model_bidding import TaskDefinition

        task_def = TaskDefinition(
            task_id=task.task_id,
            task_type=task.task_type,
            description=task.description,
            requires_reasoning=task.requires_reasoning,
            opsec_critical=task.opsec_critical,
            target_domain=task.target_domain
        )

        # Analyze complexity
        await asyncio.to_thread(factory.analyze_task_complexity, task_def)

        # Get bids
        bids = await asyncio.to_thread(factory.bid_models, task_def)

        # Convert to response format
        responses = []
        for bid in bids:
            responses.append(ModelBidResponse(
                model_id=bid.model_id,
                model_name=bid.model_name,
                estimated_cost=bid.cost_estimate,
                estimated_latency_seconds=bid.latency_estimate,
                confidence_score=bid.confidence_score,
                suitability_score=bid.suitability_score,
                reasoning=bid.reasoning
            ))

        return sorted(responses, key=lambda x: x.suitability_score, reverse=True)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bidding failed: {str(e)}")


@router.post("/assign", response_model=TaskAssignmentResponse)
async def assign_model_for_task(
    task: TaskDefinitionRequest,
    strategy: str = "balanced"
):
    """Assign optimal model for task with strategy (cheapest, fastest, balanced, quality)"""
    factory, _ = get_systems()

    try:
        from apps.backend.src.core.model_bidding import TaskDefinition

        task_def = TaskDefinition(
            task_id=task.task_id,
            task_type=task.task_type,
            description=task.description,
            requires_reasoning=task.requires_reasoning,
            opsec_critical=task.opsec_critical,
            target_domain=task.target_domain
        )

        # Complete workflow: analyze → bid → select
        assignment = await asyncio.to_thread(
            factory.auto_bid_and_select,
            task_def,
            strategy
        )

        return TaskAssignmentResponse(
            task_id=assignment.task_id,
            assigned_model=assignment.winning_model.model_name,
            backup_model=assignment.backup_model.model_name if assignment.backup_model else "None",
            verification_model=assignment.verification_model.model_name if assignment.verification_model else "None",
            total_cost_estimate=assignment.winning_bid.cost_estimate,
            strategy=strategy,
            reasoning=assignment.selection_reasoning
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Assignment failed: {str(e)}")


@router.get("/config")
async def get_model_configuration():
    """Get current model configuration and complexity routing"""
    factory, _ = get_systems()

    try:
        return {
            "models": [
                {
                    "model_id": m.model_id,
                    "name": m.model_name,
                    "provider": m.provider,
                    "max_complexity": m.max_complexity,
                    "min_complexity": m.min_complexity,
                    "capabilities": list(m.capabilities)
                }
                for m in factory.models.values()
            ],
            "complexity_routing": {
                "local_models": "Complexity 1-5 (OPSEC priority)",
                "balanced": "Complexity 5-8 (Cost+Quality balance)",
                "cloud_advanced": "Complexity 8-10 (Maximum reasoning)"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config retrieval failed: {str(e)}")


@router.get("/performance/{model_id}")
async def get_model_performance_metrics(model_id: str):
    """Get performance metrics for specific model"""
    factory, _ = get_systems()

    try:
        model = factory.models.get(model_id)
        if not model:
            raise HTTPException(status_code=404, detail=f"Model {model_id} not found")

        return {
            "model_id": model_id,
            "model_name": model.model_name,
            "metrics": model.metrics.to_dict() if hasattr(model.metrics, 'to_dict') else {
                "latency_p50_ms": model.metrics.latency_p50_ms,
                "latency_p99_ms": model.metrics.latency_p99_ms,
                "cost_per_1k_tokens": model.metrics.cost_per_1k_tokens,
                "reasoning_quality_score": model.metrics.reasoning_quality_score,
                "code_quality_score": model.metrics.code_quality_score,
                "opsec_score": model.metrics.opsec_score,
                "success_rate_percent": model.metrics.success_rate_percent
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metrics retrieval failed: {str(e)}")
