"""
Agent Zero Integration Router
K1 exposes MCP servers and workflows to Agent Zero
Agent Zero is the primary user communication interface
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import json
from datetime import datetime

# Import K1 systems
try:
    from apps.backend.src.core.agent_zero_integration import agent_zero_bridge, AgentZeroCommand
    from apps.backend.src.core.agent_a2a import agent_registry, a2a_bus, workflow_orchestrator
    from apps.backend.src.core.mcp_base import mcp_manager
    from apps.backend.src.core.llm_providers import llm_factory
except ImportError:
    agent_zero_bridge = None
    agent_registry = None
    a2a_bus = None
    workflow_orchestrator = None
    mcp_manager = None
    llm_factory = None


router = APIRouter(prefix="/api/v1/agent-zero", tags=["agent-zero"])


# ==================== PLUGIN MANAGEMENT ====================

@router.get("/plugin/info")
async def get_plugin_info():
    """Get K1 plugin information for Agent Zero"""
    if not agent_zero_bridge:
        raise HTTPException(status_code=503, detail="Agent Zero integration not available")

    return {
        "plugin_id": agent_zero_bridge.plugin_id,
        "plugin_info": agent_zero_bridge.get_plugin_info(),
        "registered": agent_zero_bridge.is_registered
    }


@router.post("/plugin/register")
async def register_with_agent_zero():
    """Manually register K1 with Agent Zero"""
    if not agent_zero_bridge:
        raise HTTPException(status_code=503, detail="Agent Zero integration not available")

    success = await agent_zero_bridge.register_with_agent_zero()

    return {
        "status": "success" if success else "failed",
        "message": "K1 registered with Agent Zero" if success else "Registration failed"
    }


# ==================== WORKFLOWS ====================

@router.post("/workflows/hunt")
async def create_hunt_workflow(
    target: str = Query(..., description="Target domain or IP"),
    scope: Optional[Dict[str, Any]] = None
):
    """Create a vulnerability hunting workflow via Agent Zero"""
    if not workflow_orchestrator:
        raise HTTPException(status_code=503, detail="Workflow orchestrator not available")

    workflow_id = workflow_orchestrator.create_hunt_workflow(
        target=target,
        scope=scope or {}
    )

    return {
        "status": "created",
        "workflow_id": workflow_id,
        "target": target,
        "message": f"Hunting workflow created for {target}"
    }


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Get workflow status"""
    if not workflow_orchestrator:
        raise HTTPException(status_code=503, detail="Workflow orchestrator not available")

    workflow = workflow_orchestrator.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    return workflow


@router.get("/workflows")
async def list_workflows(
    status: Optional[str] = None,
    limit: int = Query(50, le=100)
):
    """List workflows"""
    if not workflow_orchestrator:
        raise HTTPException(status_code=503, detail="Workflow orchestrator not available")

    workflows = workflow_orchestrator.list_workflows()

    if status:
        workflows = [w for w in workflows if w.get("status") == status]

    return {
        "total": len(workflows),
        "workflows": workflows[:limit]
    }


@router.post("/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str):
    """Cancel a running workflow"""
    if not workflow_orchestrator:
        raise HTTPException(status_code=503, detail="Workflow orchestrator not available")

    workflow = workflow_orchestrator.get_workflow(workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    workflow["status"] = "cancelled"

    return {
        "status": "cancelled",
        "workflow_id": workflow_id
    }


# ==================== AGENT STATUS ====================

@router.get("/agents")
async def get_agent_status():
    """Get status of all K1 agents"""
    if not agent_zero_bridge:
        raise HTTPException(status_code=503, detail="Agent Zero integration not available")

    status = await agent_zero_bridge.get_agent_status()
    return status


@router.get("/agents/{agent_id}")
async def get_agent_detail(agent_id: str):
    """Get details for specific agent"""
    if not agent_registry:
        raise HTTPException(status_code=503, detail="Agent registry not available")

    agent = agent_registry.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent.to_dict()


# ==================== MCP SERVERS ====================

@router.get("/mcp/registry")
async def get_mcp_registry():
    """Get MCP server registry"""
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP manager not available")

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "servers": mcp_manager.get_registry(),
        "stats": mcp_manager.get_stats()
    }


@router.get("/mcp/servers/{server_id}")
async def get_mcp_server(server_id: str):
    """Get MCP server details"""
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP manager not available")

    server = mcp_manager.get_server(server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    return server.get_stats()


@router.post("/mcp/tools/{server_id}/{tool_name}/execute")
async def execute_mcp_tool(
    server_id: str,
    tool_name: str,
    parameters: Dict[str, Any]
):
    """Execute a tool on an MCP server"""
    if not mcp_manager:
        raise HTTPException(status_code=503, detail="MCP manager not available")

    response = await mcp_manager.execute_tool(server_id, tool_name, parameters)

    return response


# ==================== LLM PROVIDER MANAGEMENT ====================

@router.get("/llm/providers")
async def get_llm_providers():
    """Get available LLM providers"""
    if not llm_factory:
        raise HTTPException(status_code=503, detail="LLM system not available")

    return {
        "primary": llm_factory.primary_provider.value if llm_factory.primary_provider else None,
        "fallback_chain": [p.value for p in llm_factory.fallback_chain],
        "available_providers": list(llm_factory.providers.keys()),
        "stats": llm_factory.get_usage_stats()
    }


@router.get("/llm/usage")
async def get_llm_usage():
    """Get LLM usage statistics"""
    if not llm_factory:
        raise HTTPException(status_code=503, detail="LLM system not available")

    return llm_factory.get_usage_stats()


# ==================== MESSAGES & COMMUNICATION ====================

@router.post("/messages/send")
async def send_agent_message(
    sender_id: str,
    receiver_id: str,
    message_type: str,
    content: Dict[str, Any]
):
    """Send a message between agents"""
    if not a2a_bus:
        raise HTTPException(status_code=503, detail="A2A bus not available")

    from apps.backend.src.core.agent_a2a import A2AMessage, MessageType

    message = A2AMessage(
        sender_id=sender_id,
        receiver_id=receiver_id,
        message_type=MessageType(message_type),
        content=content
    )

    a2a_bus.publish(message)

    return {
        "status": "sent",
        "message_id": message.message_id
    }


@router.get("/messages/{agent_id}")
async def get_agent_messages(agent_id: str, limit: int = Query(50, le=1000)):
    """Get message history for an agent"""
    if not a2a_bus:
        raise HTTPException(status_code=503, detail="A2A bus not available")

    messages = a2a_bus.get_messages(agent_id, limit)

    return {
        "agent_id": agent_id,
        "total_messages": len(messages),
        "messages": [json.loads(m.to_json()) for m in messages]
    }


@router.get("/messages/stats")
async def get_messaging_stats():
    """Get message bus statistics"""
    if not a2a_bus:
        raise HTTPException(status_code=503, detail="A2A bus not available")

    return a2a_bus.get_stats()


# ==================== NATURAL LANGUAGE COMMANDS ====================

@router.post("/commands/natural-language")
async def execute_natural_language_command(
    query: str,
    context: Optional[Dict[str, Any]] = None
):
    """Execute natural language command from Agent Zero

    Examples:
    - "hunt for XSS in example.com"
    - "analyze this finding for chains"
    - "validate evidence quality"
    """
    if not agent_zero_bridge:
        raise HTTPException(status_code=503, detail="Agent Zero integration not available")

    result = await agent_zero_bridge.handle_agent_zero_query(query, context or {})

    return result


# ==================== FINDINGS SYNC ====================

@router.post("/findings/sync")
async def sync_findings_to_agent_zero(findings: List[Dict]):
    """Sync findings from K1 to Agent Zero"""
    if not agent_zero_bridge:
        raise HTTPException(status_code=503, detail="Agent Zero integration not available")

    from apps.backend.src.core.agent_zero_integration import K1Finding

    # Convert dicts to K1Finding objects
    finding_objects = [
        K1Finding(
            title=f.get("title"),
            description=f.get("description"),
            target=f.get("target"),
            severity=f.get("severity", "medium"),
            vulnerability_type=f.get("vulnerability_type"),
            confidence=f.get("confidence", 0.0),
            evidence=f.get("evidence", [])
        )
        for f in findings
    ]

    success = await agent_zero_bridge.sync_findings_to_agent_zero(finding_objects)

    return {
        "status": "synced" if success else "failed",
        "findings_count": len(finding_objects)
    }


# ==================== HEALTH & STATUS ====================

@router.get("/health")
async def agent_zero_health():
    """K1 health check for Agent Zero"""
    health_status = {
        "timestamp": datetime.utcnow().isoformat(),
        "k1_status": "healthy",
        "systems": {}
    }

    # Check LLM system
    health_status["systems"]["llm"] = {
        "status": "operational" if llm_factory else "unavailable",
        "primary_provider": llm_factory.primary_provider.value if llm_factory and llm_factory.primary_provider else None
    }

    # Check MCP system
    health_status["systems"]["mcp"] = {
        "status": "operational" if mcp_manager else "unavailable",
        "servers": len(mcp_manager.servers) if mcp_manager else 0
    }

    # Check A2A system
    health_status["systems"]["a2a"] = {
        "status": "operational" if agent_registry else "unavailable",
        "agents": len(agent_registry.agents) if agent_registry else 0
    }

    # Check Agent Zero bridge
    health_status["systems"]["agent_zero"] = {
        "status": "operational" if agent_zero_bridge else "unavailable",
        "registered": agent_zero_bridge.is_registered if agent_zero_bridge else False
    }

    return health_status


# ==================== WEBSOCKET (Real-time updates) ====================

@router.websocket("/ws/workflows/{workflow_id}")
async def websocket_workflow_updates(websocket: WebSocket, workflow_id: str):
    """WebSocket connection for real-time workflow updates

    Sends:
    - {"type": "status_update", "step": 1, "status": "in_progress"}
    - {"type": "finding_discovered", "finding": {...}}
    - {"type": "workflow_complete", "result": {...}}
    """
    await websocket.accept()

    try:
        while True:
            # Wait for client message or send updates
            data = await websocket.receive_text()

            if data == "ping":
                await websocket.send_json({"type": "pong"})

    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        await websocket.close()


@router.websocket("/ws/agents")
async def websocket_agent_updates(websocket: WebSocket):
    """WebSocket connection for real-time agent status updates"""
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_text()

            if data == "ping":
                # Send current agent status
                status = await agent_zero_bridge.get_agent_status()
                await websocket.send_json({
                    "type": "agent_update",
                    "status": status
                })

    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        await websocket.close()
