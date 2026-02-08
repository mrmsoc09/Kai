"""
Base Tool Adapter
Abstract base class for all security tool integrations
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCategory(str, Enum):
    """Tool categories"""
    DOMAIN_INFRASTRUCTURE = "domain_infrastructure"
    IDENTITY_EMAIL_CREDENTIAL = "identity_email_credential"
    CODE_METADATA_FILE = "code_metadata_file"
    SPECIALIZED_AUTOMATION = "specialized_automation"
    DARKWEB_THREAT_INTEL = "darkweb_threat_intel"
    OSINT_SPECIALIZED = "osint_specialized"
    VULNERABILITY_SCANNING = "vulnerability_scanning"
    EXPLOIT_VALIDATION = "exploit_validation"


class ToolTier(str, Enum):
    """Tool tier (Community vs Pro)"""
    COMMUNITY = "community"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class CapabilityType(str, Enum):
    """Capability types provided by tools"""
    # Domain & Infrastructure
    SUBDOMAIN_ENUMERATION = "subdomain_enumeration"
    DNS_RECONNAISSANCE = "dns_reconnaissance"
    PORT_SCANNING = "port_scanning"
    WEB_CRAWLING = "web_crawling"
    SSL_TLS_ANALYSIS = "ssl_tls_analysis"
    CLOUD_ASSET_DISCOVERY = "cloud_asset_discovery"

    # Identity & Credentials
    EMAIL_HARVESTING = "email_harvesting"
    USERNAME_ENUMERATION = "username_enumeration"
    BREACH_DATA_SEARCH = "breach_data_search"
    PASSWORD_ANALYSIS = "password_analysis"
    SOCIAL_MEDIA_OSINT = "social_media_osint"

    # Code & Files
    SECRET_SCANNING = "secret_scanning"
    METADATA_EXTRACTION = "metadata_extraction"
    CODE_ANALYSIS = "code_analysis"
    DEPENDENCY_SCANNING = "dependency_scanning"

    # Vulnerability Discovery
    DAST = "dast"  # Dynamic Application Security Testing
    SAST = "sast"  # Static Application Security Testing
    SCA = "sca"    # Software Composition Analysis
    FUZZING = "fuzzing"
    API_SECURITY_TESTING = "api_security_testing"

    # Exploit & Validation
    EXPLOIT_DEVELOPMENT = "exploit_development"
    PAYLOAD_GENERATION = "payload_generation"
    VULNERABILITY_VALIDATION = "vulnerability_validation"


@dataclass
class ToolExecutionResult:
    """Result from tool execution"""
    tool_name: str
    success: bool
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    # Output data
    findings: List[Dict[str, Any]] = field(default_factory=list)
    raw_output: str = ""
    structured_output: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    command_executed: Optional[str] = None
    exit_code: Optional[int] = None
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    # Resource usage
    cost_cents: int = 0
    api_calls_made: int = 0


@dataclass
class ToolCapability:
    """Capability provided by a tool"""
    capability_type: CapabilityType
    confidence: float  # 0.0 - 1.0
    description: str
    tier_required: ToolTier = ToolTier.COMMUNITY


class BaseToolAdapter(ABC):
    """
    Base adapter for all security tools

    Provides unified interface for tool execution, result parsing,
    and capability advertisement.
    """

    def __init__(self):
        """Initialize tool adapter"""
        self.tool_name = self.get_tool_name()
        self.logger = logging.getLogger(f"{__name__}.{self.tool_name}")
        self._available: Optional[bool] = None

    # ========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # ========================================================================

    @abstractmethod
    def get_tool_name(self) -> str:
        """Get tool name"""
        pass

    @abstractmethod
    def get_tool_category(self) -> ToolCategory:
        """Get tool category"""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[ToolCapability]:
        """Get list of capabilities provided by this tool"""
        pass

    @abstractmethod
    async def check_availability(self) -> bool:
        """
        Check if tool is available (installed, configured, etc.)

        Returns:
            bool: True if tool is ready to use
        """
        pass

    @abstractmethod
    async def execute(
        self,
        target: str,
        options: Optional[Dict[str, Any]] = None
    ) -> ToolExecutionResult:
        """
        Execute tool against target

        Args:
            target: Target to scan (domain, IP, URL, etc.)
            options: Tool-specific options

        Returns:
            ToolExecutionResult with findings and metadata
        """
        pass

    # ========================================================================
    # Common Methods - Provided by base class
    # ========================================================================

    async def is_available(self) -> bool:
        """Check if tool is available (cached)"""
        if self._available is None:
            self._available = await self.check_availability()
        return self._available

    def get_tier_available(self) -> ToolTier:
        """
        Get highest tier available for this tool

        Subclasses can override to detect Pro/Enterprise features
        """
        return ToolTier.COMMUNITY

    def has_capability(self, capability_type: CapabilityType) -> bool:
        """Check if tool provides specific capability"""
        return any(cap.capability_type == capability_type for cap in self.get_capabilities())

    def get_capability_confidence(self, capability_type: CapabilityType) -> float:
        """Get confidence score for specific capability"""
        for cap in self.get_capabilities():
            if cap.capability_type == capability_type:
                return cap.confidence
        return 0.0

    def supports_tier(self, tier: ToolTier) -> bool:
        """Check if tool supports specific tier"""
        available_tier = self.get_tier_available()
        tier_order = [ToolTier.COMMUNITY, ToolTier.PRO, ToolTier.ENTERPRISE]
        return tier_order.index(available_tier) >= tier_order.index(tier)

    async def validate_target(self, target: str) -> bool:
        """
        Validate target format

        Subclasses can override for specific validation rules
        """
        if not target or not target.strip():
            return False
        return True

    def parse_output_to_findings(
        self,
        raw_output: str,
        target: str
    ) -> List[Dict[str, Any]]:
        """
        Parse tool output into standardized findings

        Subclasses should override with tool-specific parsing logic

        Returns:
            List of findings in standard format
        """
        return []

    def __repr__(self) -> str:
        """String representation"""
        return f"<{self.__class__.__name__}(tool={self.tool_name}, category={self.get_tool_category()})>"


class CapabilityProvider(ABC):
    """
    Capability Provider Interface

    Groups related tools that provide similar capabilities
    (e.g., Identity Provider, Infrastructure Provider)
    """

    def __init__(self):
        """Initialize capability provider"""
        self.tools: List[BaseToolAdapter] = []
        self.logger = logging.getLogger(f"{__name__}.{self.get_provider_name()}")

    @abstractmethod
    def get_provider_name(self) -> str:
        """Get provider name"""
        pass

    @abstractmethod
    def get_primary_capabilities(self) -> List[CapabilityType]:
        """Get list of primary capabilities provided"""
        pass

    def register_tool(self, tool: BaseToolAdapter):
        """Register tool with this provider"""
        self.tools.append(tool)
        self.logger.info(f"Registered tool: {tool.tool_name}")

    async def get_available_tools(self) -> List[BaseToolAdapter]:
        """Get list of available tools"""
        available = []
        for tool in self.tools:
            if await tool.is_available():
                available.append(tool)
        return available

    async def select_best_tool(
        self,
        capability: CapabilityType,
        tier_required: ToolTier = ToolTier.COMMUNITY
    ) -> Optional[BaseToolAdapter]:
        """
        Select best tool for specific capability

        Args:
            capability: Required capability
            tier_required: Minimum tier required

        Returns:
            Best available tool or None
        """
        available_tools = await self.get_available_tools()

        # Filter by capability and tier
        candidates = [
            tool for tool in available_tools
            if tool.has_capability(capability) and tool.supports_tier(tier_required)
        ]

        if not candidates:
            return None

        # Sort by confidence score
        candidates.sort(
            key=lambda t: t.get_capability_confidence(capability),
            reverse=True
        )

        return candidates[0]

    async def execute_with_best_tool(
        self,
        capability: CapabilityType,
        target: str,
        options: Optional[Dict[str, Any]] = None,
        tier_required: ToolTier = ToolTier.COMMUNITY
    ) -> Optional[ToolExecutionResult]:
        """
        Execute capability using best available tool

        Args:
            capability: Required capability
            target: Target to scan
            options: Execution options
            tier_required: Minimum tier required

        Returns:
            ToolExecutionResult or None if no tool available
        """
        tool = await self.select_best_tool(capability, tier_required)

        if not tool:
            self.logger.warning(
                f"No available tool for capability: {capability} (tier: {tier_required})"
            )
            return None

        self.logger.info(f"Executing {tool.tool_name} for capability: {capability}")

        try:
            result = await tool.execute(target, options)
            return result
        except Exception as e:
            self.logger.error(f"Tool execution failed: {str(e)}")
            return None
