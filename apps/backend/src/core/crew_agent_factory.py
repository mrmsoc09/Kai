"""
Crew Agent Factory
==================
Factory for instantiating Wave 4 crew agents for injection into mission execution.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Callable

from apps.backend.src.agents.crew.surface_mapper_agent import SurfaceMapper
from apps.backend.src.agents.crew.osint_intelligence_agent import OSINTIntelligenceAgent
from apps.backend.src.agents.crew.dark_web_intel_agent import DarkWebIntelAgent
from apps.backend.src.agents.crew.secret_scanner_agent import SecretScannerAgent
from apps.backend.src.agents.crew.content_discovery_agent import ContentDiscoveryAgent
from apps.backend.src.agents.crew.vulnerability_agent import VulnerabilityAgent
from apps.backend.src.agents.crew.api_security_agent import APISecurityAgent
from apps.backend.src.agents.crew.faraday_coordinator_agent import FaradayCoordinatorAgent

logger = logging.getLogger(__name__)


def _run_coro_in_dedicated_loop(coro: Any, agent_name: str) -> Any:
    """
    Execute a coroutine in a dedicated thread/loop and return its result.

    This is used when LangGraph invokes a sync wrapper while already running
    inside an event loop. Returning placeholders here caused silent degradation
    of crew-agent execution.
    """
    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["result"] = asyncio.run(coro)
        except Exception as exc:  # pragma: no cover - defensive relay
            box["error"] = exc

    thread = threading.Thread(target=_runner, daemon=True, name=f"{agent_name}_async_bridge")
    thread.start()
    thread.join()

    if "error" in box:
        raise RuntimeError(f"{agent_name} async bridge failed: {box['error']}") from box["error"]
    return box.get("result")


def _wrap_async_execute(
    agent_instance: Any,
    agent_name: str,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap an async execute method into a synchronous callable suitable for LangGraph.

    Args:
        agent_instance: Instance with async execute(mission_context, prior_findings) method
        agent_name: Name for logging

    Returns:
        Synchronous callable that takes state dict and returns state dict
    """

    def sync_wrapper(state: dict[str, Any]) -> dict[str, Any]:
        try:
            # Extract mission context from state
            mission_context = {
                "mission_id": state.get("mission_id"),
                "workflow_id": state.get("workflow_id"),
                "program_id": state.get("program_id"),
                "target": state.get("target"),
                "scan_id": state.get("scan_id"),
                "phase": state.get("phase"),
            }
            # Use prior findings from state or empty dict
            prior_findings = state.get("findings", [])

            # Try to execute the async method
            # LangGraph node executors are sync callables; bridge async methods safely.
            coro = agent_instance.execute(mission_context, prior_findings)

            try:
                asyncio.get_running_loop()
                result = _run_coro_in_dedicated_loop(coro, agent_name)
            except RuntimeError:
                # No running loop in current thread; execute directly.
                result = asyncio.run(coro)

            if isinstance(result, dict):
                # Merge result into state
                update = {
                    "active_node": agent_name,
                    "last_agent": agent_name,
                    "node_history": [{"node_id": agent_name, "status": "completed", "entered_at": "", "completed_at": "", "duration_ms": 0}],
                }
                for key, val in result.items():
                    if key not in update:
                        update[key] = val
                return update
            return {
                "active_node": agent_name,
                "last_agent": agent_name,
                "findings": prior_findings,
            }

        except Exception as e:
            logger.error(f"{agent_name} wrapper failed: {e}", exc_info=True)
            return {
                "active_node": agent_name,
                "last_agent": agent_name,
                "error": f"{agent_name} execution failed: {str(e)}",
            }

    return sync_wrapper


def instantiate_crew_agents() -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """
    Instantiate all Wave 4 crew agents and return as a dict of callables.

    Returns:
        dict mapping agent_id (node name) → callable for execution
    """
    agents: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    try:
        surface_agent = SurfaceMapper()
        agents["SurfaceMapper"] = _wrap_async_execute(surface_agent, "SurfaceMapper")
        logger.info("Instantiated SurfaceMapper")
    except Exception as e:
        logger.warning(f"Failed to instantiate SurfaceMapper: {e}")

    try:
        osint_agent = OSINTIntelligenceAgent()
        agents["OSINTIntelligenceAgent"] = _wrap_async_execute(osint_agent, "OSINTIntelligenceAgent")
        logger.info("Instantiated OSINTIntelligenceAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate OSINTIntelligenceAgent: {e}")

    try:
        dark_web_agent = DarkWebIntelAgent()
        agents["DarkWebIntelAgent"] = _wrap_async_execute(dark_web_agent, "DarkWebIntelAgent")
        logger.info("Instantiated DarkWebIntelAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate DarkWebIntelAgent: {e}")

    try:
        secret_agent = SecretScannerAgent()
        agents["SecretScannerAgent"] = _wrap_async_execute(secret_agent, "SecretScannerAgent")
        logger.info("Instantiated SecretScannerAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate SecretScannerAgent: {e}")

    try:
        content_agent = ContentDiscoveryAgent()
        agents["ContentDiscoveryAgent"] = _wrap_async_execute(content_agent, "ContentDiscoveryAgent")
        logger.info("Instantiated ContentDiscoveryAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate ContentDiscoveryAgent: {e}")

    try:
        vuln_agent = VulnerabilityAgent()
        agents["VulnerabilityAgent"] = _wrap_async_execute(vuln_agent, "VulnerabilityAgent")
        logger.info("Instantiated VulnerabilityAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate VulnerabilityAgent: {e}")

    try:
        api_agent = APISecurityAgent()
        agents["APISecurityAgent"] = _wrap_async_execute(api_agent, "APISecurityAgent")
        logger.info("Instantiated APISecurityAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate APISecurityAgent: {e}")

    try:
        faraday_agent = FaradayCoordinatorAgent()
        agents["FaradayCoordinatorAgent"] = _wrap_async_execute(faraday_agent, "FaradayCoordinatorAgent")
        logger.info("Instantiated FaradayCoordinatorAgent")
    except Exception as e:
        logger.warning(f"Failed to instantiate FaradayCoordinatorAgent: {e}")

    logger.info(f"Instantiated {len(agents)} crew agents")
    return agents
