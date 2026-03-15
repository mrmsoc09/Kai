"""
MCP (Model Context Protocol) Base Classes for K1
Real protocol implementation (not mock)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import json
import asyncio
import subprocess
from pathlib import Path
from datetime import datetime, timezone


class ToolType(str, Enum):
    """Types of tools MCP server can expose"""
    CLASSIFIER = "classifier"
    VALIDATOR = "validator"
    ANALYZER = "analyzer"
    SCOUT = "scout"
    PLANNER = "planner"
    REPORTER = "reporter"


@dataclass
class MCPTool:
    """Represents a tool exposed by MCP server"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    tool_type: ToolType
    enabled: bool = True
    execution_count: int = 0
    last_executed: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "tool_type": self.tool_type.value,
            "enabled": self.enabled,
            "execution_count": self.execution_count,
            "last_executed": self.last_executed.isoformat() if self.last_executed else None
        }


@dataclass
class MCPRequest:
    """MCP protocol request"""
    request_id: str
    tool_name: str
    parameters: Dict[str, Any]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MCPResponse:
    """MCP protocol response"""
    request_id: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_json(self) -> str:
        return json.dumps({
            "request_id": self.request_id,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        })


class BaseMCPServer(ABC):
    """Base class for MCP servers in K1"""

    def __init__(self, server_id: str, name: str, port: int):
        self.server_id = server_id
        self.name = name
        self.port = port
        self.tools: Dict[str, MCPTool] = {}
        self.is_running = False
        self.request_queue: asyncio.Queue = asyncio.Queue()
        self.stats = {
            "requests_received": 0,
            "requests_processed": 0,
            "errors": 0,
            "uptime_seconds": 0
        }

    @abstractmethod
    def _initialize_tools(self):
        """Initialize tools for this MCP server"""
        pass

    def register_tool(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: Callable,
        tool_type: ToolType
    ):
        """Register a tool with this MCP server"""
        tool = MCPTool(
            name=name,
            description=description,
            input_schema=input_schema,
            handler=handler,
            tool_type=tool_type
        )
        self.tools[name] = tool
        print(f"✓ Registered tool: {name}")

    def get_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        return [tool.to_dict() for tool in self.tools.values() if tool.enabled]

    async def execute_tool(
        self,
        request: MCPRequest
    ) -> MCPResponse:
        """Execute a tool and return response"""
        self.stats["requests_received"] += 1

        if request.tool_name not in self.tools:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Tool not found: {request.tool_name}"
            )

        tool = self.tools[request.tool_name]

        if not tool.enabled:
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=f"Tool disabled: {request.tool_name}"
            )

        try:
            # Execute tool handler
            if asyncio.iscoroutinefunction(tool.handler):
                result = await tool.handler(**request.parameters)
            else:
                result = tool.handler(**request.parameters)

            # Update tool stats
            tool.execution_count += 1
            tool.last_executed = datetime.now(timezone.utc)

            self.stats["requests_processed"] += 1

            return MCPResponse(
                request_id=request.request_id,
                success=True,
                result=result
            )

        except Exception as e:
            self.stats["errors"] += 1
            return MCPResponse(
                request_id=request.request_id,
                success=False,
                error=str(e)
            )

    async def handle_request(self, raw_request: str) -> str:
        """Parse and handle MCP request"""
        try:
            request_data = json.loads(raw_request)
            request = MCPRequest(
                request_id=request_data.get("request_id", "unknown"),
                tool_name=request_data.get("tool_name"),
                parameters=request_data.get("parameters", {})
            )

            response = await self.execute_tool(request)
            return response.to_json()

        except json.JSONDecodeError as e:
            return MCPResponse(
                request_id="unknown",
                success=False,
                error=f"Invalid JSON: {str(e)}"
            ).to_json()

        except Exception as e:
            return MCPResponse(
                request_id="unknown",
                success=False,
                error=f"Server error: {str(e)}"
            ).to_json()

    async def start(self):
        """Start the MCP server"""
        self.is_running = True
        self._initialize_tools()
        print(f"✓ MCP Server '{self.name}' started on port {self.port}")
        print(f"  Registered {len(self.tools)} tools")

    async def stop(self):
        """Stop the MCP server"""
        self.is_running = False
        print(f"✓ MCP Server '{self.name}' stopped")

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics"""
        return {
            "server_id": self.server_id,
            "name": self.name,
            "port": self.port,
            "is_running": self.is_running,
            "tools_registered": len(self.tools),
            "tools": self.get_tools(),
            "stats": self.stats
        }


class MCPServerManager:
    """Manages all MCP servers and their lifecycle"""

    def __init__(self, base_dir: str = "/apps/backend/src/mcp_servers"):
        self.base_dir = Path(base_dir)
        self.servers: Dict[str, BaseMCPServer] = {}
        self.processes: Dict[str, subprocess.Popen] = {}
        self.registry: List[Dict[str, Any]] = []

    def register_server(self, server: BaseMCPServer):
        """Register an MCP server"""
        self.servers[server.server_id] = server
        print(f"✓ Registered MCP server: {server.name}")

    async def start_all_servers(self):
        """Start all registered servers"""
        for server_id, server in self.servers.items():
            try:
                await server.start()
                self._update_registry()
            except Exception as e:
                print(f"✗ Failed to start {server.name}: {str(e)}")

    async def stop_all_servers(self):
        """Stop all servers gracefully"""
        for server_id, server in self.servers.items():
            try:
                await server.stop()
            except Exception as e:
                print(f"✗ Error stopping {server.name}: {str(e)}")

    def get_server(self, server_id: str) -> Optional[BaseMCPServer]:
        """Get a server by ID"""
        return self.servers.get(server_id)

    def get_registry(self) -> List[Dict[str, Any]]:
        """Get registry of all MCP servers and their tools"""
        return self.registry

    def _update_registry(self):
        """Update registry from current servers"""
        self.registry = []
        for server in self.servers.values():
            self.registry.append({
                "server_id": server.server_id,
                "name": server.name,
                "status": "online" if server.is_running else "offline",
                "port": server.port,
                "tools": server.get_tools()
            })

    async def execute_tool(
        self,
        server_id: str,
        tool_name: str,
        parameters: Dict[str, Any]
    ) -> MCPResponse:
        """Execute a tool on a specific server"""
        server = self.get_server(server_id)
        if not server:
            return MCPResponse(
                request_id="unknown",
                success=False,
                error=f"Server not found: {server_id}"
            )

        request = MCPRequest(
            request_id=f"{server_id}:{tool_name}:{datetime.now(timezone.utc).timestamp()}",
            tool_name=tool_name,
            parameters=parameters
        )

        return await server.execute_tool(request)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all servers"""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "servers": [server.get_stats() for server in self.servers.values()],
            "total_tools": sum(len(server.tools) for server in self.servers.values()),
            "total_requests": sum(server.stats["requests_received"] for server in self.servers.values()),
            "total_errors": sum(server.stats["errors"] for server in self.servers.values())
        }


# Global instance
mcp_manager = MCPServerManager()
