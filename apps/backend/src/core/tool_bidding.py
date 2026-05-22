"""
K1 Tool Bidding System (ISSUE #7)
==================================
Competitive tool selection replacing the hardcoded preferred_sequences dict in
praison_agent_runtime._execute_specialist_bootstrap_tools().

Tools submit bids based on MissionContext; the BiddingOrchestrator ranks by
bid_score and selects top-N within budget.

Bid score formula:  confidence × (100 / (1 + estimated_cost_cents)) × priority_boost

Enable via env:  K1_TOOL_BIDDING_ENABLED=true  (default: false)
Fallback:        preferred_sequences dict in praison_agent_runtime.py is preserved
                 and used when bidding is disabled or all tools abstain.

Adding a new tool (data-driven):
  1. Add an entry in config/tool_bid_rules.yaml with phase_affinity, dependencies,
     estimated_cost_cents, execution_time_estimate_ms, output_schema, and
     priority_boost_if_goals.
  2. YamlConfiguredToolAgent handles it automatically — no Python changes needed.

Adding a new tool (bespoke logic):
  1. Subclass IToolAgent and override evaluate_bid().
  2. Decorate with @register("tool_id").
"""

from __future__ import annotations

import logging
import os
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Registry                                                                     #
# --------------------------------------------------------------------------- #

_REGISTRY: dict[str, type[IToolAgent]] = {}
_REGISTRY_LOCK = threading.Lock()


def register(tool_id: str):
    """Decorator: register a bespoke IToolAgent subclass for a specific tool."""
    def decorator(cls: type[IToolAgent]) -> type[IToolAgent]:
        with _REGISTRY_LOCK:
            _REGISTRY[tool_id] = cls
        return cls
    return decorator


# --------------------------------------------------------------------------- #
# Data layer                                                                   #
# --------------------------------------------------------------------------- #

@dataclass
class FindingDataset:
    """Structured view of findings accumulated during the mission so far."""
    subdomains: list[str] = field(default_factory=list)
    open_ports: list[int] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    urls_found: list[str] = field(default_factory=list)
    parameterized_urls: list[str] = field(default_factory=list)
    secrets_found: list[str] = field(default_factory=list)
    vulnerabilities: list[dict[str, Any]] = field(default_factory=list)

    def has(self, dataset_key: str) -> bool:
        """Return True when the named field list is non-empty."""
        return bool(getattr(self, dataset_key, None))


@dataclass
class ToolExecutionRecord:
    """One completed tool run, retained for learning / calibration."""
    tool_id: str
    mission_id: str
    executed_at: str          # ISO-8601
    estimated_cost_cents: float
    actual_cost_cents: Optional[float]
    estimated_time_ms: float
    actual_time_ms: Optional[float]
    findings_count: int
    success: bool


@dataclass
class MissionContext:
    """
    Runtime snapshot passed to every IToolAgent.evaluate_bid() call.

    Built from a K1GraphState dict via build_mission_context().
    budget_remaining_cents is float("inf") when the caller sets no budget.
    """
    target: str
    phase: str                              # e.g. "recon", "vuln_scanning"
    goals: list[str]                        # e.g. ["subdomain_enumeration"]
    findings_so_far: FindingDataset
    budget_remaining_cents: float           # float("inf") = unlimited
    time_budget_remaining_ms: float         # float("inf") = unlimited
    execution_history: list[ToolExecutionRecord]
    mission_id: str
    agent_id: str                           # AgentIdentity.agent_id


@dataclass
class ToolBid:
    """A tool's bid to execute in the next selection round."""
    tool_id: str
    confidence: float                       # 0.0 – 1.0; 0.0 = abstain
    estimated_cost_cents: float
    execution_time_estimate_ms: float
    output_schema: dict[str, str]
    dependencies: list[str]                 # FindingDataset keys required
    priority_boost: float                   # multiplier ≥ 1.0
    reasoning: str

    @property
    def bid_score(self) -> float:
        """Higher is better: confidence × (100 / (1 + cost)) × boost."""
        if self.confidence <= 0.0:
            return 0.0
        return self.confidence * (100.0 / (1.0 + self.estimated_cost_cents)) * self.priority_boost

    def within_budget(self, budget_cents: float) -> bool:
        return self.estimated_cost_cents <= budget_cents

    def __repr__(self) -> str:
        return (
            f"ToolBid(tool={self.tool_id!r}, score={self.bid_score:.3f}, "
            f"conf={self.confidence:.2f}, cost={self.estimated_cost_cents}¢, "
            f"boost={self.priority_boost:.2f})"
        )


# --------------------------------------------------------------------------- #
# IToolAgent ABC                                                               #
# --------------------------------------------------------------------------- #

class IToolAgent(ABC):
    """
    Interface every tool-bidding agent must implement.

    The default helpers (_check_dependencies, _compute_base_confidence) cover
    the most common bid logic; override evaluate_bid() for bespoke behaviour.
    """

    @abstractmethod
    def evaluate_bid(self, context: MissionContext) -> ToolBid:
        """Return a bid.  Confidence=0.0 signals that the tool abstains."""
        ...

    def _check_dependencies(
        self,
        deps: list[str],
        findings: FindingDataset,
    ) -> tuple[bool, str]:
        """Return (met, reason).  True only when every dep is non-empty."""
        missing = [d for d in deps if not findings.has(d)]
        if missing:
            return False, f"missing findings: {', '.join(missing)}"
        return True, "all dependencies met"

    def _compute_base_confidence(
        self,
        phase_affinity: list[str],
        current_phase: str,
        phase_mismatch_penalty: float = 0.4,
    ) -> float:
        """0.85 for a matching phase; reduced by penalty for mismatches."""
        if not phase_affinity or current_phase in phase_affinity:
            return 0.85
        return max(0.0, 0.85 - phase_mismatch_penalty)


# --------------------------------------------------------------------------- #
# YAML-configured tool agent                                                   #
# --------------------------------------------------------------------------- #

_YAML_CONFIG: dict[str, Any] = {}
_YAML_LOAD_LOCK = threading.Lock()
_YAML_LOADED = False

# Resolve relative to this file: src/core/ → project root → config/
_DEFAULT_RULES_PATH = (
    Path(__file__).parent.parent.parent.parent.parent / "config" / "tool_bid_rules.yaml"
)


def _load_yaml_config(path: Optional[Path] = None) -> dict[str, Any]:
    global _YAML_CONFIG, _YAML_LOADED
    with _YAML_LOAD_LOCK:
        if _YAML_LOADED and path is None:
            return _YAML_CONFIG
        resolved = path or Path(
            os.getenv("K1_TOOL_BID_RULES", str(_DEFAULT_RULES_PATH))
        )
        try:
            with open(resolved, "r") as fh:
                data = yaml.safe_load(fh) or {}
            if path is None:
                _YAML_CONFIG = data
                _YAML_LOADED = True
            return data
        except FileNotFoundError:
            logger.warning(
                "tool_bid_rules.yaml not found at %s — bidding will use defaults",
                resolved,
            )
        except Exception as exc:
            logger.error("Failed to load tool_bid_rules.yaml: %s", exc)
        if path is None:
            _YAML_CONFIG = {}
            _YAML_LOADED = True
        return {}


def _reset_yaml_cache() -> None:
    """Test helper — forces next call to _load_yaml_config() to re-read disk."""
    global _YAML_LOADED
    with _YAML_LOAD_LOCK:
        _YAML_LOADED = False


class YamlConfiguredToolAgent(IToolAgent):
    """
    Data-driven IToolAgent that reads bidding config from tool_bid_rules.yaml.

    One instance is created per tool_id when no @register() class is present.
    Tests may inject config directly via the config= parameter to avoid I/O.
    """

    def __init__(
        self,
        tool_id: str,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.tool_id = tool_id
        self._cfg: dict[str, Any] = (
            config if config is not None
            else _load_yaml_config().get(tool_id, {})
        )

    def evaluate_bid(self, context: MissionContext) -> ToolBid:
        cfg = self._cfg
        deps: list[str] = cfg.get("dependencies", [])

        # We no longer hard-fail on dependencies here, as BiddingOrchestrator
        # will resolve the DAG to see if other selected tools will provide them.
        deps_met, deps_reason = self._check_dependencies(
            deps, context.findings_so_far
        )
        # We record the reason but do not zero out the confidence yet.
        base_reason = "deps=met" if deps_met else f"deps_missing={deps_reason}"

        phase_affinity: list[str] = cfg.get("phase_affinity", [])
        confidence = self._compute_base_confidence(phase_affinity, context.phase)

        # Already executed in this mission → reduce confidence to avoid repetition.
        already_run = any(
            r.tool_id == self.tool_id for r in context.execution_history
        )
        if already_run:
            confidence *= 0.5

        # Goal-matching → priority boost.
        boost_goals: list[str] = cfg.get("priority_boost_if_goals", [])
        boost = 1.0
        if boost_goals and any(g in context.goals for g in boost_goals):
            boost = float(cfg.get("priority_boost_value", 1.5))

        cost = float(cfg.get("estimated_cost_cents", 0))
        time_ms = float(cfg.get("execution_time_estimate_ms", 30_000))

        parts = [
            "phase=" + ("match" if not phase_affinity or context.phase in phase_affinity else "mismatch"),
            base_reason,
        ]
        if boost > 1.0:
            parts.append(f"goal_boost={boost:.1f}")
        if already_run:
            parts.append("already_run(penalty)")

        return ToolBid(
            tool_id=self.tool_id,
            confidence=round(confidence, 4),
            estimated_cost_cents=cost,
            execution_time_estimate_ms=time_ms,
            output_schema=cfg.get("output_schema", {}),
            dependencies=deps,
            priority_boost=boost,
            reasoning="; ".join(parts),
        )


# --------------------------------------------------------------------------- #
# BiddingOrchestrator                                                          #
# --------------------------------------------------------------------------- #

class BiddingOrchestrator:
    """
    Collects bids from all allowed tools, ranks by bid_score, returns top-N
    tools within the remaining budget.

    Thread-safe: execution history is guarded by a lock.
    """

    def __init__(self, yaml_rules_path: Optional[Path] = None) -> None:
        self._history: list[ToolExecutionRecord] = []
        self._history_lock = threading.Lock()
        self._yaml_path = yaml_rules_path

    # ---------------------------------------------------------------------- #
    # Internal helpers                                                         #
    # ---------------------------------------------------------------------- #

    def _agent_for(self, tool_id: str) -> IToolAgent:
        """Return a bespoke agent if registered, else a YAML-configured one."""
        with _REGISTRY_LOCK:
            cls = _REGISTRY.get(tool_id)
        if cls is not None:
            return cls()
        cfg = _load_yaml_config(self._yaml_path).get(tool_id, {})
        return YamlConfiguredToolAgent(tool_id, config=cfg)

    # ---------------------------------------------------------------------- #
    # Public API                                                               #
    # ---------------------------------------------------------------------- #

    def collect_bids(
        self,
        tool_ids: list[str],
        context: MissionContext,
    ) -> list[ToolBid]:
        """Return one bid per tool, including abstentions (confidence=0.0)."""
        bids: list[ToolBid] = []
        for tool_id in tool_ids:
            try:
                agent = self._agent_for(tool_id)
                bid = agent.evaluate_bid(context)
                logger.debug(
                    "bid tool=%s score=%.3f conf=%.2f reason=%s",
                    tool_id,
                    bid.bid_score,
                    bid.confidence,
                    bid.reasoning,
                )
            except Exception as exc:
                logger.warning("bid evaluation error tool=%s: %s", tool_id, exc)
                bid = ToolBid(
                    tool_id=tool_id,
                    confidence=0.0,
                    estimated_cost_cents=0.0,
                    execution_time_estimate_ms=0.0,
                    output_schema={},
                    dependencies=[],
                    priority_boost=1.0,
                    reasoning=f"error: {exc}",
                )
            bids.append(bid)
        return bids

    def resolve_dag_dependencies(
        self,
        bids: list[ToolBid],
        findings: FindingDataset
    ) -> list[ToolBid]:
        """
        Resolve topological execution order and filter out unsatisfiable tools.
        """
        available_data = set()
        # Pre-populate with existing finding types
        for k in dir(findings):
            if not k.startswith("_") and findings.has(k):
                available_data.add(k)
                
        satisfiable_bids = []
        pending_bids = [b for b in bids if b.confidence > 0.0]
        
        progress = True
        while progress:
            progress = False
            for bid in list(pending_bids):
                # check if all dependencies are in available_data
                if all(dep in available_data for dep in bid.dependencies):
                    satisfiable_bids.append(bid)
                    pending_bids.remove(bid)
                    # add outputs to available_data
                    for output_key in bid.output_schema.keys():
                        available_data.add(output_key)
                    progress = True
                    
        # Update reasoning for rejected bids (optional, but good for logs)
        for rejected in pending_bids:
            logger.debug(f"Tool {rejected.tool_id} rejected due to unsatisfiable dependencies: {rejected.dependencies}")
            
        return satisfiable_bids

    def select_tools(
        self,
        tool_ids: list[str],
        context: MissionContext,
        max_tools: int = 5,
        min_confidence: float = 0.1,
    ) -> list[str]:
        """
        Return up to max_tools tool IDs ranked by bid_score.

        Returns an empty list when all tools abstain (all confidence < min_confidence).
        The caller in praison_agent_runtime.py falls back to preferred_sequences
        in that case.
        """
        bids = self.collect_bids(tool_ids, context)
        
        # Filter through DAG dependency resolver
        satisfiable_bids = self.resolve_dag_dependencies(bids, context.findings_so_far)

        eligible = [
            b for b in satisfiable_bids
            if b.confidence >= min_confidence
            and b.within_budget(context.budget_remaining_cents)
        ]
        ranked = sorted(eligible, key=lambda b: b.bid_score, reverse=True)
        selected = ranked[:max_tools]

        logger.info(
            "bidding: mission=%s agent=%s phase=%s eligible=%d selected=%d tools=%s",
            context.mission_id,
            context.agent_id,
            context.phase,
            len(eligible),
            len(selected),
            [b.tool_id for b in selected],
        )
        return [b.tool_id for b in selected]

    def record_execution(self, record: ToolExecutionRecord) -> None:
        """Append a completed execution record (used for calibration)."""
        with self._history_lock:
            self._history.append(record)

    @property
    def history(self) -> list[ToolExecutionRecord]:
        with self._history_lock:
            return list(self._history)


# --------------------------------------------------------------------------- #
# Context builder                                                              #
# --------------------------------------------------------------------------- #

def _parse_findings(raw_findings: list[Any]) -> FindingDataset:
    """
    Convert the accumulated findings list from K1GraphState into a FindingDataset.

    Finding dicts are heterogeneous; extraction is best-effort by known keys.
    """
    ds = FindingDataset()
    for item in raw_findings or []:
        if not isinstance(item, dict):
            continue
        ftype = item.get("type", "")

        # Subdomains
        if ftype == "subdomain" or "subdomain" in item:
            val = item.get("subdomain") or item.get("value")
            if isinstance(val, str) and val:
                ds.subdomains.append(val)

        # Ports
        if ftype == "port" or "port" in item:
            val = item.get("port")
            if isinstance(val, int):
                ds.open_ports.append(val)

        # Technologies
        if ftype == "technology" or "technology" in item:
            val = item.get("technology") or item.get("value")
            if isinstance(val, str) and val:
                ds.technologies.append(val)

        # URLs — parameterized detection: has both "?" and "="
        if ftype == "url" or "url" in item:
            val = item.get("url") or item.get("value")
            if isinstance(val, str) and val:
                ds.urls_found.append(val)
                if "?" in val and "=" in val:
                    ds.parameterized_urls.append(val)

        # Secrets
        if ftype == "secret" or "secret" in item:
            val = item.get("secret") or item.get("value")
            if isinstance(val, str) and val:
                ds.secrets_found.append(val)

        # Vulnerabilities
        if ftype == "vulnerability" or "vulnerability" in item:
            ds.vulnerabilities.append(item)

    return ds


def build_mission_context(
    state: dict[str, Any],
    agent_id: str,
    execution_history: Optional[list[ToolExecutionRecord]] = None,
) -> MissionContext:
    """
    Build a MissionContext from a K1GraphState dict.

    Args:
        state:             LangGraph state dict (K1GraphState fields).
        agent_id:          AgentIdentity.agent_id (e.g. "SurfaceMapper").
        execution_history: Completed ToolExecutionRecords for calibration.
    """
    phase = (state.get("phase") or "recon").strip().lower()
    goals: list[str] = state.get("goals") or []
    target: str = state.get("target") or ""
    mission_id: str = state.get("mission_id") or ""
    raw_findings: list[Any] = state.get("findings") or []

    budget_raw = state.get("budget_remaining_cents")
    budget_cents = float(budget_raw) if budget_raw is not None else float("inf")

    time_raw = state.get("time_budget_remaining_ms")
    time_ms = float(time_raw) if time_raw is not None else float("inf")

    return MissionContext(
        target=target,
        phase=phase,
        goals=goals if isinstance(goals, list) else [goals],
        findings_so_far=_parse_findings(raw_findings),
        budget_remaining_cents=budget_cents,
        time_budget_remaining_ms=time_ms,
        execution_history=execution_history or [],
        mission_id=mission_id,
        agent_id=agent_id,
    )
