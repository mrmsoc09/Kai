"""
Agent Zero Integration Bridge
K1 as Agent Zero Plugin with bi-directional communication
Agent Zero is the primary user interface and communication hub
"""

import httpx
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import asyncio


class PluginCapability(str, Enum):
    """K1 capabilities exposed to Agent Zero"""
    VULNERABILITY_DISCOVERY = "vulnerability_discovery"
    OSINT = "osint"
    EVIDENCE_VALIDATION = "evidence_validation"
    CHAIN_ANALYSIS = "chain_analysis"
    REPORT_GENERATION = "report_generation"
    ATTACK_PLANNING = "attack_planning"


@dataclass
class PluginInfo:
    """Information about K1 as Agent Zero plugin"""
    name: str = "Kaison K1"
    version: str = "7.0"
    description: str = "Autonomous OSINT and vulnerability discovery platform"
    author: str = "Kaison"
    capabilities: List[PluginCapability] = None
    endpoints: Dict[str, str] = None
    mcp_servers: List[str] = None
    branding: Dict[str, str] = None
    status: str = "active"

    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = list(PluginCapability)

        if self.endpoints is None:
            self.endpoints = {
                "api_base": "http://localhost:8000/api/v1",
                "websocket": "ws://localhost:8000/ws",
                "health": "http://localhost:8000/api/v1/state/health",
                "workflows": "http://localhost:8000/api/v1/agent-zero/workflows",
                "findings": "http://localhost:8000/api/v1/findings"
            }

        if self.mcp_servers is None:
            self.mcp_servers = [
                "k1-validator",
                "k1-analysis",
                "k1-osint",
                "k1-graph"
            ]

        if self.branding is None:
            self.branding = {
                "name": "Kaison K1",
                "tagline": "Enterprise OSINT & Vulnerability Discovery",
                "color": "#0066CC",
                "icon": "vulnerability"
            }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "capabilities": [c.value for c in self.capabilities],
            "endpoints": self.endpoints,
            "mcp_servers": self.mcp_servers,
            "branding": self.branding,
            "status": self.status
        }


@dataclass
class AgentZeroCommand:
    """Command from Agent Zero to K1"""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_type: str = ""  # hunt, analyze, validate, etc.
    target: str = ""
    scope: Dict[str, Any] = None
    parameters: Dict[str, Any] = None
    user_context: Dict[str, Any] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type,
            "target": self.target,
            "scope": self.scope or {},
            "parameters": self.parameters or {},
            "user_context": self.user_context or {},
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class K1Finding:
    """Finding discovered by K1, sent to Agent Zero"""
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""
    description: str = ""
    target: str = ""
    severity: str = "medium"
    vulnerability_type: str = ""
    confidence: float = 0.0
    evidence: List[str] = None
    mcp_server: str = ""  # Which MCP server discovered it
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_workflow_id: str = ""

    def __post_init__(self):
        if self.evidence is None:
            self.evidence = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "title": self.title,
            "description": self.description,
            "target": self.target,
            "severity": self.severity,
            "vulnerability_type": self.vulnerability_type,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "mcp_server": self.mcp_server,
            "timestamp": self.timestamp.isoformat(),
            "source_workflow_id": self.source_workflow_id
        }


class AgentZeroBridge:
    """Bridge K1 agents to Agent Zero infrastructure"""

    def __init__(
        self,
        agent_zero_url: str = "http://localhost:8001",
        k1_api_url: str = "http://localhost:8000/api/v1"
    ):
        self.agent_zero_url = agent_zero_url
        self.k1_api_url = k1_api_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.is_registered = False
        self.plugin_id = str(uuid.uuid4())
        self.plugin_info = PluginInfo()
        self.command_queue: asyncio.Queue = asyncio.Queue()
        self.finding_queue: asyncio.Queue = asyncio.Queue()
        self.workflow_cache: Dict[str, Dict] = {}

    async def register_with_agent_zero(self) -> bool:
        """Register K1 as Agent Zero plugin"""
        try:
            response = await self.client.post(
                f"{self.agent_zero_url}/api/v1/plugins/register",
                json={
                    "plugin_id": self.plugin_id,
                    "plugin_info": self.plugin_info.to_dict()
                }
            )

            if response.status_code in [200, 201]:
                self.is_registered = True
                print("✓ K1 registered with Agent Zero")
                return True
            else:
                print(f"✗ Agent Zero registration failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"✗ Failed to register with Agent Zero: {str(e)}")
            return False

    async def execute_agent_zero_command(
        self,
        command: AgentZeroCommand
    ) -> Dict[str, Any]:
        """Execute a command from Agent Zero"""
        # Queue the command
        await self.command_queue.put(command)

        # Return queued response
        return {
            "status": "queued",
            "command_id": command.command_id,
            "message": f"K1 hunt workflow started for {command.target}"
        }

    async def sync_findings_to_agent_zero(self, findings: List[K1Finding]) -> bool:
        """Sync K1 findings to Agent Zero"""
        try:
            response = await self.client.post(
                f"{self.agent_zero_url}/api/v1/findings/ingest",
                json={
                    "source": "k1",
                    "plugin_id": self.plugin_id,
                    "findings": [f.to_dict() for f in findings],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )

            return response.status_code in [200, 201]

        except Exception as e:
            print(f"Failed to sync findings: {str(e)}")
            return False

    async def get_mcp_registry(self) -> Dict[str, Any]:
        """Get K1's MCP server registry for Agent Zero"""
        # This will be populated by actual MCP servers
        return {
            "plugin_id": self.plugin_id,
            "mcp_servers": self.plugin_info.mcp_servers,
            "servers_online": len(self.plugin_info.mcp_servers),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def coordinate_workflow(
        self,
        workflow_type: str,
        target: str,
        scope: Dict[str, Any],
        agent_zero_user_id: str = None
    ) -> Dict[str, Any]:
        """Coordinate K1 workflow with Agent Zero"""
        workflow_id = str(uuid.uuid4())

        workflow_def = {
            "workflow_id": workflow_id,
            "type": workflow_type,
            "target": target,
            "scope": scope,
            "initiated_by": agent_zero_user_id or "agent_zero",
            "created_at": datetime.utcnow().isoformat(),
            "status": "created",
            "k1_api_endpoint": f"{self.k1_api_url}/workflows/{workflow_id}",
            "websocket_url": f"ws://localhost:8000/ws/workflows/{workflow_id}"
        }

        # Store workflow
        self.workflow_cache[workflow_id] = workflow_def

        # Send to Agent Zero
        try:
            response = await self.client.post(
                f"{self.agent_zero_url}/api/v1/workflows/coordinate",
                json=workflow_def
            )

            if response.status_code in [200, 201]:
                return {
                    "status": "success",
                    "workflow_id": workflow_id,
                    "message": "K1 workflow coordinated with Agent Zero"
                }
            else:
                return {
                    "status": "error",
                    "workflow_id": workflow_id,
                    "message": f"Agent Zero coordination failed: {response.status_code}"
                }

        except Exception as e:
            return {
                "status": "error",
                "workflow_id": workflow_id,
                "message": f"Coordination error: {str(e)}"
            }

    async def handle_agent_zero_query(
        self,
        query: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Handle natural language query from Agent Zero"""
        # This will be processed by the intent parser
        return {
            "query": query,
            "processing": True,
            "status": "Parsing user intent and creating K1 workflow"
        }

    async def stream_agent_updates(self) -> str:
        """Stream real-time agent updates to Agent Zero"""
        # This will be used for WebSocket connections
        pass

    async def get_agent_status(self) -> Dict[str, Any]:
        """Get current status of all K1 agents"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "k1_status": "online",
            "agents": {
                "total": 6,
                "working": 2,
                "idle": 4,
                "agents": [
                    {"name": "Recon Scout", "status": "working"},
                    {"name": "Evidence Validator", "status": "idle"},
                    {"name": "Deep Analyzer", "status": "working"},
                    {"name": "Attack Planner", "status": "idle"},
                    {"name": "Report Generator", "status": "idle"},
                    {"name": "Orchestrator", "status": "idle"}
                ]
            },
            "mcp_servers": {
                "total": 4,
                "online": 4,
                "servers": self.plugin_info.mcp_servers
            }
        }

    async def health_check(self) -> bool:
        """Health check for Agent Zero"""
        try:
            response = await self.client.get(
                f"{self.k1_api_url}/state/health"
            )
            return response.status_code == 200
        except:
            return False

    def get_plugin_info(self) -> Dict[str, Any]:
        """Return plugin info for Agent Zero"""
        return self.plugin_info.to_dict()


class AgentZeroCommandProcessor:
    """Process commands from Agent Zero"""

    def __init__(self, bridge: AgentZeroBridge, orchestrator):
        self.bridge = bridge
        self.orchestrator = orchestrator
        self.is_running = False

    async def start(self):
        """Start processing Agent Zero commands"""
        self.is_running = True
        print("✓ Agent Zero command processor started")

        while self.is_running:
            try:
                # Get next command from queue
                command = await asyncio.wait_for(
                    self.bridge.command_queue.get(),
                    timeout=1.0
                )

                # Process based on command type
                if command.command_type == "hunt":
                    await self._process_hunt_command(command)
                elif command.command_type == "analyze":
                    await self._process_analyze_command(command)
                else:
                    print(f"Unknown command type: {command.command_type}")

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Error processing command: {str(e)}")

    async def _process_hunt_command(self, command: AgentZeroCommand):
        """Process vulnerability hunting command from Agent Zero"""
        print(f"Processing hunt command for {command.target}")

        # Create K1 workflow
        workflow_id = self.orchestrator.create_hunt_workflow(
            target=command.target,
            scope=command.scope or {}
        )

        print(f"Created K1 workflow: {workflow_id}")

    async def _process_analyze_command(self, command: AgentZeroCommand):
        """Process analysis command from Agent Zero"""
        print(f"Processing analysis command: {command.command_type}")

    async def stop(self):
        """Stop command processor"""
        self.is_running = False
        print("✓ Agent Zero command processor stopped")


# Global instances
agent_zero_bridge = None


def initialize_agent_zero_integration(
    agent_zero_url: str = "http://localhost:8001",
    k1_api_url: str = "http://localhost:8000/api/v1"
) -> AgentZeroBridge:
    """Initialize Agent Zero integration"""
    global agent_zero_bridge

    agent_zero_bridge = AgentZeroBridge(agent_zero_url, k1_api_url)
    print("✓ Agent Zero bridge initialized")

    return agent_zero_bridge
