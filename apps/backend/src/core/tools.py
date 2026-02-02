"""
Unified Tool Framework for K1
Base classes, registry, and execution context for all tools
"""

import json
import uuid
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """Tool categories for organization"""
    OSINT = "osint"              # Open source intelligence
    SCANNER = "scanner"          # Vulnerability scanning
    CTI = "cti"                  # Cyber threat intelligence
    ANALYSIS = "analysis"        # Finding/chain analysis
    VALIDATION = "validation"    # Decision validation
    REPORTING = "reporting"      # Report generation
    ORCHESTRATION = "orchestration"  # Workflow orchestration
    REASONING = "reasoning"      # Deep reasoning (DeepAgents)


class ToolStatus(Enum):
    """Tool execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolAutonomyTier(Enum):
    """Autonomy tier determines approval requirements"""
    TIER_0_AUTO = 0        # No approval needed (local-only, reversible)
    TIER_1_NOTIFY = 1      # Notification only (low-risk external)
    TIER_2_APPROVE = 2     # Requires HiL approval (external execution)
    TIER_3_HARD_STOP = 3   # Explicit approval required (irreversible)


@dataclass
class ToolParameter:
    """Represents a tool parameter/input"""
    name: str
    type: str  # "string", "number", "boolean", "array", "object"
    description: str
    required: bool = True
    default: Any = None
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None

    def to_schema(self) -> Dict[str, Any]:
        """Convert to JSON schema format"""
        schema = {
            "type": self.type,
            "description": self.description,
        }
        if self.default is not None:
            schema["default"] = self.default
        if self.enum:
            schema["enum"] = self.enum
        if self.min_value is not None:
            schema["minimum"] = self.min_value
        if self.max_value is not None:
            schema["maximum"] = self.max_value
        return schema


@dataclass
class ToolResult:
    """Result from tool execution"""
    tool_id: str
    status: ToolStatus
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    tokens_used: Optional[Dict[str, int]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_id": self.tool_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
        }


@dataclass
class ToolExecutionContext:
    """Context for tool execution"""
    tool_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    run_id: Optional[str] = None
    user_id: Optional[str] = None
    approval_status: str = "pending"  # pending, approved, rejected
    approved_by: Optional[str] = None
    approval_timestamp: Optional[datetime] = None
    autonomy_tier: ToolAutonomyTier = ToolAutonomyTier.TIER_2_APPROVE
    requires_approval: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_approved(self) -> bool:
        """Check if execution is approved"""
        if self.autonomy_tier == ToolAutonomyTier.TIER_0_AUTO:
            return True
        return self.approval_status == "approved"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "tool_id": self.tool_id,
            "execution_id": self.execution_id,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "autonomy_tier": self.autonomy_tier.name,
            "requires_approval": self.requires_approval,
            "metadata": self.metadata,
        }


class BaseTool(ABC):
    """Base class for all K1 tools"""

    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        category: ToolCategory,
        autonomy_tier: ToolAutonomyTier = ToolAutonomyTier.TIER_2_APPROVE,
        parameters: Optional[List[ToolParameter]] = None,
        version: str = "1.0.0",
    ):
        self.id = id
        self.name = name
        self.description = description
        self.category = category
        self.autonomy_tier = autonomy_tier
        self.parameters = parameters or []
        self.version = version
        self.created_at = datetime.utcnow()
        self.last_used = None
        self.use_count = 0
        self.success_count = 0
        self.failure_count = 0

    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters"""
        pass

    def get_schema(self) -> Dict[str, Any]:
        """Get tool schema for LLM tool calling"""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = param.to_schema()
            if param.required:
                required.append(param.name)

        return {
            "name": self.id,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def validate_parameters(self, **kwargs) -> tuple[bool, Optional[str]]:
        """Validate input parameters"""
        required_params = {p.name for p in self.parameters if p.required}
        provided_params = set(kwargs.keys())

        missing = required_params - provided_params
        if missing:
            return False, f"Missing required parameters: {missing}"

        extra = provided_params - {p.name for p in self.parameters}
        if extra:
            return False, f"Unknown parameters: {extra}"

        return True, None

    def record_execution(self, result: ToolResult):
        """Record tool execution metrics"""
        self.use_count += 1
        self.last_used = datetime.utcnow()

        if result.status == ToolStatus.COMPLETED:
            self.success_count += 1
        else:
            self.failure_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get tool usage statistics"""
        success_rate = (
            (self.success_count / self.use_count * 100)
            if self.use_count > 0
            else 0
        )
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category.value,
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "use_count": self.use_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": success_rate,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "autonomy_tier": self.autonomy_tier.name,
            "version": self.version,
            "parameters": [asdict(p) for p in self.parameters],
            "created_at": self.created_at.isoformat(),
            "schema": self.get_schema(),
            "stats": self.get_stats(),
        }


class ToolRegistry:
    """Registry for managing all available tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tools_by_category: Dict[ToolCategory, Set[str]] = {
            cat: set() for cat in ToolCategory
        }

    def register(self, tool: BaseTool):
        """Register a tool"""
        if tool.id in self._tools:
            logger.warning(f"Overwriting tool: {tool.id}")

        self._tools[tool.id] = tool
        self._tools_by_category[tool.category].add(tool.id)
        logger.info(f"Registered tool: {tool.id}")

    def unregister(self, tool_id: str) -> bool:
        """Unregister a tool"""
        if tool_id not in self._tools:
            return False

        tool = self._tools[tool_id]
        self._tools_by_category[tool.category].discard(tool_id)
        del self._tools[tool_id]
        logger.info(f"Unregistered tool: {tool_id}")
        return True

    def get(self, tool_id: str) -> Optional[BaseTool]:
        """Get a tool by ID"""
        return self._tools.get(tool_id)

    def list_all(self) -> List[BaseTool]:
        """List all registered tools"""
        return list(self._tools.values())

    def list_by_category(self, category: ToolCategory) -> List[BaseTool]:
        """List tools by category"""
        tool_ids = self._tools_by_category[category]
        return [self._tools[id] for id in tool_ids]

    def list_by_autonomy_tier(self, tier: ToolAutonomyTier) -> List[BaseTool]:
        """List tools by autonomy tier"""
        return [t for t in self._tools.values() if t.autonomy_tier == tier]

    def get_schema(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """Get tool schema for LLM tool calling"""
        tool = self.get(tool_id)
        return tool.get_schema() if tool else None

    def get_all_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Get all tool schemas"""
        return {tool_id: self.get_schema(tool_id) for tool_id in self._tools}

    def count(self) -> int:
        """Get total number of registered tools"""
        return len(self._tools)

    def stats(self) -> Dict[str, Any]:
        """Get registry statistics"""
        return {
            "total_tools": self.count(),
            "by_category": {
                cat.value: len(self._tools_by_category[cat])
                for cat in ToolCategory
            },
            "tools": {
                tool_id: tool.get_stats()
                for tool_id, tool in self._tools.items()
            },
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert registry to dictionary"""
        return {
            "tools": {tool_id: tool.to_dict() for tool_id, tool in self._tools.items()},
            "stats": self.stats(),
        }


# Global registry instance
_global_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    """Get global tool registry"""
    return _global_registry


def register_tool(tool: BaseTool):
    """Register a tool globally"""
    _global_registry.register(tool)


def get_tool(tool_id: str) -> Optional[BaseTool]:
    """Get tool from global registry"""
    return _global_registry.get(tool_id)
