from __future__ import annotations

import importlib
import logging
import socket
from typing import Any

logger = logging.getLogger(__name__)

# OSINT finding signals that warrant automatic dark web escalation
_DARK_WEB_SIGNAL_KEYWORDS = (
    "credential",
    "password",
    "leaked",
    "breach",
    "dump",
    "paste",
    "darkweb",
    "dark web",
    "onion",
    "ransomware",
    "extortion",
)


def _osint_suggests_darkweb(prior_findings: dict) -> bool:
    """Return True if prior OSINT findings contain dark web escalation signals."""
    leaked_creds = prior_findings.get("leaked_credentials", [])
    if leaked_creds:
        return True
    for key in ("raw_text", "summary", "notes", "mentions"):
        text = str(prior_findings.get(key, "")).lower()
        if any(kw in text for kw in _DARK_WEB_SIGNAL_KEYWORDS):
            return True
    return False


class DarkWebIntelAgent:
    """Coordinates dark web tool agents (opt-in only).

    Runs only when:
    - mission_context["dark_web_scope_enabled"] is True, OR
    - prior OSINT findings signal dark web relevance (leaked creds, breach mentions)
    """

    def __init__(self, config: dict | None = None):
        self.config = config or {}

    async def execute(
        self,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        """Execute dark web intelligence phase — skipped unless explicitly enabled or signalled."""
        explicitly_enabled = bool(
            mission_context.get("dark_web_scope_enabled", False)
        )
        signal_detected = _osint_suggests_darkweb(prior_findings)

        if not explicitly_enabled and not signal_detected:
            logger.info(
                "DarkWebIntelAgent skipped: dark_web_scope_enabled=False "
                "and no OSINT signals detected."
            )
            return {
                "dark_web_complete": False,
                "skipped": True,
                "reason": "dark_web_scope_not_enabled",
                "credential_mentions": [],
                "org_mentions": [],
                "onion_urls": [],
            }

        if signal_detected and not explicitly_enabled:
            logger.info(
                "DarkWebIntelAgent triggered by OSINT signal "
                "(leaked credentials or breach mention detected)."
            )

        try:
            tor_available = self.verify_tor_service()
            if not tor_available:
                logger.warning(
                    "Tor unavailable on port 9050. "
                    "Running ahmia-client only."
                )

            results = []
            errors = []

            execution_groups = self.get_execution_order(
                prior_findings
            )

            for group in execution_groups:
                group_results = []
                for tool_name in group:
                    try:
                        # Skip Tor-dependent tools if Tor unavailable
                        if (
                            not tor_available
                            and tool_name in ("torbot", "onionsearch")
                        ):
                            errors.append(
                                f"{tool_name}: Tor unavailable"
                            )
                            continue

                        tool_context = self.build_tool_context(
                            tool_name,
                            mission_context,
                            prior_findings,
                        )

                        # Check if tool should be skipped
                        if tool_context.get("skip"):
                            continue

                        # Import and instantiate the tool agent
                        tool_agent = self._load_tool_agent(
                            tool_name
                        )
                        if tool_agent is None:
                            errors.append(
                                f"{tool_name}: agent not found"
                            )
                            continue

                        # Execute the tool agent
                        result = tool_agent.execute(
                            target=tool_context.get(
                                "target",
                                mission_context.get("target", "")
                            ),
                            options=tool_context,
                            mission_id=mission_context.get(
                                "mission_id",
                                "mission-001"
                            ),
                        )
                        group_results.append({
                            "tool": tool_name,
                            "result": result,
                            "finding_count": len(result.findings),
                            "high_value_findings": [
                                f.model_dump()
                                for f in result.findings
                                if f.severity
                                in ("critical", "high")
                            ],
                            "parsed_findings": [
                                f.model_dump()
                                for f in result.findings
                            ],
                        })

                    except Exception as e:
                        logger.error(
                            "Tool agent %s failed in "
                            "DarkWebIntelAgent: %s",
                            tool_name,
                            str(e),
                        )
                        errors.append(
                            f"{tool_name}: {str(e)}"
                        )
                        continue

                results.extend(group_results)

            aggregated = self.aggregate_tool_results(
                results, mission_context
            )
            aggregated["errors"] = errors
            aggregated["tools_executed"] = [
                r["tool"] for r in results
            ]
            return aggregated

        except Exception as e:
            logger.error(
                f"DarkWebIntelAgent failed: {e}", exc_info=True
            )
            return {
                "dark_web_complete": False,
                "error": str(e),
                "credential_mentions": [],
                "org_mentions": [],
                "onion_urls": [],
            }

    def _load_tool_agent(self, tool_name: str):
        """
        Dynamically load a tool agent by name.
        Returns None if agent cannot be loaded.
        """
        # Normalize tool name to module name
        module_name = tool_name.replace("-", "_")

        try:
            module = importlib.import_module(
                f"apps.backend.src.agents.tools.{module_name}.agent"
            )
            # Find the agent class
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and attr_name.endswith("Agent")
                    and attr_name != "BaseToolAgent"
                ):
                    return attr()
            logger.warning(
                "No agent class found in %s", module_name
            )
            return None
        except ImportError as e:
            logger.warning(
                "Could not import tool agent %s: %s",
                tool_name, str(e)
            )
            return None

    def verify_tor_service(self) -> bool:
        """Check if Tor service is available on port 9050."""
        try:
            s = socket.socket()
            s.settimeout(5)
            s.connect(("127.0.0.1", 9050))
            s.close()
            return True
        except Exception:
            return False

    def get_tool_agents(self) -> list[str]:
        return ["torbot", "onionsearch", "ahmia-client"]

    def get_execution_order(
        self,
        prior_findings: dict,
    ) -> list[list[str]]:
        return [
            ["ahmia-client"],
            ["torbot", "onionsearch"],
        ]

    def build_tool_context(
        self,
        tool_name: str,
        mission_context: dict,
        prior_findings: dict,
    ) -> dict:
        return {
            "target": mission_context.get("target"),
            "scan_id": mission_context.get("scan_id"),
            "mission_id": mission_context.get("mission_id"),
            "artifact_dir": mission_context.get(
                "artifact_dir"
            ),
            "timeout": mission_context.get("timeout", 300),
            "prior_phase_findings": prior_findings,
        }

    def aggregate_tool_results(
        self,
        tool_results: list[dict],
        mission_context: dict,
    ) -> dict:
        return {
            "dark_web_complete": True,
            "credential_mentions": [],
            "org_mentions": [],
            "onion_urls": [],
        }
