"""
/api/v1/orchestration — GeminiOrchestrator REST + WebSocket + SSE endpoints.

WebSocket auth pattern (identical to realtime.py):
  token query param → decode_access_token → close(1008) on failure.

Five-tier routing is handled entirely server-side.  Clients see ModelTier
and QuotaStatus in responses but do not control tier selection directly.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from ..core.auth import decode_access_token
from ..core.gemini_orchestrator import get_gemini_orchestrator

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration_v1"])


# ---------------------------------------------------------------------------
# REST — health / agents / quota / tier / workflows
# ---------------------------------------------------------------------------


@router.get("/health")
async def health() -> dict[str, Any]:
    """Return provider-chain health and quota summary from GeminiOrchestrator."""
    return get_gemini_orchestrator().health()


@router.get("/agents")
async def agents() -> list[dict[str, Any]]:
    """Return provider chain represented as agent nodes (for frontend agent panel)."""
    return get_gemini_orchestrator().agent_list()


@router.get("/quota")
async def quota() -> dict[str, Any]:
    """Return QuotaStatus for all API tiers.

    Used by the frontend quota indicator in UnifiedOrchestrationDashboard.
    Color-coding thresholds:
      Flash > 100 RPD: green   | 50-100: yellow  | < 50: orange (spillover active)
      Pro   < 20 RPD:  red     (buffer zone — hard-gated until next reset)
    """
    return get_gemini_orchestrator().quota_status_dict()


@router.get("/tier")
async def active_tier() -> dict[str, Any]:
    """Return the currently active model tier."""
    status = get_gemini_orchestrator().quota.status()
    return {
        "active_tier": status.active_tier.value,
        "emergency_fallback_active": status.emergency_fallback_active,
        "flash_lite_spillover_active": status.flash_lite_spillover_active,
        "pro_restricted": status.pro_restricted,
    }


@router.get("/workflows")
async def workflows(limit: int = Query(default=30, ge=1, le=200)) -> dict[str, Any]:
    """List recent hunt workflows (stub — wired to workflow store in next session)."""
    return {"workflows": [], "total": 0, "limit": limit}


@router.post("/workflows/hunt")
async def create_hunt_workflow(target: str = Query(...)) -> dict[str, Any]:
    """Enqueue a new hunt workflow for *target* (stub — wired to workflow engine)."""
    return {
        "workflow_id": f"hunt-{int(datetime.now(timezone.utc).timestamp())}",
        "target": target,
        "status": "queued",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# REST — task dispatch
# ---------------------------------------------------------------------------


@router.post("/dispatch")
async def dispatch(payload: dict[str, Any]) -> dict[str, Any]:
    """Dispatch an OrchestrationTask through the 5-tier routing stack.

    Expected payload (all fields optional except instruction):
      {
        "task_id":         str,   // auto-generated if omitted
        "instruction":     str,   // REQUIRED — natural language task
        "phase":           str,
        "context":         dict,
        "tools_available": list[str],
        "complexity_hint": "low" | "medium" | "high",
        "timeout_seconds": int,
        "priority":        int,
        "session_id":      str
      }

    Response: OrchestrationResult dict
    """
    instruction = payload.get("instruction", "")
    if not instruction:
        return {
            "task_id": payload.get("task_id", str(uuid.uuid4())),
            "status": "failed",
            "error": "instruction is required",
        }

    orch = get_gemini_orchestrator()
    result = await orch.execute(
        instruction,
        context=payload.get("context"),
        tools=payload.get("tools_available"),
        complexity_hint=payload.get("complexity_hint"),
        timeout_seconds=int(payload.get("timeout_seconds", 120)),
        session_id=payload.get("session_id") or payload.get("task_id"),
    )
    return result


# ---------------------------------------------------------------------------
# SSE — task stream
# ---------------------------------------------------------------------------


@router.get("/stream/{task_id}")
async def stream_session(task_id: str) -> StreamingResponse:
    """Server-Sent Events stream for a running task.

    Clients receive periodic status updates until the task completes.
    Format: text/event-stream.
    """

    async def event_generator():
        # In the current stub implementation, tasks complete synchronously.
        # This SSE endpoint is wired for future async task tracking.
        yield f"data: {json.dumps({'task_id': task_id, 'status': 'streaming', 'message': 'connected'})}\n\n"
        await asyncio.sleep(0)
        yield f"data: {json.dumps({'task_id': task_id, 'status': 'complete'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# REST — LLM usage / plugin info (legacy endpoints consumed by frontend)
# ---------------------------------------------------------------------------


@router.get("/llm/usage")
async def llm_usage() -> dict[str, Any]:
    """Return session LLM usage statistics."""
    orch = get_gemini_orchestrator()
    return {
        "primary": orch._primary,
        "stats": orch.factory.get_usage_stats(),
        "quota": orch.quota_status_dict(),
    }


@router.get("/llm/providers")
async def llm_providers() -> dict[str, Any]:
    """Return registered provider info (consumed by dashboard LLM stats panel)."""
    orch = get_gemini_orchestrator()
    return {
        "primary": orch._primary,
        "stats": orch.factory.get_usage_stats(),
    }


@router.get("/plugin/info")
async def plugin_info() -> dict[str, Any]:
    return {"name": "GeminiOrchestrator", "version": "5-tier", "status": "active"}


# ---------------------------------------------------------------------------
# REST — chat (HTTP fallback; prefer WS /ws/chat for streaming)
# ---------------------------------------------------------------------------


@router.post("/chat/message")
async def chat_message(payload: dict[str, Any]) -> dict[str, Any]:
    """Send a chat message to the primary LLM tier.  Non-streaming POST."""
    content = payload.get("content", "")
    if not content:
        return {"error": "content required"}
    orch = get_gemini_orchestrator()
    result = await orch.execute(
        content,
        session_id=payload.get("session_id"),
    )
    return {
        "content": result.get("output", ""),
        "model": result.get("model_used"),
        "tier": result.get("tier_used"),
        "session_id": payload.get("session_id"),
    }


@router.get("/chat/history")
async def chat_history(session_id: str = Query(default=""), limit: int = Query(default=80)) -> dict[str, Any]:
    """Chat history stub — wired to session store in a future session."""
    return {"messages": [], "session_id": session_id, "limit": limit}


@router.post("/chat/approval")
async def chat_approval(payload: dict[str, Any]) -> dict[str, Any]:
    """Approval response stub for HIL gates."""
    return {"status": "recorded", "approval_id": payload.get("approval_id")}


# ---------------------------------------------------------------------------
# REST — natural language commands
# ---------------------------------------------------------------------------


@router.post("/commands/natural-language")
async def natural_language_command(payload: dict[str, Any]) -> dict[str, Any]:
    """Execute a natural language command through the orchestrator."""
    query = payload.get("query", "")
    if not query:
        return {"error": "query required"}
    orch = get_gemini_orchestrator()
    result = await orch.execute(query, context=payload.get("context"))
    return {
        "status": result.get("status"),
        "output": result.get("output"),
        "tier_used": result.get("tier_used"),
    }


# ---------------------------------------------------------------------------
# WebSockets
# ---------------------------------------------------------------------------


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Streaming chat relay backed by the primary LLM provider.

    Auth: Bearer token in ?token= query param.  Closes 1008 on auth failure.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        user = decode_access_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    await websocket.send_json({"type": "connected", "user_id": user.id})

    orchestrator = get_gemini_orchestrator()

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "invalid_json"})
                continue

            if payload.get("type") == "ping" or raw == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            content = payload.get("content", "")
            if not content:
                await websocket.send_json({"type": "error", "message": "empty_content"})
                continue

            try:
                result = await orchestrator.execute(
                    content,
                    context=payload.get("context"),
                    session_id=payload.get("session_id"),
                )
                await websocket.send_json(
                    {
                        "type": "message",
                        "content": result.get("output", ""),
                        "model": result.get("model_used"),
                        "tier": result.get("tier_used"),
                        "duration_ms": result.get("duration_ms"),
                    }
                )
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})

    except WebSocketDisconnect:
        pass


@router.websocket("/ws/agents")
async def ws_agents(websocket: WebSocket) -> None:
    """Push provider/agent status updates every 5 seconds.

    Auth: Bearer token in ?token= query param.  Closes 1008 on auth failure.
    Payload also includes QuotaStatus for the dashboard quota indicator.
    """
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return

    try:
        decode_access_token(token)
    except Exception:
        await websocket.close(code=1008)
        return

    await websocket.accept()

    try:
        while True:
            orchestrator = get_gemini_orchestrator()
            status = orchestrator.health()
            status["agents"] = orchestrator.agent_list()
            status["quota"] = orchestrator.quota_status_dict()
            await websocket.send_json({"type": "agent_update", "status": status})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass
