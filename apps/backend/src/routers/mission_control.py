"""
Mission Control API
===================
API for mission lifecycle management, including creation, execution,
stopping, and replay of missions.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole

from apps.backend.src.core.praison_mission_runtime import get_mission_runtime, MissionStatus
from apps.backend.src.core.graph_visualization import export_graph_structure
from apps.backend.src.core.praison_topology import (
    ClusterSpec,
    EdgeSpec,
    MissionGraphSpec,
    NodeSpec,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/missions", tags=["mission-control"])


# -- Request/Response Schemas -------------------------------------------------

class MissionCreateRequest(BaseModel):
    workflow_id: str
    program_id: str
    mission_name: str = ""
    execution_mode: str = "live"
    run_config: dict[str, Any] = Field(default_factory=dict)
    graph_spec: dict[str, Any] | None = None


class MissionResponse(BaseModel):
    mission_id: str
    workflow_id: str
    program_id: str
    state: str
    execution_mode: str
    phase: str
    active_node: str
    progress: float
    error: str | None = None


def _as_object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_str(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    return str(value)


def _build_graph_spec(payload: dict[str, Any], default_workflow_id: str, default_program_id: str, mission_name: str) -> MissionGraphSpec:
    graph_payload = _as_object(payload)
    nodes_raw = graph_payload.get("nodes")
    edges_raw = graph_payload.get("edges")
    clusters_raw = graph_payload.get("clusters")

    node_entries: list[tuple[str, dict[str, Any]]] = []
    if isinstance(nodes_raw, dict):
        for node_id, row in nodes_raw.items():
            row_obj = _as_object(row)
            node_entries.append((_as_str(row_obj.get("node_id"), _as_str(node_id)).strip(), row_obj))
    else:
        for row in _as_list(nodes_raw):
            row_obj = _as_object(row)
            node_id = _as_str(row_obj.get("node_id")).strip()
            if node_id:
                node_entries.append((node_id, row_obj))

    if not node_entries:
        raise ValueError("graph_spec.nodes must contain at least one node")

    nodes: dict[str, NodeSpec] = {}
    for node_id, row in node_entries:
        if not node_id:
            continue
        if node_id in nodes:
            raise ValueError(f"graph_spec contains duplicate node_id: {node_id}")
        metadata = row.get("metadata")
        nodes[node_id] = NodeSpec(
            node_id=node_id,
            agent_id=_as_str(row.get("agent_id"), node_id),
            node_type=_as_str(row.get("node_type"), "agent"),
            cluster_id=_as_str(row.get("cluster_id"), ""),
            agent_class=_as_str(row.get("agent_class"), "specialist"),
            risk_profile=_as_str(row.get("risk_profile"), "standard"),
            review_policy=_as_str(row.get("review_policy"), "standard"),
            memory_scope=_as_str(row.get("memory_scope"), "session"),
            allowed_tools=[_as_str(item).strip() for item in _as_list(row.get("allowed_tools")) if _as_str(item).strip()],
            system_prompt=_as_str(row.get("system_prompt"), ""),
            litellm_model=_as_str(row.get("litellm_model"), ""),
            interrupt_before=bool(row.get("interrupt_before", False)),
            interrupt_after=bool(row.get("interrupt_after", False)),
            is_entry=bool(row.get("is_entry", False)),
            is_exit=bool(row.get("is_exit", False)),
            metadata=_as_object(metadata),
        )

    edges: list[EdgeSpec] = []
    for row in _as_list(edges_raw):
        row_obj = _as_object(row)
        source = _as_str(row_obj.get("source")).strip()
        target = _as_str(row_obj.get("target")).strip()
        if not source or not target:
            continue
        if source not in nodes or target not in nodes:
            raise ValueError(f"graph_spec edge references unknown node: {source} -> {target}")
        edges.append(
            EdgeSpec(
                edge_id=_as_str(row_obj.get("edge_id"), "").strip() or EdgeSpec().edge_id,
                source=source,
                target=target,
                condition=_as_str(row_obj.get("condition"), "always"),
                artifact_type=_as_str(row_obj.get("artifact_type"), ""),
                label=_as_str(row_obj.get("label"), ""),
            )
        )

    if not edges:
        raise ValueError("graph_spec.edges must contain at least one edge")

    clusters: dict[str, ClusterSpec] = {}
    cluster_rows: list[dict[str, Any]] = []
    if isinstance(clusters_raw, dict):
        for cluster_id, row in clusters_raw.items():
            row_obj = _as_object(row)
            row_obj.setdefault("cluster_id", _as_str(cluster_id))
            cluster_rows.append(row_obj)
    else:
        cluster_rows = [_as_object(row) for row in _as_list(clusters_raw)]

    for row in cluster_rows:
        cluster_id = _as_str(row.get("cluster_id")).strip()
        if not cluster_id:
            continue
        if cluster_id in clusters:
            raise ValueError(f"graph_spec contains duplicate cluster_id: {cluster_id}")
        specialist_ids = [_as_str(item).strip() for item in _as_list(row.get("specialist_ids")) if _as_str(item).strip()]
        coordinator_id = _as_str(row.get("coordinator_id"), "").strip()
        entry_node = _as_str(row.get("entry_node"), "").strip()
        exit_node = _as_str(row.get("exit_node"), "").strip()
        for node_id in [coordinator_id, entry_node, exit_node, *specialist_ids]:
            if node_id and node_id not in nodes:
                raise ValueError(f"graph_spec cluster references unknown node: {node_id}")
        clusters[cluster_id] = ClusterSpec(
            cluster_id=cluster_id,
            cluster_name=_as_str(row.get("cluster_name"), cluster_id),
            phase=_as_str(row.get("phase"), ""),
            coordinator_id=coordinator_id,
            specialist_ids=specialist_ids,
            entry_node=entry_node,
            exit_node=exit_node,
            parallel_execution=bool(row.get("parallel_execution", True)),
        )

    workflow_id = _as_str(graph_payload.get("workflow_id"), default_workflow_id)
    program_id = _as_str(graph_payload.get("program_id"), default_program_id)
    graph_name = _as_str(graph_payload.get("mission_name"), mission_name or f"graph_{workflow_id}")
    graph_id = _as_str(graph_payload.get("graph_id"), "").strip()

    graph_spec = MissionGraphSpec(
        graph_id=graph_id or MissionGraphSpec().graph_id,
        mission_name=graph_name,
        workflow_id=workflow_id,
        program_id=program_id,
        nodes=nodes,
        edges=edges,
        clusters=clusters,
        entry_node=_as_str(graph_payload.get("entry_node"), "").strip(),
        exit_node=_as_str(graph_payload.get("exit_node"), "").strip(),
        checkpointer_scope=_as_str(graph_payload.get("checkpointer_scope"), "workflow"),
    )

    if not graph_spec.entry_node:
        for node in nodes.values():
            if node.is_entry:
                graph_spec.entry_node = node.node_id
                break
    if not graph_spec.exit_node:
        for node in nodes.values():
            if node.is_exit:
                graph_spec.exit_node = node.node_id
                break
    if not graph_spec.entry_node:
        graph_spec.entry_node = next(iter(nodes.keys()))
    if not graph_spec.exit_node:
        graph_spec.exit_node = next(reversed(nodes.keys()))

    return graph_spec


# -- Endpoints ----------------------------------------------------------------

@router.post("/", response_model=MissionResponse)
async def create_mission(
    payload: MissionCreateRequest,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Create a new mission."""
    runtime = get_mission_runtime()
    try:
        graph_spec = _build_graph_spec(
            payload.graph_spec,
            default_workflow_id=payload.workflow_id,
            default_program_id=payload.program_id,
            mission_name=payload.mission_name,
        ) if payload.graph_spec else None
        handle = runtime.create_mission(
            tenant_id=current_user.tenant_id,
            workflow_id=payload.workflow_id,
            program_id=payload.program_id,
            mission_name=payload.mission_name,
            execution_mode=payload.execution_mode,
            graph_spec=graph_spec,
        )
        return MissionResponse(
            mission_id=handle.mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            state="created",
            execution_mode=handle.execution_mode,
            phase="",
            active_node="",
            progress=0.0,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Failed to create mission: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/", response_model=list[MissionResponse])
async def list_missions(
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """List all mission statuses for the current tenant."""
    runtime = get_mission_runtime()
    statuses = runtime.list_missions(tenant_id=current_user.tenant_id)
    return [
        MissionResponse(
            mission_id=s.mission_id,
            workflow_id=s.workflow_id,
            program_id=s.program_id,
            state=s.state,
            execution_mode=s.execution_mode,
            phase=s.phase,
            active_node=s.active_node,
            progress=s.progress,
            error=s.error or None,
        )
        for s in statuses
    ]


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission_status(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get status of a specific mission for the current tenant."""
    runtime = get_mission_runtime()
    try:
        s = runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        return MissionResponse(
            mission_id=s.mission_id,
            workflow_id=s.workflow_id,
            program_id=s.program_id,
            state=s.state,
            execution_mode=s.execution_mode,
            phase=s.phase,
            active_node=s.active_node,
            progress=s.progress,
            error=s.error or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{mission_id}/graph")
async def get_mission_graph(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Export mission graph structure for visualization."""
    result = export_graph_structure(mission_id, tenant_id=current_user.tenant_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{mission_id}/start")
async def start_mission(
    mission_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Start mission execution in the background."""
    runtime = get_mission_runtime()
    try:
        # Check if already running
        status = runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        if status.state == "running":
            return {"status": "already running"}
        
        # Start in background as LangGraph might block
        background_tasks.add_task(runtime.start_mission, mission_id, tenant_id=current_user.tenant_id)
        return {"status": "started", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/stop")
async def stop_mission(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Stop/pause a running mission."""
    runtime = get_mission_runtime()
    try:
        runtime.stop_mission(mission_id, tenant_id=current_user.tenant_id)
        return {"status": "stopping", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{mission_id}/replay")
async def replay_mission(
    mission_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Replay a historical mission from checkpoints."""
    runtime = get_mission_runtime()
    try:
        # Replay implementation (mocked for now as we need real replay logic)
        # Assuming we can resume with replay mode
        background_tasks.add_task(runtime.resume_mission, mission_id, tenant_id=current_user.tenant_id)
        return {"status": "replay_started", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
