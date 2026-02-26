"""
Agent-to-Agent (A2A) Communication System for K1
Redis-based pub/sub with agent registry and workflow orchestration
"""

import redis
import json
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
from datetime import datetime
import asyncio


class AgentRole(str, Enum):
    """Agent roles in K1"""
    ORCHESTRATOR = "orchestrator"      # Master coordinator
    SCOUT = "scout"                     # OSINT/reconnaissance
    VALIDATOR = "validator"             # Finding validation
    ANALYZER = "analyzer"               # Deep analysis
    STRATEGIST = "strategist"           # Attack planning
    REPORTER = "reporter"               # Report generation


class MessageType(str, Enum):
    """Types of messages agents can send"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    STATUS_UPDATE = "status_update"
    ERROR_REPORT = "error_report"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    BROADCAST = "broadcast"


@dataclass
class Agent:
    """Represents an autonomous agent"""
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: AgentRole = AgentRole.SCOUT
    name: str = ""
    description: str = ""
    status: str = "idle"  # idle, working, waiting, error
    current_task_id: Optional[str] = None
    llm_model: str = "claude-3-5-sonnet-20241022"
    available_tools: List[str] = field(default_factory=list)
    autonomy_tier: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_activity: datetime = field(default_factory=datetime.utcnow)
    messages_sent: int = 0
    messages_received: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "name": self.name,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "llm_model": self.llm_model,
            "autonomy_tier": self.autonomy_tier
        }


@dataclass
class A2AMessage:
    """Agent-to-Agent message"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    receiver_id: str = ""
    message_type: MessageType = MessageType.TASK_REQUEST
    content: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""  # Links request/response
    priority: int = 5  # 1-10, higher = more important
    timestamp: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None

    def to_json(self) -> str:
        return json.dumps({
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "correlation_id": self.correlation_id,
            "priority": self.priority,
            "timestamp": self.timestamp.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None
        }, default=str)

    @classmethod
    def from_json(cls, data: str) -> 'A2AMessage':
        d = json.loads(data)
        return cls(
            message_id=d.get("message_id", ""),
            sender_id=d.get("sender_id", ""),
            receiver_id=d.get("receiver_id", ""),
            message_type=MessageType(d.get("message_type", "task_request")),
            content=d.get("content", {}),
            correlation_id=d.get("correlation_id", ""),
            priority=d.get("priority", 5),
            timestamp=datetime.fromisoformat(d.get("timestamp", datetime.utcnow().isoformat())),
            expires_at=datetime.fromisoformat(d["expires_at"]) if d.get("expires_at") else None
        )


class AgentRegistry:
    """Central registry of all K1 agents"""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.agents: Dict[str, Agent] = {}
        self._initialize_default_agents()

    def _initialize_default_agents(self):
        """Create default K1 agents"""
        agents_config = [
            {
                "role": AgentRole.ORCHESTRATOR,
                "name": "Orchestrator",
                "description": "Coordinates multi-agent workflows",
                "available_tools": ["job_queue", "task_dispatch", "status_monitor"],
                "autonomy_tier": 3
            },
            {
                "role": AgentRole.SCOUT,
                "name": "Recon Scout",
                "description": "Performs OSINT and reconnaissance",
                "available_tools": ["domain_enumeration", "subdomain_discovery", "ssl_analyzer", "header_analyzer"],
                "autonomy_tier": 1
            },
            {
                "role": AgentRole.VALIDATOR,
                "name": "Evidence Validator",
                "description": "Validates findings and evidence",
                "available_tools": ["quick_classifier", "finding_validator", "evidence_scorer"],
                "autonomy_tier": 1
            },
            {
                "role": AgentRole.ANALYZER,
                "name": "Deep Analyzer",
                "description": "Performs deep technical analysis",
                "available_tools": ["vulnerability_analyzer", "chain_analyzer"],
                "autonomy_tier": 1
            },
            {
                "role": AgentRole.STRATEGIST,
                "name": "Attack Planner",
                "description": "Plans attack chains and strategies",
                "available_tools": ["attack_graph_builder", "chain_builder", "scope_mapper"],
                "autonomy_tier": 1
            },
            {
                "role": AgentRole.REPORTER,
                "name": "Report Generator",
                "description": "Generates professional reports",
                "available_tools": ["report_generator", "program_matcher"],
                "autonomy_tier": 0  # Requires human review
            }
        ]

        for config in agents_config:
            agent = Agent(
                role=config["role"],
                name=config["name"],
                description=config["description"],
                available_tools=config["available_tools"],
                autonomy_tier=config.get("autonomy_tier", 0)
            )
            self.agents[agent.agent_id] = agent
            self.redis.hset(f"agent:{agent.agent_id}", mapping=self._agent_to_redis(agent))

    def _agent_to_redis(self, agent: Agent) -> Dict[str, str]:
        """Convert agent to Redis hash format"""
        return {
            "agent_id": agent.agent_id,
            "role": agent.role.value,
            "name": agent.name,
            "status": agent.status,
            "current_task_id": agent.current_task_id or "",
            "llm_model": agent.llm_model,
            "available_tools": json.dumps(agent.available_tools),
            "autonomy_tier": str(agent.autonomy_tier),
            "last_activity": agent.last_activity.isoformat()
        }

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)

    def get_agents_by_role(self, role: AgentRole) -> List[Agent]:
        return [a for a in self.agents.values() if a.role == role]

    def update_agent_status(self, agent_id: str, status: str, task_id: Optional[str] = None):
        """Update agent status"""
        agent = self.agents.get(agent_id)
        if agent:
            agent.status = status
            agent.current_task_id = task_id
            agent.last_activity = datetime.utcnow()
            self.redis.hset(f"agent:{agent_id}", mapping=self._agent_to_redis(agent))

    def list_agents(self) -> List[Dict]:
        return [a.to_dict() for a in self.agents.values()]


class A2ABus:
    """Redis-based message bus for agent communication"""

    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
        self.message_log: List[Dict] = []
        self.message_handlers: Dict[str, List[Callable]] = {}

    def subscribe(self, agent_id: str, message_type: Optional[MessageType] = None) -> str:
        """Subscribe to messages for an agent"""
        channel = f"agent:{agent_id}"
        if message_type:
            channel += f":{message_type.value}"

        self.pubsub.subscribe(channel)
        return channel

    def unsubscribe(self, channel: str):
        """Unsubscribe from channel"""
        self.pubsub.unsubscribe(channel)

    def publish(self, message: A2AMessage) -> int:
        """Publish message to agent"""
        channel = f"agent:{message.receiver_id}"
        if message.message_type != MessageType.BROADCAST:
            channel += f":{message.message_type.value}"

        # Store in Redis sorted set for persistence
        timestamp = message.timestamp.timestamp()
        self.redis.zadd(f"messages:{message.receiver_id}", {message.to_json(): timestamp})

        # Publish to channel
        result = self.redis.publish(channel, message.to_json())

        # Log message
        self.message_log.append({
            "message_id": message.message_id,
            "sender": message.sender_id,
            "receiver": message.receiver_id,
            "type": message.message_type.value,
            "timestamp": message.timestamp.isoformat()
        })

        return result

    async def broadcast(self, message: A2AMessage, recipients: List[str]):
        """Broadcast message to multiple agents"""
        for recipient_id in recipients:
            message.receiver_id = recipient_id
            self.publish(message)

    def get_messages(self, agent_id: str, limit: int = 100) -> List[A2AMessage]:
        """Get message history for an agent"""
        messages = []
        for msg_json in self.redis.zrange(f"messages:{agent_id}", -limit, -1):
            try:
                messages.append(A2AMessage.from_json(msg_json.decode()))
            except Exception:
                pass
        return messages

    def clear_messages(self, agent_id: str):
        """Clear message history"""
        self.redis.delete(f"messages:{agent_id}")

    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics"""
        return {
            "total_messages_logged": len(self.message_log),
            "recent_messages": self.message_log[-10:],
            "message_types": self._count_by_type()
        }

    def _count_by_type(self) -> Dict[str, int]:
        """Count messages by type"""
        counts = {}
        for msg in self.message_log:
            msg_type = msg.get("type", "unknown")
            counts[msg_type] = counts.get(msg_type, 0) + 1
        return counts


class WorkflowOrchestrator:
    """Orchestrates multi-agent workflows"""

    def __init__(self, agent_registry: AgentRegistry, a2a_bus: A2ABus):
        self.registry = agent_registry
        self.bus = a2a_bus
        self.workflows: Dict[str, Dict] = {}
        self.redis = a2a_bus.redis

    def create_hunt_workflow(
        self,
        target: str,
        scope: Dict[str, Any],
        workflow_id: Optional[str] = None
    ) -> str:
        """Create a vulnerability hunting workflow"""
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        workflow = {
            "id": workflow_id,
            "target": target,
            "scope": scope,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
            "started_at": None,
            "completed_at": None,
            "steps": [
                {
                    "step_id": str(uuid.uuid4()),
                    "name": "Reconnaissance",
                    "agent_role": AgentRole.SCOUT.value,
                    "status": "pending",
                    "result": None
                },
                {
                    "step_id": str(uuid.uuid4()),
                    "name": "Finding Validation",
                    "agent_role": AgentRole.VALIDATOR.value,
                    "status": "pending",
                    "depends_on": 0
                },
                {
                    "step_id": str(uuid.uuid4()),
                    "name": "Technical Analysis",
                    "agent_role": AgentRole.ANALYZER.value,
                    "status": "pending",
                    "depends_on": 1
                },
                {
                    "step_id": str(uuid.uuid4()),
                    "name": "Attack Planning",
                    "agent_role": AgentRole.STRATEGIST.value,
                    "status": "pending",
                    "depends_on": 2
                },
                {
                    "step_id": str(uuid.uuid4()),
                    "name": "Report Generation",
                    "agent_role": AgentRole.REPORTER.value,
                    "status": "pending",
                    "depends_on": 3
                }
            ]
        }

        self.workflows[workflow_id] = workflow
        self.redis.set(f"workflow:{workflow_id}", json.dumps(workflow, default=str))

        # Start first step
        self._dispatch_step(workflow_id, 0)

        return workflow_id

    def _dispatch_step(self, workflow_id: str, step_index: int):
        """Dispatch a workflow step to appropriate agent"""
        workflow = self.workflows.get(workflow_id)
        if not workflow or step_index >= len(workflow["steps"]):
            return

        step = workflow["steps"][step_index]
        step["status"] = "in_progress"

        # Get agent for this role
        role = AgentRole(step["agent_role"])
        agents = self.registry.get_agents_by_role(role)

        if not agents:
            print(f"No agent available for role: {role.value}")
            return

        agent = agents[0]  # Use first available

        # Send task to agent
        message = A2AMessage(
            sender_id="orchestrator",
            receiver_id=agent.agent_id,
            message_type=MessageType.TASK_REQUEST,
            content={
                "workflow_id": workflow_id,
                "step_id": step["step_id"],
                "step_name": step["name"],
                "target": workflow["target"],
                "scope": workflow["scope"]
            },
            correlation_id=workflow_id
        )

        self.bus.publish(message)
        self.registry.update_agent_status(agent.agent_id, "working", workflow_id)

    def handle_step_completion(self, workflow_id: str, step_index: int, result: Dict):
        """Handle step completion and dispatch next step"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return

        step = workflow["steps"][step_index]
        step["status"] = "complete"
        step["result"] = result

        # Dispatch next step
        self._dispatch_step(workflow_id, step_index + 1)

        # Check if workflow complete
        if step_index == len(workflow["steps"]) - 1:
            workflow["status"] = "complete"
            workflow["completed_at"] = datetime.utcnow().isoformat()

    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        return self.workflows.get(workflow_id)

    def list_workflows(self) -> List[Dict]:
        return list(self.workflows.values())


# Global instances
agent_registry = None  # Initialize with Redis
a2a_bus = None  # Initialize with Redis
workflow_orchestrator = None  # Initialize with registry and bus


def initialize_a2a(redis_url: str = "redis://localhost:6379"):
    """Initialize A2A system"""
    global agent_registry, a2a_bus, workflow_orchestrator

    redis_client = redis.from_url(redis_url)
    agent_registry = AgentRegistry(redis_client)
    a2a_bus = A2ABus(redis_url)
    workflow_orchestrator = WorkflowOrchestrator(agent_registry, a2a_bus)

    print("✓ A2A communication system initialized")
    print(f"  - Registered {len(agent_registry.agents)} agents")
    return agent_registry, a2a_bus, workflow_orchestrator
