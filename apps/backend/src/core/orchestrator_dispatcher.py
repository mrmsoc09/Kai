from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from typing import Any

from .playbook_memory import PlaybookMemory
from .tool_adapters.base_adapter import execute_registered_tool
from .tools import get_registry

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    step: int
    playbook_name: str
    tool_id: str
    status: str
    error: str | None
    output: dict[str, Any] | None
    fallback_used: bool = False
    executed_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "playbook_name": self.playbook_name,
            "tool_id": self.tool_id,
            "status": self.status,
            "error": self.error,
            "output": self.output,
            "fallback_used": self.fallback_used,
            "executed_at": self.executed_at or datetime.now(timezone.utc).isoformat(),
        }


class OrchestratorDispatcher:
    """
    Search-and-execute dispatcher using precomputed indices only.
    """

    def __init__(
        self,
        *,
        playbook_memory: PlaybookMemory | None = None,
        registry: Any | None = None,
    ) -> None:
        self.memory = playbook_memory or PlaybookMemory.get_instance()
        self.registry = registry or get_registry()

    def match_target_to_playbook(
        self,
        cve_id: str,
        tech_stack: list[str] | tuple[str, ...] | None = None,
        *,
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        return self.memory.match_target_to_playbook(cve_id, tech_stack, top_k=top_k)

    def validate_handoff(self, output_schema: str, input_schema: str) -> bool:
        return self.memory.validate_handoff(output_schema, input_schema)

    def _cached_execution_plan(self) -> dict[str, Any]:
        payload = self.memory.get_index("execution_plan_cache", {})
        return payload if isinstance(payload, dict) else {}

    def _playbook_index(self) -> dict[str, Any]:
        payload = self.memory.get_index("playbook_index", {})
        return payload if isinstance(payload, dict) else {}

    def _resolve_tool_for_playbook(self, playbook_name: str, params: dict[str, Any]) -> str:
        explicit = str(params.get("tool_id") or "").strip()
        if explicit:
            return explicit

        index = self._playbook_index()
        rows = index.get("playbooks_by_success_weight", [])
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get("id") or "").strip() == playbook_name:
                    tools = row.get("tools", [])
                    if isinstance(tools, list) and tools:
                        return str(tools[0]).strip()

        return playbook_name

    def dispatch_instruction_tuples(
        self,
        instructions: list[list[Any] | tuple[Any, ...]],
        *,
        target: str,
    ) -> list[dict[str, Any]]:
        """
        Execute instruction tuples:
          (step_N, playbook_name, params, timing, fallback)
        """
        results: list[dict[str, Any]] = []
        for raw in instructions:
            if not isinstance(raw, (list, tuple)) or len(raw) < 5:
                continue
            step_n, playbook_name, params, _timing, fallback = raw[:5]
            step = int(step_n) if str(step_n).isdigit() else 0
            playbook = str(playbook_name)
            params_dict = params if isinstance(params, dict) else {}
            params_dict = dict(params_dict)
            params_dict.setdefault("target", target)

            tool_id = self._resolve_tool_for_playbook(playbook, params_dict)
            tool = self.registry.get(tool_id)
            used_fallback = False

            if tool is None and fallback:
                fallback_tool_id = str(fallback).strip()
                tool = self.registry.get(fallback_tool_id)
                if tool is not None:
                    used_fallback = True
                    tool_id = fallback_tool_id

            if tool is None:
                results.append(
                    DispatchResult(
                        step=step,
                        playbook_name=playbook,
                        tool_id=tool_id,
                        status="failed",
                        error=f"tool_not_registered:{tool_id}",
                        output=None,
                        fallback_used=used_fallback,
                    ).as_dict()
                )
                continue

            try:
                tool_result = execute_registered_tool(tool, params_dict)
                result_dict = (
                    tool_result.to_dict() if hasattr(tool_result, "to_dict") else {"output": tool_result}
                )
                status = str(result_dict.get("status") or "completed")
                results.append(
                    DispatchResult(
                        step=step,
                        playbook_name=playbook,
                        tool_id=tool_id,
                        status=status,
                        error=result_dict.get("error"),
                        output=result_dict,
                        fallback_used=used_fallback,
                    ).as_dict()
                )
            except Exception as exc:
                logger.exception("Instruction dispatch failed for step=%s playbook=%s", step, playbook)
                results.append(
                    DispatchResult(
                        step=step,
                        playbook_name=playbook,
                        tool_id=tool_id,
                        status="failed",
                        error=str(exc),
                        output=None,
                        fallback_used=used_fallback,
                    ).as_dict()
                )
        return results

    def dispatch_cached_plan(
        self,
        *,
        key: str,
        target: str,
    ) -> list[dict[str, Any]]:
        plan_cache = self._cached_execution_plan()
        instructions = plan_cache.get(key, [])
        if not isinstance(instructions, list):
            return []
        return self.dispatch_instruction_tuples(instructions, target=target)

