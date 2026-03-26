"""
Agent Zero Integration Router
K1 exposes MCP servers and workflows to Agent Zero
Agent Zero is the primary user communication interface

Enhanced with:
- WebSocket chat endpoint for real-time streaming
- Chat history persistence
- HiL approval integration
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
import json
import asyncio
import uuid
from datetime import datetime, timezone
from collections import defaultdict

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

# Import HiL approval workflow
try:
    from apps.backend.src.core.approval_workflow import HiLApprovalWorkflow
    hil_workflow = None  # Set during startup
except ImportError:
    HiLApprovalWorkflow = None
    hil_workflow = None


router = APIRouter(prefix="/api/v1/agent-zero", tags=["agent-zero"])


# ==================== CHAT SESSION MANAGEMENT ====================

class ChatMessage(BaseModel):
    """Chat message model."""
    id: str
    role: str  # "user", "assistant", "system", "tool"
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    approval_required: Optional[bool] = None
    approval_id: Optional[str] = None


class ChatSession:
    """Manages a chat session with history."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: List[ChatMessage] = []
        self.created_at = datetime.now(timezone.utc)
        self.last_activity = datetime.now(timezone.utc)
        self.pending_approvals: Dict[str, Dict] = {}
        self.context: Dict[str, Any] = {}

    def add_message(self, role: str, content: str, **kwargs) -> ChatMessage:
        """Add a message to the session."""
        message = ChatMessage(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
        self.messages.append(message)
        self.last_activity = datetime.now(timezone.utc)
        return message

    def get_history(self, limit: int = 50) -> List[Dict]:
        """Get message history."""
        return [m.model_dump() for m in self.messages[-limit:]]

    def to_dict(self) -> Dict:
        """Convert session to dictionary."""
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "message_count": len(self.messages),
            "pending_approvals": len(self.pending_approvals)
        }


# Global chat session storage
_chat_sessions: Dict[str, ChatSession] = {}
_active_connections: Dict[str, List[WebSocket]] = defaultdict(list)


def get_or_create_session(session_id: str) -> ChatSession:
    """Get existing session or create new one."""
    if session_id not in _chat_sessions:
        _chat_sessions[session_id] = ChatSession(session_id)
    return _chat_sessions[session_id]


def set_hil_workflow(workflow):
    """Set HiL workflow reference (called during startup)."""
    global hil_workflow
    hil_workflow = workflow


class ChatConnectionManager:
    """Manages WebSocket connections for chat."""

    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a connection."""
        await websocket.accept()
        self.active_connections[session_id].append(websocket)

    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a connection."""
        if websocket in self.active_connections[session_id]:
            self.active_connections[session_id].remove(websocket)

    async def send_message(self, session_id: str, message: Dict):
        """Send message to all connections in a session."""
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_json(message)
            except Exception:
                pass

    async def broadcast_to_session(self, session_id: str, event_type: str, data: Dict):
        """Broadcast an event to all session connections."""
        message = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        await self.send_message(session_id, message)


chat_manager = ChatConnectionManager()


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
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


# ==================== CHAT ENDPOINTS ====================

class SendMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    content: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None


class ApprovalResponse(BaseModel):
    """Response model for approval decisions."""
    approval_id: str
    decision: str  # "approved" or "rejected"
    reason: Optional[str] = None


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, session_id: Optional[str] = None):
    """WebSocket endpoint for real-time chat streaming.

    Protocol:
    - Client sends: {"type": "message", "content": "...", "context": {...}}
    - Server streams: {"type": "token", "content": "..."}
    - Server sends: {"type": "message_complete", "message": {...}}
    - Server sends: {"type": "tool_call", "tool": "...", "params": {...}}
    - Server sends: {"type": "approval_required", "approval_id": "...", "details": {...}}
    - Client sends: {"type": "approval_response", "approval_id": "...", "decision": "approved|rejected"}
    """
    # Create or get session
    if not session_id:
        session_id = str(uuid.uuid4())

    session = get_or_create_session(session_id)
    await chat_manager.connect(websocket, session_id)

    try:
        # Send session info
        await websocket.send_json({
            "type": "session_started",
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })

        while True:
            # Receive message from client
            data = await websocket.receive_text()

            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                continue

            msg_type = message_data.get("type", "message")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if msg_type == "message":
                # Process user message
                content = message_data.get("content", "")
                context = message_data.get("context", {})

                # Add user message to history
                user_msg = session.add_message("user", content)
                await websocket.send_json({
                    "type": "message_received",
                    "message_id": user_msg.id
                })

                # Process with Agent Zero
                await _process_chat_message(
                    websocket, session, content, context
                )

            elif msg_type == "approval_response":
                # Handle approval decision
                approval_id = message_data.get("approval_id")
                decision = message_data.get("decision")
                reason = message_data.get("reason", "")

                await _handle_approval_response(
                    websocket, session, approval_id, decision, reason
                )

            elif msg_type == "get_history":
                # Return chat history
                limit = message_data.get("limit", 50)
                await websocket.send_json({
                    "type": "history",
                    "messages": session.get_history(limit)
                })

    except WebSocketDisconnect:
        chat_manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"WebSocket chat error: {str(e)}")
        chat_manager.disconnect(websocket, session_id)


async def _process_chat_message(
    websocket: WebSocket,
    session: ChatSession,
    content: str,
    context: Dict[str, Any]
):
    """Process a chat message and stream response."""
    try:
        # Check if this requires tool execution
        tool_call = _detect_tool_call(content)

        if tool_call:
            # Notify about tool call
            await websocket.send_json({
                "type": "tool_call",
                "tool": tool_call["tool"],
                "params": tool_call["params"],
                "description": tool_call.get("description", "Executing tool...")
            })

            # Check if approval is needed
            if tool_call.get("tier", 0) >= 2:
                approval_id = str(uuid.uuid4())
                session.pending_approvals[approval_id] = {
                    "tool_call": tool_call,
                    "context": context,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }

                await websocket.send_json({
                    "type": "approval_required",
                    "approval_id": approval_id,
                    "operation": tool_call["tool"],
                    "tier": tool_call["tier"],
                    "details": tool_call,
                    "message": f"This operation requires approval: {tool_call['description']}"
                })

                # Add system message about approval
                session.add_message(
                    "system",
                    f"Approval required for {tool_call['tool']}",
                    approval_required=True,
                    approval_id=approval_id
                )
                return

            # Execute tool if no approval needed
            result = await _execute_tool_call(tool_call)
            await websocket.send_json({
                "type": "tool_result",
                "tool": tool_call["tool"],
                "result": result
            })

        # Generate response using Agent Zero bridge
        if agent_zero_bridge:
            # Stream response tokens
            response_content = ""

            try:
                result = await agent_zero_bridge.handle_agent_zero_query(
                    content, {**context, **session.context}
                )

                if isinstance(result, dict):
                    response_content = result.get("response", result.get("message", str(result)))
                else:
                    response_content = str(result)

                # Simulate streaming (would be actual streaming with real LLM)
                words = response_content.split()
                for i, word in enumerate(words):
                    await websocket.send_json({
                        "type": "token",
                        "content": word + (" " if i < len(words) - 1 else "")
                    })
                    await asyncio.sleep(0.02)  # Small delay for streaming effect

            except Exception as e:
                response_content = f"I encountered an error processing your request: {str(e)}"

        else:
            # Fallback response when Agent Zero not available
            response_content = _generate_fallback_response(content, context)

            # Stream response
            words = response_content.split()
            for i, word in enumerate(words):
                await websocket.send_json({
                    "type": "token",
                    "content": word + (" " if i < len(words) - 1 else "")
                })
                await asyncio.sleep(0.02)

        # Add assistant message to history
        assistant_msg = session.add_message("assistant", response_content)

        # Send completion
        await websocket.send_json({
            "type": "message_complete",
            "message": assistant_msg.model_dump()
        })

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Error processing message: {str(e)}"
        })


async def _handle_approval_response(
    websocket: WebSocket,
    session: ChatSession,
    approval_id: str,
    decision: str,
    reason: str
):
    """Handle an approval decision from the user."""
    if approval_id not in session.pending_approvals:
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown approval ID: {approval_id}"
        })
        return

    approval_data = session.pending_approvals.pop(approval_id)
    tool_call = approval_data["tool_call"]

    if decision == "approved":
        # Record approval with HiL workflow if available
        if hil_workflow:
            try:
                await hil_workflow.record_approval(
                    approval_id=approval_id,
                    operation=tool_call["tool"],
                    decision="APPROVED",
                    reason=reason
                )
            except Exception as e:
                print(f"Failed to record approval: {e}")

        # Execute the tool
        await websocket.send_json({
            "type": "approval_granted",
            "approval_id": approval_id,
            "message": "Approval granted, executing operation..."
        })

        result = await _execute_tool_call(tool_call)

        await websocket.send_json({
            "type": "tool_result",
            "tool": tool_call["tool"],
            "result": result,
            "approval_id": approval_id
        })

        session.add_message(
            "system",
            f"Operation {tool_call['tool']} completed after approval",
            metadata={"result": result}
        )

    else:
        # Record rejection
        if hil_workflow:
            try:
                await hil_workflow.record_approval(
                    approval_id=approval_id,
                    operation=tool_call["tool"],
                    decision="REJECTED",
                    reason=reason
                )
            except Exception as e:
                print(f"Failed to record rejection: {e}")

        await websocket.send_json({
            "type": "approval_rejected",
            "approval_id": approval_id,
            "reason": reason,
            "message": f"Operation rejected: {reason}"
        })

        session.add_message(
            "system",
            f"Operation {tool_call['tool']} rejected: {reason}"
        )


def _detect_tool_call(content: str) -> Optional[Dict[str, Any]]:
    """Detect if the message requires a tool call."""
    content_lower = content.lower()

    # Tool detection patterns
    tool_patterns = [
        {
            "keywords": ["hunt", "scan for vulnerabilities", "find vulnerabilities"],
            "tool": "vulnerability_hunt",
            "tier": 1,
            "description": "Start vulnerability hunting workflow"
        },
        {
            "keywords": ["exploit", "attack", "pwn"],
            "tool": "exploit_execution",
            "tier": 3,
            "description": "Execute exploitation (requires approval)"
        },
        {
            "keywords": ["nuclei scan", "run nuclei"],
            "tool": "nuclei_scan",
            "tier": 1,
            "description": "Run Nuclei vulnerability scanner"
        },
        {
            "keywords": ["sqlmap", "sql injection test"],
            "tool": "sqlmap_scan",
            "tier": 2,
            "description": "Run SQL injection testing (requires approval)"
        },
        {
            "keywords": ["xss", "cross-site scripting"],
            "tool": "xss_scan",
            "tier": 1,
            "description": "Scan for XSS vulnerabilities"
        },
        {
            "keywords": ["recon", "reconnaissance", "gather info"],
            "tool": "reconnaissance",
            "tier": 0,
            "description": "Perform reconnaissance"
        },
    ]

    for pattern in tool_patterns:
        if any(kw in content_lower for kw in pattern["keywords"]):
            # Extract target from content (simplified)
            target = _extract_target(content)
            return {
                "tool": pattern["tool"],
                "tier": pattern["tier"],
                "description": pattern["description"],
                "params": {"target": target, "query": content}
            }

    return None


def _extract_target(content: str) -> Optional[str]:
    """Extract target domain/IP from content."""
    import re

    # Domain pattern
    domain_match = re.search(r'([a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}', content)
    if domain_match:
        return domain_match.group()

    # IP pattern
    ip_match = re.search(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', content)
    if ip_match:
        return ip_match.group()

    return None


async def _execute_tool_call(tool_call: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a tool call."""
    tool = tool_call["tool"]
    params = tool_call.get("params", {})

    try:
        if tool == "vulnerability_hunt" and workflow_orchestrator:
            target = params.get("target", "unknown")
            workflow_id = workflow_orchestrator.create_hunt_workflow(
                target=target,
                scope={}
            )
            return {
                "status": "started",
                "workflow_id": workflow_id,
                "target": target
            }

        elif tool == "reconnaissance":
            return {
                "status": "completed",
                "message": f"Reconnaissance initiated for {params.get('target', 'target')}",
                "data": {"subdomains": [], "ports": [], "services": []}
            }

        elif tool == "nuclei_scan":
            return {
                "status": "started",
                "message": f"Nuclei scan started for {params.get('target', 'target')}",
                "scan_id": str(uuid.uuid4())
            }

        else:
            return {
                "status": "completed",
                "message": f"Tool {tool} executed with params: {params}"
            }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


def _generate_fallback_response(content: str, context: Dict[str, Any]) -> str:
    """Generate a fallback response when Agent Zero is not available."""
    content_lower = content.lower()

    if "help" in content_lower:
        return """I can help you with vulnerability hunting and security operations. Here are some things you can ask me:

- "Hunt for vulnerabilities in example.com"
- "Run a nuclei scan on target.com"
- "Show me the current findings"
- "What's the status of my agents?"
- "Start reconnaissance on 10.0.0.1"

What would you like to do?"""

    elif "status" in content_lower:
        return "I'm operational and ready to assist with your security operations. You can ask me to start hunts, run scans, or manage your findings."

    elif any(word in content_lower for word in ["hello", "hi", "hey"]):
        return "Hello! I'm K1, your security operations assistant. How can I help you today?"

    else:
        return f"I received your message: '{content}'. I'm currently operating in fallback mode. Please try rephrasing your request or ask for 'help' to see available commands."


# ==================== REST CHAT ENDPOINTS ====================

@router.post("/chat/message")
async def send_chat_message(request: SendMessageRequest):
    """Send a chat message via REST API (non-streaming).

    For streaming responses, use the WebSocket endpoint.
    """
    session_id = request.session_id or str(uuid.uuid4())
    session = get_or_create_session(session_id)

    # Add user message
    user_msg = session.add_message("user", request.content)

    # Check for tool calls
    tool_call = _detect_tool_call(request.content)
    tool_result = None

    if tool_call:
        if tool_call.get("tier", 0) >= 2:
            # Requires approval
            approval_id = str(uuid.uuid4())
            session.pending_approvals[approval_id] = {
                "tool_call": tool_call,
                "context": request.context or {},
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            return {
                "session_id": session_id,
                "message_id": user_msg.id,
                "approval_required": True,
                "approval_id": approval_id,
                "operation": tool_call["tool"],
                "tier": tool_call["tier"],
                "message": f"This operation requires approval: {tool_call['description']}"
            }

        # Execute tool
        tool_result = await _execute_tool_call(tool_call)

    # Generate response
    if agent_zero_bridge:
        try:
            result = await agent_zero_bridge.handle_agent_zero_query(
                request.content, request.context or {}
            )
            response_content = result.get("response", str(result)) if isinstance(result, dict) else str(result)
        except Exception as e:
            response_content = f"Error: {str(e)}"
    else:
        response_content = _generate_fallback_response(request.content, request.context or {})

    # Add assistant message
    assistant_msg = session.add_message(
        "assistant",
        response_content,
        tool_calls=[tool_call] if tool_call else None
    )

    return {
        "session_id": session_id,
        "message_id": assistant_msg.id,
        "response": response_content,
        "tool_result": tool_result,
        "timestamp": assistant_msg.timestamp
    }


@router.get("/chat/history")
async def get_chat_history(
    session_id: str = Query(..., description="Chat session ID"),
    limit: int = Query(50, le=200, description="Maximum messages to return")
):
    """Get chat history for a session."""
    if session_id not in _chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = _chat_sessions[session_id]
    return {
        "session_id": session_id,
        "session_info": session.to_dict(),
        "messages": session.get_history(limit)
    }


@router.get("/chat/sessions")
async def list_chat_sessions(
    limit: int = Query(20, le=100)
):
    """List all chat sessions."""
    sessions = sorted(
        _chat_sessions.values(),
        key=lambda s: s.last_activity,
        reverse=True
    )[:limit]

    return {
        "total": len(_chat_sessions),
        "sessions": [s.to_dict() for s in sessions]
    }


@router.delete("/chat/sessions/{session_id}")
async def delete_chat_session(session_id: str):
    """Delete a chat session."""
    if session_id not in _chat_sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    del _chat_sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


@router.post("/chat/approval")
async def handle_chat_approval(request: ApprovalResponse):
    """Handle an approval decision via REST API."""
    # Find session with this approval
    for session in _chat_sessions.values():
        if request.approval_id in session.pending_approvals:
            approval_data = session.pending_approvals.pop(request.approval_id)
            tool_call = approval_data["tool_call"]

            if request.decision == "approved":
                # Record and execute
                if hil_workflow:
                    try:
                        await hil_workflow.record_approval(
                            approval_id=request.approval_id,
                            operation=tool_call["tool"],
                            decision="APPROVED",
                            reason=request.reason or ""
                        )
                    except Exception:
                        pass

                result = await _execute_tool_call(tool_call)

                session.add_message(
                    "system",
                    f"Operation {tool_call['tool']} completed after approval",
                    metadata={"result": result}
                )

                # Broadcast to WebSocket connections
                await chat_manager.broadcast_to_session(
                    session.session_id,
                    "approval_granted",
                    {"approval_id": request.approval_id, "result": result}
                )

                return {
                    "status": "approved",
                    "approval_id": request.approval_id,
                    "result": result
                }
            else:
                # Record rejection
                if hil_workflow:
                    try:
                        await hil_workflow.record_approval(
                            approval_id=request.approval_id,
                            operation=tool_call["tool"],
                            decision="REJECTED",
                            reason=request.reason or ""
                        )
                    except Exception:
                        pass

                session.add_message(
                    "system",
                    f"Operation {tool_call['tool']} rejected: {request.reason}"
                )

                await chat_manager.broadcast_to_session(
                    session.session_id,
                    "approval_rejected",
                    {"approval_id": request.approval_id, "reason": request.reason}
                )

                return {
                    "status": "rejected",
                    "approval_id": request.approval_id,
                    "reason": request.reason
                }

    raise HTTPException(status_code=404, detail="Approval not found")
