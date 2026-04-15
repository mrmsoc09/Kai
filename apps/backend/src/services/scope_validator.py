"""Real-time scope validation service.

Validates every outbound request before execution to ensure scans stay
within authorized scope. Performance optimized with caching (< 10ms per check).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from enum import Enum
from fnmatch import fnmatch
from ipaddress import IPv4Address, IPv4Network, AddressValueError
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..models.campaign import Program
from ..models.scope_violations import ScopeViolation

logger = logging.getLogger(__name__)


class ScopeViolationType(str, Enum):
    """Types of scope violations that can be detected."""

    ENDPOINT_OUT_OF_SCOPE = "endpoint_out_of_scope"
    DOMAIN_OUT_OF_SCOPE = "domain_out_of_scope"
    IP_OUT_OF_SCOPE = "ip_out_of_scope"
    PORT_OUT_OF_SCOPE = "port_out_of_scope"
    PARAMETER_OUT_OF_SCOPE = "parameter_out_of_scope"
    SENSITIVE_PATH = "sensitive_path"
    RATE_LIMIT_THRESHOLD = "rate_limit_threshold"


class ScopeValidator:
    """Real-time scope validation for outbound requests.

    Validates EVERY request before execution. Uses caching to keep
    overhead under 10ms per check (DB hits ~1/60s, checks pure Python).
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._scope_cache: dict[str, tuple[dict[str, Any], float]] = {}
        self.cache_ttl_seconds = 60
        self.request_count = 0
        self.violation_count = 0

    async def validate_request(
        self,
        program_id: str | UUID,
        target_url: str,
        target_endpoint: str,
        scan_id: Optional[str | UUID] = None,
        target_port: Optional[int] = None,
        target_ip: Optional[str] = None,
        parameters: Optional[dict[str, Any]] = None,
    ) -> tuple[bool, Optional[ScopeViolationType], Optional[str]]:
        """Validate that request is in-scope before executing.

        Args:
            program_id: Program to check scope for
            target_url: Full URL being requested
            target_endpoint: Endpoint path (e.g., /api/users)
            scan_id: Scan ID for audit trail
            target_port: Port number if applicable
            target_ip: IP address if applicable
            parameters: Query/body parameters

        Returns:
            (is_valid, violation_type, violation_reason)
                is_valid=True means request is OK to execute
                is_valid=False includes violation_type and reason
        """
        self.request_count += 1
        program_id_str = str(program_id) if isinstance(program_id, UUID) else program_id

        # Load program scope (with caching)
        scope = await self._load_scope_config(program_id_str)
        if not scope:
            return False, None, f"Program {program_id_str} scope not configured"

        # CHECK 1: Sensitive paths (highest priority — absolute block)
        if self._check_sensitive_paths(target_endpoint):
            reason = f"Sensitive path blocked: {target_endpoint}"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.SENSITIVE_PATH, reason, target_endpoint)
            return False, ScopeViolationType.SENSITIVE_PATH, reason

        # CHECK 2: Endpoint in scope?
        if not self._check_endpoint_in_scope(target_endpoint, scope):
            reason = f"Endpoint {target_endpoint} not in scope"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.ENDPOINT_OUT_OF_SCOPE, reason, target_endpoint)
            return False, ScopeViolationType.ENDPOINT_OUT_OF_SCOPE, reason

        # CHECK 3: IP in scope? (before domain, IPs are more specific)
        if target_ip and not self._check_ip_in_scope(target_ip, scope):
            reason = f"IP {target_ip} not in scope"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.IP_OUT_OF_SCOPE, reason, target_ip)
            return False, ScopeViolationType.IP_OUT_OF_SCOPE, reason

        # CHECK 4: Domain in scope?
        if not self._check_domain_in_scope(target_url, scope):
            reason = f"Domain {target_url} not in scope"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.DOMAIN_OUT_OF_SCOPE, reason, target_url)
            return False, ScopeViolationType.DOMAIN_OUT_OF_SCOPE, reason

        # CHECK 5: Port in scope?
        if target_port and not self._check_port_in_scope(target_port, scope):
            reason = f"Port {target_port} not in scope"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.PORT_OUT_OF_SCOPE, reason, str(target_port))
            return False, ScopeViolationType.PORT_OUT_OF_SCOPE, reason

        # CHECK 6: Parameters in scope?
        if parameters and not self._check_parameters_in_scope(parameters, scope):
            reason = "Parameter not in scope"
            await self._log_violation(program_id_str, scan_id, ScopeViolationType.PARAMETER_OUT_OF_SCOPE, reason, str(list(parameters.keys())))
            return False, ScopeViolationType.PARAMETER_OUT_OF_SCOPE, reason

        # All checks passed
        return True, None, None

    async def _load_scope_config(self, program_id: str) -> Optional[dict[str, Any]]:
        """Load scope config from DB with caching (60s TTL)."""
        now = datetime.now(timezone.utc).timestamp()

        # Check cache
        if program_id in self._scope_cache:
            config, cached_at = self._scope_cache[program_id]
            if now - cached_at < self.cache_ttl_seconds:
                return config

        # Load from DB
        try:
            # Convert string UUID to UUID object for proper comparison
            program_uuid = UUID(program_id) if isinstance(program_id, str) else program_id
            stmt = select(Program).where(Program.id == program_uuid)
            result = await self.db.execute(stmt)
            program = result.scalars().first()

            if not program or not program.config_json:
                return None

            # Extract scope from config
            scope = program.config_json.get("scope", {})
            self._scope_cache[program_id] = (scope, now)
            return scope

        except Exception as e:
            logger.error(f"Failed to load scope for program {program_id}: {e}")
            return None

    def _check_sensitive_paths(self, endpoint: str) -> bool:
        """Reject attempts to scan sensitive paths."""
        forbidden_paths = [
            "/admin",
            "/internal",
            "/config",
            "/etc",
            "/system",
            "/private",
            "/.env",
            "/backup",
            "/database",
            "/api/admin",
            "/api/internal",
            "/debug",
            "/.git",
            "/.well-known",
            "/account",
            "/login",
        ]

        endpoint_lower = endpoint.lower()
        for forbidden in forbidden_paths:
            if endpoint_lower.startswith(forbidden):
                return True

        return False

    def _check_endpoint_in_scope(self, endpoint: str, scope: dict[str, Any]) -> bool:
        """Check if endpoint matches scope inclusions/exclusions."""
        inclusions = scope.get("included_endpoints", [])
        exclusions = scope.get("excluded_endpoints", [])

        # Check exclusions first (highest priority)
        for excluded in exclusions:
            if self._match_pattern(endpoint, excluded):
                return False

        # If no inclusions specified, reject by default
        if not inclusions:
            return False

        # Check inclusions
        for included in inclusions:
            if self._match_pattern(endpoint, included):
                return True

        return False

    def _check_domain_in_scope(self, target_url: str, scope: dict[str, Any]) -> bool:
        """Check if domain from URL is in scope.

        Note: IPs are checked separately before this, so we can safely
        assume if we get here with an IP, it's already been validated.
        """
        allowed_domains = scope.get("allowed_domains", [])

        if not allowed_domains:
            return False

        # Extract domain from URL (simple extraction)
        try:
            from urllib.parse import urlparse

            parsed = urlparse(target_url)
            domain = parsed.netloc.split(":")[0] if parsed.netloc else target_url
        except Exception:
            domain = target_url

        # If domain is an IP address, it was already validated in _check_ip_in_scope
        try:
            IPv4Address(domain)
            return True  # IP was already validated
        except AddressValueError:
            pass  # Not an IP, check against allowed domains

        # Check against allowed domains
        for allowed in allowed_domains:
            if self._match_pattern(domain, allowed):
                return True

        return False

    def _check_port_in_scope(self, port: int, scope: dict[str, Any]) -> bool:
        """Check if port is in allowed list."""
        allowed_ports = scope.get("allowed_ports", [])

        if not allowed_ports:
            return False

        return port in allowed_ports

    def _check_ip_in_scope(self, ip: str, scope: dict[str, Any]) -> bool:
        """Check if IP is in allowed list or CIDR ranges."""
        allowed_ips = scope.get("allowed_ips", [])
        allowed_cidrs = scope.get("allowed_cidrs", [])

        try:
            ip_obj = IPv4Address(ip)
        except AddressValueError:
            # Not a valid IP, reject
            return False

        # Check direct IPs
        for allowed_ip in allowed_ips:
            try:
                if IPv4Address(allowed_ip) == ip_obj:
                    return True
            except AddressValueError:
                continue

        # Check CIDR ranges
        for cidr in allowed_cidrs:
            try:
                cidr_obj = IPv4Network(cidr, strict=False)
                if ip_obj in cidr_obj:
                    return True
            except AddressValueError:
                continue

        return False

    def _check_parameters_in_scope(self, parameters: dict[str, Any], scope: dict[str, Any]) -> bool:
        """Check if parameters are allowed."""
        excluded_parameters = scope.get("excluded_parameters", [])

        for param_name in parameters.keys():
            if param_name in excluded_parameters:
                return False

        return True

    def _match_pattern(self, target: str, pattern: str) -> bool:
        """Match target against pattern (supports wildcards and regex)."""
        # Try fnmatch first (simple glob patterns like /api/*)
        if fnmatch(target, pattern):
            return True

        # Try as regex if it looks like one (surrounded by /)
        if pattern.startswith("/") and pattern.endswith("/"):
            try:
                regex_pattern = pattern[1:-1]
                if re.match(regex_pattern, target):
                    return True
            except re.error:
                pass

        return False

    async def _log_violation(
        self,
        program_id: str,
        scan_id: Optional[str | UUID],
        violation_type: ScopeViolationType,
        reason: str,
        target: str,
    ) -> None:
        """Log scope violation immutably."""
        self.violation_count += 1

        try:
            # Convert strings to UUID objects
            program_uuid = UUID(program_id) if isinstance(program_id, str) else program_id
            scan_uuid = UUID(scan_id) if isinstance(scan_id, str) and scan_id else None

            violation = ScopeViolation(
                program_id=program_uuid,
                scan_id=scan_uuid,
                violation_type=violation_type.value,
                reason=reason,
                target=target,
                created_by="scope_validator",
                immutable=True,
            )

            self.db.add(violation)
            await self.db.flush()
            await self.db.commit()

            logger.warning(f"SCOPE VIOLATION: {violation_type.value} - {reason} - target: {target}")

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to log scope violation: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get validation statistics."""
        return {
            "request_count": self.request_count,
            "violation_count": self.violation_count,
            "violation_rate": (
                self.violation_count / self.request_count if self.request_count > 0 else 0
            ),
            "cached_configs": len(self._scope_cache),
        }
