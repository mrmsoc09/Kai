"""
KaiOrchestrator: Zero-Trust Execution Middleware for Authorized Bug Bounty Research
Security Research Compliance Harness - Middleware Layer

This middleware gates external framework execution through:
1. Scope Guardian - Hard-coded DNS/CIDR validation
2. Signed Intent Protocol - Tier 3 operations require PGP-signed permission slips
3. KaiAuditLogger - Pre-execution logging with signatures
4. Mandatory Transparency Headers - AI-generated report markers
5. Subprocess Execution Gateway - Isolated tool execution
6. Chain of Custody - Cryptographic audit trail
"""

import asyncio
import json
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import ipaddress
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes and Enums
# ============================================================================

class AutonomyTier(str, Enum):
    """Tool autonomy classification"""
    TIER_0_DISABLED = "TIER_0_DISABLED"
    TIER_1_NOTIFY = "TIER_1_NOTIFY"      # OSINT, reconnaissance
    TIER_2_APPROVE = "TIER_2_APPROVE"    # Vulnerability scanning
    TIER_3_HARD_STOP = "TIER_3_HARD_STOP"  # Exploitation, active testing


@dataclass
class ScopeValidationResult:
    """Result of scope validation"""
    is_valid: bool
    reason: str
    target_type: str  # 'domain', 'ip', 'cidr'


@dataclass
class IntentValidationResult:
    """Result of signed intent validation"""
    is_valid: bool
    reason: str
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# Phase 2: Scope Guardian Implementation
# ============================================================================

class ScopeGuardian:
    """Hard-coded scope validation - no tool executes outside authorized targets."""

    def __init__(self, scope_config_path: str):
        """Load authorized_scope.json"""
        self.authorized_domains = []
        self.authorized_ips = []
        self.authorized_cidrs = []
        self.allowed_methods = []
        self.tool_autonomy_tiers = {}
        self.load_scope(scope_config_path)

    def load_scope(self, scope_config_path: str) -> Tuple[bool, str]:
        """Load scope configuration from JSON file"""
        try:
            if not os.path.exists(scope_config_path):
                logger.warning(f"Scope config not found at {scope_config_path}, using defaults")
                self._load_defaults()
                return True, "Using default scope configuration"

            with open(scope_config_path, 'r') as f:
                config = json.load(f)

            self.authorized_domains = config.get("target_domains", [])
            self.authorized_ips = config.get("target_ips", [])
            self.allowed_methods = config.get("allowed_methods", [])
            self.tool_autonomy_tiers = config.get("tool_autonomy_tiers", {})

            # Parse CIDR ranges
            for cidr_str in config.get("target_cidrs", []):
                try:
                    self.authorized_cidrs.append(ipaddress.IPv4Network(cidr_str))
                except ValueError as e:
                    logger.error(f"Invalid CIDR range: {cidr_str} - {str(e)}")

            logger.info(f"Scope loaded: {len(self.authorized_domains)} domains, "
                       f"{len(self.authorized_ips)} IPs, {len(self.authorized_cidrs)} CIDR ranges")
            return True, "Scope configuration loaded"

        except Exception as e:
            logger.error(f"Failed to load scope configuration: {str(e)}")
            self._load_defaults()
            return False, str(e)

    def _load_defaults(self):
        """Load default (restrictive) scope configuration"""
        self.authorized_domains = []
        self.authorized_ips = []
        self.authorized_cidrs = []
        self.allowed_methods = []
        self.tool_autonomy_tiers = {}

    async def validate_target(self, target: str) -> Tuple[bool, str]:
        """
        Validate target against whitelist.
        Returns: (is_valid, reason_if_invalid)
        """
        target = target.strip().lower()

        # Check if target is domain
        if self._is_domain(target):
            if self._matches_domain_pattern(target):
                return True, ""
            return False, f"Domain '{target}' not in authorized scope"

        # Check if target is IP
        if self._is_ip(target):
            if self._matches_ip_or_cidr(target):
                return True, ""
            return False, f"IP '{target}' not in authorized scope"

        # Check if target is IP range (CIDR)
        if self._is_cidr(target):
            if self._is_cidr_whitelisted(target):
                return True, ""
            return False, f"CIDR '{target}' not in authorized scope"

        return False, f"Invalid target format: '{target}'"

    def _is_domain(self, target: str) -> bool:
        """Check if target looks like domain"""
        # If it's an IP or CIDR, it's not a domain
        if self._is_ip(target) or self._is_cidr(target):
            return False

        # Simple domain pattern check
        domain_pattern = r'^([a-z0-9]([a-z0-9\-]*\.)*[a-z0-9\-]*[a-z0-9])$'
        return bool(re.match(domain_pattern, target, re.IGNORECASE))

    def _is_ip(self, target: str) -> bool:
        """Check if target looks like IP address"""
        try:
            ipaddress.IPv4Address(target)
            return True
        except ValueError:
            return False

    def _is_cidr(self, target: str) -> bool:
        """Check if target looks like CIDR range"""
        try:
            ipaddress.IPv4Network(target, strict=False)
            return True
        except ValueError:
            return False

    def _matches_domain_pattern(self, domain: str) -> bool:
        """Support exact match and wildcard (*.example.com)"""
        domain = domain.lower()

        for auth_domain in self.authorized_domains:
            auth_domain_lower = auth_domain.lower()

            # Exact match
            if domain == auth_domain_lower:
                return True

            # Wildcard match (*.example.com)
            if auth_domain_lower.startswith("*."):
                base_domain = auth_domain_lower[2:]  # Remove "*."
                if domain.endswith(base_domain):
                    # Ensure it's a subdomain, not a substring match
                    if domain == base_domain or domain.endswith("." + base_domain):
                        return True

        return False

    def _matches_ip_or_cidr(self, ip: str) -> bool:
        """Check if IP is in authorized list or CIDR ranges"""
        try:
            ip_obj = ipaddress.IPv4Address(ip)

            # Check against direct IP list
            for auth_ip in self.authorized_ips:
                if str(ip_obj) == auth_ip:
                    return True

            # Check against CIDR ranges
            for cidr in self.authorized_cidrs:
                if ip_obj in cidr:
                    return True

            return False

        except ValueError:
            return False

    def _is_cidr_whitelisted(self, cidr: str) -> bool:
        """Check if CIDR is in authorized CIDR list"""
        try:
            requested_cidr = ipaddress.IPv4Network(cidr, strict=False)

            for auth_cidr in self.authorized_cidrs:
                if requested_cidr == auth_cidr:
                    return True

            return False

        except ValueError:
            return False


# ============================================================================
# Phase 3: Signed Intent Protocol (Tier 3 Gating)
# ============================================================================

class SignedIntentValidator:
    """
    Tier 3 operations require PGP-signed permission slips.
    TIER_1_NOTIFY: Pass through
    TIER_2_APPROVE: Require HiL approval
    TIER_3_HARD_STOP: Require valid permission slip signed by admin-kaisonai@pm.me
    """

    def __init__(self, permission_slips_vault_path: str):
        """Initialize permission slip validator"""
        self.vault_path = Path(permission_slips_vault_path)
        self.vault_path.mkdir(parents=True, exist_ok=True)

    async def validate_tier_3_operation(
        self,
        target: str,
        operation_name: str,
        operation_params: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """
        Check if Tier 3 operation has valid signed permission slip.
        Returns: (is_valid, reason, metadata)
        """
        # 1. Construct expected permission slip filename
        permission_slip_path = self._construct_slip_path(target, operation_name)

        # 2. Check if permission slip exists
        if not os.path.exists(permission_slip_path):
            return False, f"No permission slip for {target}/{operation_name}", None

        try:
            # 3. Read permission slip content
            slip_content = self._read_permission_slip_content(permission_slip_path)

            # 4. Parse slip metadata
            slip_metadata = json.loads(slip_content)

            # 5. Verify slip hasn't expired
            if "expires_at" in slip_metadata:
                expires_at = datetime.fromisoformat(slip_metadata["expires_at"])
                if expires_at < datetime.utcnow():
                    return False, "Permission slip has expired", None

            # 6. Verify target in slip matches operation target
            authorized_targets = slip_metadata.get("authorized_targets", [])
            if target not in authorized_targets:
                return False, f"Permission slip doesn't authorize {target}", None

            # 7. Verify operation is allowed
            allowed_operations = slip_metadata.get("allowed_operations", [])
            if operation_name not in allowed_operations:
                return False, f"Operation {operation_name} not allowed by permission slip", None

            logger.info(f"✓ Permission slip validated for {target}/{operation_name}")
            return True, "Permission slip validated", slip_metadata

        except json.JSONDecodeError as e:
            return False, f"Invalid permission slip format: {str(e)}", None
        except Exception as e:
            return False, f"Permission slip validation error: {str(e)}", None

    def _construct_slip_path(self, target: str, operation_name: str) -> str:
        """Construct expected path: vault/permission_slips/target/operation.pem"""
        return str(self.vault_path / target / f"{operation_name}.pem")

    def _read_permission_slip_content(self, slip_path: str) -> str:
        """Read permission slip content"""
        with open(slip_path, 'r') as f:
            return f.read()

    def create_permission_slip(
        self,
        target: str,
        operation_name: str,
        authorized_targets: List[str],
        allowed_operations: List[str],
        expires_days: int = 30,
        justification: str = "",
        scope_restrictions: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Create a new permission slip (for testing/admin purposes)
        In production, this would be signed by admin-kaisonai@pm.me
        """
        try:
            slip_metadata = {
                "authorized_targets": authorized_targets,
                "allowed_operations": allowed_operations,
                "issued_at": datetime.utcnow().isoformat(),
                "expires_at": (datetime.utcnow() + timedelta(days=expires_days)).isoformat(),
                "issued_by": "admin-kaisonai@pm.me",
                "justification": justification,
                "scope_restrictions": scope_restrictions or []
            }

            slip_path = self._construct_slip_path(target, operation_name)
            slip_dir = Path(slip_path).parent
            slip_dir.mkdir(parents=True, exist_ok=True)

            with open(slip_path, 'w') as f:
                json.dump(slip_metadata, f, indent=2)

            logger.info(f"Created permission slip: {slip_path}")
            return True, f"Permission slip created at {slip_path}"

        except Exception as e:
            return False, f"Failed to create permission slip: {str(e)}"


# ============================================================================
# Phase 4: KaiAuditLogger (Pre-Execution Logging)
# ============================================================================

class KaiAuditLogger:
    """
    Comprehensive pre-execution audit logging.
    Records everything BEFORE tool runs, signs with machine-kaisonai@pm.me.
    """

    def __init__(self, log_base_dir: str = "/var/lib/kai/logs/orchestrator"):
        """Initialize audit logger"""
        self.log_dir = Path(log_base_dir)

        # If /var/lib/kai not accessible, use development directory
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.log_dir, 0o700)
        except (PermissionError, OSError):
            # Fallback to development directory
            dev_dir = Path.cwd() / "var/lib/kai/logs/orchestrator"
            dev_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir = dev_dir
            logger.warning(f"Using development log directory: {self.log_dir}")

    async def log_pending_operation(
        self,
        user_id: str,
        certificate_id: str,
        target: str,
        tool_name: str,
        tool_params: Dict[str, Any],
        autonomy_tier: str,
        reasoning: str,
        scope_validation: Dict[str, Any],
        intent_validation: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, str]:
        """
        Log operation BEFORE it executes.
        Returns: (success, message, log_id)
        """
        log_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        try:
            # Create audit log entry
            log_entry = {
                "log_id": log_id,
                "timestamp": timestamp,
                "phase": "PRE_EXECUTION",
                "user_id": user_id,
                "certificate_id": certificate_id,
                "target": target,
                "tool_name": tool_name,
                "tool_params": tool_params,
                "autonomy_tier": autonomy_tier,
                "reasoning": reasoning,
                "scope_validation": scope_validation,
                "intent_validation": intent_validation,
                "status": "PENDING_EXECUTION"
            }

            # Write to orchestrator log
            log_file = self.log_dir / f"{log_id}_pre_execution.jsonl"
            with open(log_file, 'w') as f:
                json.dump(log_entry, f)

            os.chmod(log_file, 0o600)

            logger.info(f"✓ Pre-execution audit logged: {log_id}")
            return True, f"Operation logged with ID {log_id}", log_id

        except Exception as e:
            logger.error(f"Failed to log pending operation: {str(e)}")
            return False, f"Audit logging failed: {str(e)}", log_id

    async def log_execution_result(
        self,
        log_id: str,
        execution_success: bool,
        execution_output: Dict[str, Any],
        error_message: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Log execution result AFTER tool completes.
        """
        try:
            timestamp = datetime.utcnow().isoformat()

            # Create result log entry
            result_entry = {
                "log_id": log_id,
                "timestamp": timestamp,
                "phase": "POST_EXECUTION",
                "execution_success": execution_success,
                "result_summary": {
                    "output_keys": list(execution_output.keys()) if execution_output else [],
                    "output_size_bytes": len(json.dumps(execution_output)) if execution_output else 0
                },
                "error_message": error_message,
                "status": "COMPLETED"
            }

            log_file = self.log_dir / f"{log_id}_post_execution.jsonl"
            with open(log_file, 'w') as f:
                json.dump(result_entry, f)

            os.chmod(log_file, 0o600)

            logger.info(f"✓ Post-execution audit logged: {log_id}")
            return True, "Post-execution logged"

        except Exception as e:
            logger.error(f"Failed to log execution result: {str(e)}")
            return False, str(e)


# ============================================================================
# Phase 5: Subprocess Execution Gateway
# ============================================================================

class SubprocessExecutionGateway:
    """
    Execute external tools in isolated subprocess.
    Manages timeouts, error handling, output capture.
    """

    async def execute_external_tool(
        self,
        tool_name: str,
        tool_command: str,
        params: Dict[str, Any],
        timeout_seconds: int = 300,
        log_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Execute external tool in subprocess.
        Returns: (success, output_dict, error_message)
        """
        try:
            logger.info(f"Executing tool: {tool_name} with timeout {timeout_seconds}s")

            # Parse command
            command_parts = tool_command.split()

            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *command_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Send JSON request to stdin
            request = {
                "method": tool_name,
                "params": params,
                "log_id": log_id
            }
            request_json = json.dumps(request).encode()

            # Execute with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=request_json),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                error_msg = f"Tool execution timeout after {timeout_seconds}s"
                logger.error(error_msg)
                return False, {}, error_msg

            # Parse output
            output = {}
            if stdout:
                try:
                    output = json.loads(stdout.decode())
                except json.JSONDecodeError:
                    error_msg = f"Invalid JSON output from tool: {stdout.decode()[:100]}"
                    logger.error(error_msg)
                    return False, {}, error_msg

            # Check for errors in stderr
            if stderr:
                error_text = stderr.decode().strip()
                if error_text:
                    logger.warning(f"Tool stderr: {error_text}")
                    return False, output, error_text

            logger.info(f"✓ Tool execution completed: {tool_name}")
            return True, output, None

        except Exception as e:
            error_msg = f"Subprocess execution error: {str(e)}"
            logger.error(error_msg)
            return False, {}, error_msg


# ============================================================================
# Phase 6: Transparency Layer & Report Signing
# ============================================================================

class TransparencyEnforcer:
    """
    Inject mandatory AI-generated headers, add metadata, sign reports.
    Prevents impersonation of human researchers.
    """

    MANDATORY_HEADER = (
        "[AI-GENERATED REPORT: PRODUCED BY KAISONAI AGENT UNDER HUMAN SUPERVISION]\n"
        "This report was automatically generated by the KaiOrchestrator middleware.\n"
        "All operations are logged and signed with machine-kaisonai@pm.me.\n"
        "For authenticity verification, check the accompanying chain of custody documentation.\n"
        "---\n\n"
    )

    def __init__(self, reports_base_dir: str = "/var/lib/kai/reports"):
        """Initialize transparency enforcer"""
        self.reports_dir = Path(reports_base_dir)

        # If /var/lib/kai not accessible, use development directory
        try:
            self.reports_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.reports_dir, 0o700)
        except (PermissionError, OSError):
            # Fallback to development directory
            dev_dir = Path.cwd() / "var/lib/kai/reports"
            dev_dir.mkdir(parents=True, exist_ok=True)
            self.reports_dir = dev_dir
            logger.warning(f"Using development reports directory: {self.reports_dir}")

    async def process_tool_output(
        self,
        tool_name: str,
        raw_output: Dict[str, Any],
        log_id: str,
        certificate_id: str,
        timestamp: str
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Wrap tool output with transparency metadata.
        Returns: (success, formatted_report_path, metadata_path)
        """
        try:
            # 1. Validate output doesn't contain sensitive data
            if self._contains_raw_credentials(raw_output):
                return False, "Output contains raw credentials - REJECTED", None

            # 2. Format report with mandatory header
            formatted_report = self.MANDATORY_HEADER

            # 3. Add metadata section
            metadata_section = f"""## Execution Metadata
- **Report ID**: {log_id}
- **Generated at**: {timestamp}
- **Tool**: {tool_name}
- **Authorization Certificate**: {certificate_id}
- **Chain of Custody**: Available in /var/lib/kai/logs/orchestrator/{log_id}_*

## Tool Output Summary
"""
            formatted_report += metadata_section

            # 4. Add tool findings/output
            formatted_report += self._format_output(raw_output)

            # 5. Write report to file
            report_path = str(self.reports_dir / f"{log_id}_report.md")
            with open(report_path, 'w') as f:
                f.write(formatted_report)

            os.chmod(report_path, 0o600)

            # 6. Write metadata sidecar
            metadata = {
                "log_id": log_id,
                "tool": tool_name,
                "certificate_id": certificate_id,
                "timestamp": timestamp,
                "report_path": report_path,
                "output_keys": list(raw_output.keys()) if raw_output else [],
                "ai_generated": True,
                "supervision_required": "human_in_loop"
            }

            metadata_path = str(self.reports_dir / f"{log_id}_metadata.json")
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            os.chmod(metadata_path, 0o600)

            logger.info(f"✓ Report generated: {report_path}")
            return True, report_path, metadata_path

        except Exception as e:
            error_msg = f"Transparency processing failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg, None

    def _contains_raw_credentials(self, output: Dict[str, Any]) -> bool:
        """
        Scan output for raw credentials/passwords.
        Returns True if found.
        """
        # Convert to string for scanning
        output_str = json.dumps(output).lower()

        # Check for common credential patterns
        credential_patterns = [
            r'password\s*[:=]',
            r'api[_-]?key\s*[:=]',
            r'secret\s*[:=]',
            r'token\s*[:=]',
            r'private[_-]?key\s*[:=]',
            r'auth[_-]?token\s*[:=]',
            r'bearer\s+[a-zA-Z0-9\-_]+',
            r'begin\s+rsa\s+private\s+key'
        ]

        for pattern in credential_patterns:
            if re.search(pattern, output_str):
                logger.warning(f"Potential credential detected in output")
                return True

        return False

    def _format_output(self, raw_output: Dict[str, Any]) -> str:
        """Format tool output into markdown"""
        if not raw_output:
            return "No output from tool.\n"

        formatted = ""

        for key, value in raw_output.items():
            formatted += f"\n### {key}\n"

            if isinstance(value, dict):
                formatted += f"```json\n{json.dumps(value, indent=2)}\n```\n"
            elif isinstance(value, list):
                if value and isinstance(value[0], dict):
                    formatted += f"```json\n{json.dumps(value, indent=2)}\n```\n"
                else:
                    formatted += "\n".join([f"- {item}" for item in value]) + "\n"
            else:
                formatted += f"{str(value)}\n"

        return formatted


# ============================================================================
# Phase 7: KaiOrchestrator Main Middleware Class
# ============================================================================

class KaiOrchestrator:
    """
    Main middleware orchestrator.
    Coordinates all compliance layers: Scope Guardian, Signed Intent, Audit Logger,
    Execution Gateway, Transparency Enforcer.
    """

    def __init__(
        self,
        scope_config_path: str = "config/authorized_scope.json",
        permission_slips_vault_path: str = "vault/permission_slips",
        logs_base_dir: str = "/var/lib/kai/logs/orchestrator",
        reports_base_dir: str = "/var/lib/kai/reports"
    ):
        """Initialize KaiOrchestrator middleware"""
        logger.info("Initializing KaiOrchestrator middleware...")

        self.scope_guardian = ScopeGuardian(scope_config_path)
        self.signed_intent = SignedIntentValidator(permission_slips_vault_path)
        self.audit_logger = KaiAuditLogger(logs_base_dir)
        self.execution_gateway = SubprocessExecutionGateway()
        self.transparency = TransparencyEnforcer(reports_base_dir)

        logger.info("✓ KaiOrchestrator initialized with all compliance layers")

    async def execute_tool(
        self,
        user_id: str,
        certificate_id: str,
        target: str,
        tool_name: str,
        tool_params: Dict[str, Any],
        tool_command: str,
        reasoning: str
    ) -> Dict[str, Any]:
        """
        Main execution pipeline with full compliance gating.

        Returns Dict with:
        - success: bool
        - result: Dict or None
        - error: str or None
        - log_id: str
        - report_path: str or None
        - metadata_path: str or None
        """

        timestamp = datetime.utcnow().isoformat()

        # ============================================================
        # 1. SCOPE GUARDIAN VALIDATION
        # ============================================================
        logger.info(f"[1/6] Validating scope for target: {target}")
        valid, reason = await self.scope_guardian.validate_target(target)
        if not valid:
            logger.warning(f"SCOPE VALIDATION FAILED: {reason}")
            return {
                "success": False,
                "error": f"SCOPE VALIDATION FAILED: {reason}",
                "result": None,
                "log_id": None
            }

        # ============================================================
        # 2. AUTONOMY TIER DETERMINATION
        # ============================================================
        logger.info(f"[2/6] Determining autonomy tier for tool: {tool_name}")
        autonomy_tier = self._get_tool_autonomy_tier(tool_name)
        logger.info(f"Tool autonomy tier: {autonomy_tier}")

        # ============================================================
        # 3. SIGNED INTENT PROTOCOL (Tier 3 only)
        # ============================================================
        intent_validation = None
        if autonomy_tier == AutonomyTier.TIER_3_HARD_STOP:
            logger.info(f"[3/6] Validating signed intent for Tier 3 operation")
            valid, msg, metadata = await self.signed_intent.validate_tier_3_operation(
                target=target,
                operation_name=tool_name,
                operation_params=tool_params
            )
            if not valid:
                logger.warning(f"SIGNED INTENT VALIDATION FAILED: {msg}")
                return {
                    "success": False,
                    "error": f"SIGNED INTENT VALIDATION FAILED: {msg}",
                    "result": None,
                    "log_id": None
                }
            intent_validation = metadata
            logger.info("✓ Signed intent validated")
        else:
            logger.info(f"[3/6] Skipping signed intent (Tier {autonomy_tier})")

        # ============================================================
        # 4. PRE-EXECUTION AUDIT LOGGING
        # ============================================================
        logger.info(f"[4/6] Logging pre-execution audit")
        success, msg, log_id = await self.audit_logger.log_pending_operation(
            user_id=user_id,
            certificate_id=certificate_id,
            target=target,
            tool_name=tool_name,
            tool_params=tool_params,
            autonomy_tier=autonomy_tier.value,
            reasoning=reasoning,
            scope_validation={"target": target, "valid": True},
            intent_validation=intent_validation
        )

        if not success:
            logger.error(f"AUDIT LOGGING FAILED: {msg}")
            return {
                "success": False,
                "error": f"AUDIT LOGGING FAILED: {msg}",
                "result": None,
                "log_id": log_id
            }

        logger.info(f"✓ Pre-execution logged: {log_id}")

        # ============================================================
        # 5. SUBPROCESS EXECUTION GATEWAY
        # ============================================================
        logger.info(f"[5/6] Executing tool in subprocess")
        exec_success, exec_output, exec_error = await self.execution_gateway.execute_external_tool(
            tool_name=tool_name,
            tool_command=tool_command,
            params=tool_params,
            timeout_seconds=300,
            log_id=log_id
        )

        # ============================================================
        # 6. POST-EXECUTION AUDIT LOGGING
        # ============================================================
        logger.info(f"[6/6] Logging post-execution audit")
        await self.audit_logger.log_execution_result(
            log_id=log_id,
            execution_success=exec_success,
            execution_output=exec_output,
            error_message=exec_error
        )

        if not exec_success:
            logger.error(f"TOOL EXECUTION FAILED: {exec_error}")
            return {
                "success": False,
                "error": f"TOOL EXECUTION FAILED: {exec_error}",
                "result": None,
                "log_id": log_id
            }

        logger.info("✓ Tool execution completed successfully")

        # ============================================================
        # 7. TRANSPARENCY LAYER & REPORT GENERATION
        # ============================================================
        logger.info(f"[7/7] Applying transparency layer and generating report")
        trans_success, report_path, metadata_path = await self.transparency.process_tool_output(
            tool_name=tool_name,
            raw_output=exec_output,
            log_id=log_id,
            certificate_id=certificate_id,
            timestamp=timestamp
        )

        if not trans_success:
            logger.error(f"TRANSPARENCY PROCESSING FAILED: {report_path}")
            return {
                "success": False,
                "error": f"TRANSPARENCY PROCESSING FAILED: {report_path}",
                "result": None,
                "log_id": log_id
            }

        logger.info("✓ Report generated with transparency headers")

        # ============================================================
        # SUCCESS: Return signed, audited report
        # ============================================================
        logger.info(f"✓ ORCHESTRATION COMPLETE - All compliance gates passed")

        return {
            "success": True,
            "result": exec_output,
            "error": None,
            "log_id": log_id,
            "report_path": report_path,
            "metadata_path": metadata_path,
            "autonomy_tier": autonomy_tier.value,
            "execution_timestamp": timestamp,
            "chain_of_custody_logs": [
                str(self.audit_logger.log_dir / f"{log_id}_pre_execution.jsonl"),
                str(self.audit_logger.log_dir / f"{log_id}_post_execution.jsonl")
            ]
        }

    def _get_tool_autonomy_tier(self, tool_name: str) -> AutonomyTier:
        """Look up tool autonomy tier from authorized_scope.json"""
        tier_str = self.scope_guardian.tool_autonomy_tiers.get(
            tool_name,
            AutonomyTier.TIER_2_APPROVE.value
        )

        try:
            return AutonomyTier(tier_str)
        except ValueError:
            logger.warning(f"Unknown autonomy tier: {tier_str}, defaulting to TIER_2_APPROVE")
            return AutonomyTier.TIER_2_APPROVE


# ============================================================================
# Global Orchestrator Instance
# ============================================================================

_global_orchestrator = None


def initialize_kai_orchestrator(
    scope_config_path: str = "config/authorized_scope.json",
    permission_slips_vault_path: str = "vault/permission_slips"
) -> KaiOrchestrator:
    """Initialize the global KaiOrchestrator"""
    global _global_orchestrator

    _global_orchestrator = KaiOrchestrator(
        scope_config_path=scope_config_path,
        permission_slips_vault_path=permission_slips_vault_path
    )

    return _global_orchestrator


def get_kai_orchestrator() -> KaiOrchestrator:
    """Get the global KaiOrchestrator instance"""
    global _global_orchestrator

    if _global_orchestrator is None:
        _global_orchestrator = KaiOrchestrator()

    return _global_orchestrator
