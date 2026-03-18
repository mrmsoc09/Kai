"""
LangGraph Adapter — Praison → LangGraph Node Spec
=====================================================
Converts a K1 AgentIdentity into a LangGraph node specification dict.

This adapter is a SCAFFOLD. It does NOT compile or execute LangGraph graphs.
That is Platform 3's responsibility (the LangGraph execution DAG engine).

What this adapter does RIGHT NOW:
- Converts AgentIdentity into a complete node spec dict
- Spec dict contains everything LangGraph needs to compile the node
- Declares graph edge policy (handoff triggers, conditional routing)
- Sets approval interrupt behavior based on review_policy

What Platform 3 (LangGraph) will do with these specs:
- Compile StateGraph nodes from spec dicts
- Wire conditional edges based on handoff_policy
- Attach checkpointing (PostgreSQL via langgraph-checkpoint-postgres)
- Bind PraisonAI governance as interrupt() calls for HIL stops

Mapping:
    Praison concept        LangGraph concept
    ─────────────────────  ──────────────────────────────────────
    agent                  graph node
    agent_id               node name
    system_prompt          node system prompt
    allowed_tools          tools bound to node
    review_policy=strict   interrupt_before=[node_name] (HIL stop)
    handoff policy         conditional edge routing
    memory_scope=workflow  checkpointer scope
"""

from __future__ import annotations

import logging
from typing import Any

from apps.backend.src.core.praison_agent import AgentIdentity, resolve_litellm_string

logger = logging.getLogger(__name__)


def to_langgraph_node(identity: AgentIdentity) -> dict[str, Any]:
    """
    Convert a Praison AgentIdentity into a LangGraph node specification.

    Returns a spec dict that Platform 3 (LangGraph execution engine) will
    consume to compile StateGraph nodes. Nothing is instantiated here —
    this is a pure data transformation.

    Returns:
        {
            "node_id":        str,   # unique node name in the graph
            "node_type":      str,   # "agent" | "governance" | "reporter"
            "system_prompt":  str,   # injected as node's system message
            "llm_pin":        str,   # provider key for LLM selection
            "litellm_model":  str,   # resolved LiteLLM string
            "allowed_tools":  list,  # tool IDs available to this node
            "risk_profile":   str,   # node capability tier
            "memory_scope":   str,   # checkpoint persistence scope
            "handoff_policy": dict,  # conditional edge routing rules
            "interrupt_policy": dict, # HIL stop configuration
            "workflow_id":    str,   # runtime campaign context
            "program_id":     str,
            "execution_id":   str,
        }
    """
    node_type = _classify_node_type(identity.risk_profile)
    handoff_policy = _build_handoff_policy(identity)
    interrupt_policy = _build_interrupt_policy(identity)

    spec: dict[str, Any] = {
        "node_id":         identity.agent_id,
        "node_type":       node_type,
        "system_prompt":   identity.system_prompt,
        "llm_pin":         identity.llm_pin,
        "litellm_model":   resolve_litellm_string(identity.llm_pin),
        "allowed_tools":   list(identity.allowed_tools),
        "risk_profile":    identity.risk_profile,
        "memory_scope":    identity.memory_scope,
        "handoff_policy":  handoff_policy,
        "interrupt_policy": interrupt_policy,
        # Runtime fields — set at graph execution time
        "workflow_id":     identity.workflow_id,
        "program_id":      identity.program_id,
        "execution_id":    identity.execution_id,
        "spawned_at":      identity.spawned_at.isoformat(),
    }

    logger.debug(
        "LangGraph node spec created: node_id=%s type=%s llm=%s interrupt=%s",
        identity.agent_id,
        node_type,
        spec["litellm_model"],
        interrupt_policy.get("interrupt_before", False),
    )
    return spec


def _classify_node_type(risk_profile: str) -> str:
    """
    Map risk_profile to a LangGraph node type.
    Node type determines how Platform 3 routes edges and applies policies.
    """
    mapping = {
        "governance":    "governance",   # interrupts graph for HIL on Band 2+
        "analysis":      "reporter",     # read-only, non-interrupting
        "orchestration": "coordinator",  # routes edges, no tool execution
        "recon":         "agent",        # active scanning node
        "reporting":     "reporter",
        "standard":      "agent",
    }
    return mapping.get(risk_profile, "agent")


def _build_handoff_policy(identity: AgentIdentity) -> dict[str, Any]:
    """
    Build edge routing policy for this node.
    LangGraph uses this to configure conditional edges between nodes.

    The HandoffAgent in the Praison layer decides WHAT to route at runtime.
    This policy declares HOW routing is configured structurally in the graph.
    """
    return {
        # governance nodes block dependent branches on HIL hold
        "blocks_on_hil_hold":    identity.risk_profile == "governance",
        # analysis/reporter nodes route to HandoffAgent after completion
        "routes_to_handoff":     identity.risk_profile in ("analysis", "reporting"),
        # Memory persistence across edges
        "persist_context":       identity.memory_scope in ("workflow", "persistent"),
        # Governance agents inject their output into the HIL approval context
        "injects_hil_context":   identity.risk_profile == "governance",
    }


def _build_interrupt_policy(identity: AgentIdentity) -> dict[str, Any]:
    """
    Build interrupt configuration for this node.
    LangGraph's interrupt_before / interrupt_after controls HIL stops.
    """
    return {
        # strict agents pause execution before the node runs (human must approve)
        "interrupt_before": identity.review_policy == "strict",
        # moderate agents pause after (human reviews output before next node)
        "interrupt_after":  identity.review_policy == "moderate",
        # standard agents run without interruption
        "requires_approval": identity.review_policy in ("strict", "moderate"),
        # Which PraisonAI agent handles the interrupt (governance layer)
        "approval_agent":   "SecurityGovernorAgent",
    }
