"""
Tool Registry
Central registry for all tool adapters with discovery and selection
"""

import logging
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field

from .base_adapter import (
    BaseToolAdapter,
    CapabilityProvider,
    ToolCategory,
    ToolTier,
    CapabilityType
)

# Import all tool adapters
from .amass_adapter import AmassAdapter
from .subfinder_adapter import SubfinderAdapter
from .nuclei_adapter import NucleiAdapter
from .trufflehog_adapter import TruffleHogAdapter

logger = logging.getLogger(__name__)


@dataclass
class ToolRegistryStats:
    """Statistics about registered tools"""
    total_tools: int = 0
    available_tools: int = 0
    unavailable_tools: int = 0
    by_category: Dict[str, int] = field(default_factory=dict)
    by_tier: Dict[str, int] = field(default_factory=dict)
    by_capability: Dict[str, int] = field(default_factory=dict)


class ToolRegistry:
    """
    Central registry for all tool adapters

    Manages tool discovery, availability checking, and intelligent
    tool selection based on capabilities and requirements.
    """

    def __init__(self):
        """Initialize tool registry"""
        self.tools: Dict[str, BaseToolAdapter] = {}
        self.tools_by_category: Dict[ToolCategory, List[BaseToolAdapter]] = {}
        self.tools_by_capability: Dict[CapabilityType, List[BaseToolAdapter]] = {}
        self.capability_providers: Dict[str, CapabilityProvider] = {}
        self._initialized = False

        logger.info("ToolRegistry initialized")

    async def initialize(self):
        """
        Initialize registry and discover available tools

        This should be called at application startup
        """
        if self._initialized:
            logger.warning("ToolRegistry already initialized")
            return

        logger.info("Discovering and registering tools...")

        # Register all tool adapters
        self._register_core_tools()

        # Check availability of all tools
        await self._check_all_availability()

        # Build indexes
        self._build_indexes()

        self._initialized = True

        # Log summary
        stats = await self.get_stats()
        logger.info(f"Tool registry initialized:")
        logger.info(f"  Total tools: {stats.total_tools}")
        logger.info(f"  Available: {stats.available_tools}")
        logger.info(f"  Unavailable: {stats.unavailable_tools}")

    def _register_core_tools(self):
        """Register all core tool adapters"""

        # Domain & Infrastructure Tools
        self.register_tool(AmassAdapter())
        self.register_tool(SubfinderAdapter())

        # Vulnerability Scanning Tools
        self.register_tool(NucleiAdapter())

        # Code & Secret Scanning Tools
        self.register_tool(TruffleHogAdapter())

        # NOTE: Extend this registry incrementally as additional adapters are onboarded.
        # self.register_tool(ShodanAdapter())
        # self.register_tool(TheHarvesterAdapter())
        # self.register_tool(MassDNSAdapter())
        # self.register_tool(SubfinderAdapter())
        # self.register_tool(FFUFAdapter())
        # self.register_tool(GoWitnessAdapter())
        # self.register_tool(GitLeaksAdapter())
        # self.register_tool(SemgrepAdapter())
        # ... etc

    def register_tool(self, tool: BaseToolAdapter):
        """
        Register a tool adapter

        Args:
            tool: Tool adapter instance
        """
        tool_name = tool.get_tool_name()

        if tool_name in self.tools:
            logger.warning(f"Tool {tool_name} already registered, replacing...")

        self.tools[tool_name] = tool
        logger.debug(f"Registered tool: {tool_name}")

    async def _check_all_availability(self):
        """Check availability of all registered tools"""
        logger.info(f"Checking availability of {len(self.tools)} tools...")

        for tool_name, tool in self.tools.items():
            try:
                is_available = await tool.is_available()
                if is_available:
                    tier = tool.get_tier_available()
                    logger.info(f"✓ {tool_name} available (tier: {tier.value})")
                else:
                    logger.warning(f"✗ {tool_name} not available")
            except Exception as e:
                logger.error(f"Error checking {tool_name}: {str(e)}")

    def _build_indexes(self):
        """Build search indexes for fast tool lookup"""

        # Clear existing indexes
        self.tools_by_category.clear()
        self.tools_by_capability.clear()

        # Index by category
        for tool in self.tools.values():
            category = tool.get_tool_category()
            if category not in self.tools_by_category:
                self.tools_by_category[category] = []
            self.tools_by_category[category].append(tool)

        # Index by capability
        for tool in self.tools.values():
            for capability in tool.get_capabilities():
                cap_type = capability.capability_type
                if cap_type not in self.tools_by_capability:
                    self.tools_by_capability[cap_type] = []
                self.tools_by_capability[cap_type].append(tool)

        logger.debug(f"Built indexes: {len(self.tools_by_category)} categories, "
                    f"{len(self.tools_by_capability)} capabilities")

    def get_tool(self, tool_name: str) -> Optional[BaseToolAdapter]:
        """Get tool by name"""
        return self.tools.get(tool_name)

    def get_tools_by_category(self, category: ToolCategory) -> List[BaseToolAdapter]:
        """Get all tools in a specific category"""
        return self.tools_by_category.get(category, [])

    def get_tools_by_capability(self, capability: CapabilityType) -> List[BaseToolAdapter]:
        """Get all tools providing a specific capability"""
        return self.tools_by_capability.get(capability, [])

    async def get_available_tools(
        self,
        category: Optional[ToolCategory] = None,
        capability: Optional[CapabilityType] = None,
        tier: Optional[ToolTier] = None
    ) -> List[BaseToolAdapter]:
        """
        Get available tools matching criteria

        Args:
            category: Filter by category
            capability: Filter by capability
            tier: Minimum tier required

        Returns:
            List of available tools matching criteria
        """
        # Start with all tools
        candidates = list(self.tools.values())

        # Filter by category
        if category:
            candidates = [t for t in candidates if t.get_tool_category() == category]

        # Filter by capability
        if capability:
            candidates = [t for t in candidates if t.has_capability(capability)]

        # Filter by tier
        if tier:
            candidates = [t for t in candidates if t.supports_tier(tier)]

        # Filter by availability
        available = []
        for tool in candidates:
            if await tool.is_available():
                available.append(tool)

        return available

    async def select_best_tool(
        self,
        capability: CapabilityType,
        tier: ToolTier = ToolTier.COMMUNITY
    ) -> Optional[BaseToolAdapter]:
        """
        Select best available tool for a capability

        Args:
            capability: Required capability
            tier: Minimum tier required

        Returns:
            Best tool or None if no tools available
        """
        tools = await self.get_available_tools(capability=capability, tier=tier)

        if not tools:
            logger.warning(f"No available tools for capability: {capability} (tier: {tier})")
            return None

        # Sort by confidence score
        tools.sort(
            key=lambda t: t.get_capability_confidence(capability),
            reverse=True
        )

        best_tool = tools[0]
        logger.info(f"Selected {best_tool.tool_name} for {capability} "
                   f"(confidence: {best_tool.get_capability_confidence(capability)})")

        return best_tool

    async def get_stats(self) -> ToolRegistryStats:
        """Get registry statistics"""
        stats = ToolRegistryStats()

        stats.total_tools = len(self.tools)

        # Count available/unavailable
        for tool in self.tools.values():
            if await tool.is_available():
                stats.available_tools += 1
            else:
                stats.unavailable_tools += 1

        # Count by category
        for category, tools in self.tools_by_category.items():
            stats.by_category[category.value] = len(tools)

        # Count by tier
        for tool in self.tools.values():
            if await tool.is_available():
                tier = tool.get_tier_available()
                stats.by_tier[tier.value] = stats.by_tier.get(tier.value, 0) + 1

        # Count by capability
        for capability, tools in self.tools_by_capability.items():
            # Count only available tools
            available_count = 0
            for tool in tools:
                if await tool.is_available():
                    available_count += 1
            stats.by_capability[capability.value] = available_count

        return stats

    def list_all_tools(self) -> List[str]:
        """Get list of all registered tool names"""
        return list(self.tools.keys())

    def list_all_capabilities(self) -> List[CapabilityType]:
        """Get list of all available capabilities"""
        return list(self.tools_by_capability.keys())


# ============================================================================
# Global Registry Instance
# ============================================================================

_registry: Optional[ToolRegistry] = None


def get_tool_registry() -> ToolRegistry:
    """Get global tool registry instance"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


async def initialize_tool_registry() -> ToolRegistry:
    """
    Initialize global tool registry

    Should be called at application startup
    """
    registry = get_tool_registry()
    await registry.initialize()
    return registry
