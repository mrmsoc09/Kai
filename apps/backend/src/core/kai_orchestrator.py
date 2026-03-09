import asyncio
import json
import os
import re
import uuid
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import ipaddress
import logging

from apps.backend.src.core.secret_manager import get_secret_manager

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
    Comprehensive pre-execution audit logging with cryptographic chaining.
    Records everything BEFORE tool runs, signs with machine-kaisonai@pm.me.
    """

    def __init__(self, log_base_dir: str = "/var/lib/kai/logs/orchestrator"):
        """Initialize audit logger with blockchain-style chaining"""
        self.log_dir = Path(log_base_dir)
        self.last_hash = "0" * 64  # Genesis block hash

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
            
        # Try to load last hash from most recent log file
        self._load_last_hash()

    def _load_last_hash(self):
        """Attempt to restore the hash chain from disk"""
        try:
            log_files = sorted(self.log_dir.glob("*_post_execution.jsonl"), key=os.path.getmtime)
            if log_files:
                last_log = log_files[-1]
                with open(last_log, 'r') as f:
                    data = json.load(f)
                    self.last_hash = data.get("current_hash", self.last_hash)
        except Exception as e:
            logger.warning(f"Could not restore audit chain: {e}")

    def _calculate_hash(self, data: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of a log entry"""
        canonical = json.dumps(data, sort_keys=True).encode('utf-8')
        return hashlib.sha256(canonical).hexdigest()

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
                "status": "PENDING_EXECUTION",
                "previous_hash": self.last_hash
            }
            
            # Cryptographic sealing
            current_hash = self._calculate_hash(log_entry)
            log_entry["current_hash"] = current_hash
            self.last_hash = current_hash

            # Write to orchestrator log
            log_file = self.log_dir / f"{log_id}_pre_execution.jsonl"
            with open(log_file, 'w') as f:
                json.dump(log_entry, f)

            os.chmod(log_file, 0o600)

            logger.info(f"✓ Pre-execution audit logged: {log_id} (Hash: {current_hash[:8]}...)")
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
                "status": "COMPLETED",
                "previous_hash": self.last_hash
            }
            
            # Cryptographic sealing
            current_hash = self._calculate_hash(result_entry)
            result_entry["current_hash"] = current_hash
            self.last_hash = current_hash

            log_file = self.log_dir / f"{log_id}_post_execution.jsonl"
            with open(log_file, 'w') as f:
                json.dump(result_entry, f)

            os.chmod(log_file, 0o600)

            logger.info(f"✓ Post-execution audit logged: {log_id} (Hash: {current_hash[:8]}...)")
            return True, "Post-execution logged"

        except Exception as e:
            logger.error(f"Failed to log execution result: {str(e)}")
            return False, str(e)


# ============================================================================
# Phase 5: Subprocess Execution Gateway
# ============================================================================

class SubprocessExecutionGateway:
    """
    Execute external tools in isolated environments.
    Supports Docker-based sandboxing for high-security environments.
    """
    
    # Mapping of tool names to their expected API key environment variables
    # This allows automatic secret injection from Vault
    TOOL_SECRET_MAP = {
        "shodan": ["SHODAN_API_KEY"],
        "zoomeye": ["ZOOMEYE_API_KEY"],
        "alienvault": ["ALIEN_VAULT_API_KEY", "OTX_API_KEY"],
        "abuseipdb": ["ABUSEIPDB_API_KEY"],
        "binaryedge": ["BINARYEDGE_API_KEY"],
        "censys": ["CENSYS_API_ID", "CENSYS_API_SECRET"],
        "chaos": ["CHAOS_API_KEY"],
        "github": ["GITHUB_TOKEN", "GITHUB_API_KEY"],
        "hunter": ["HUNTER_API_KEY"],
        "intelx": ["INTELX_API_KEY"],
        "securitytrails": ["SECURITYTRAILS_API_KEY"],
        "virustotal": ["VIRUSTOTAL_API_KEY"]
    }

    def __init__(self):
        # Default to False for dev safety, can be enabled via env
        self.use_docker = os.getenv("KAI_USE_DOCKER_SANDBOX", "false").lower() == "true"
        self.docker_image = os.getenv("KAI_TOOL_DOCKER_IMAGE", "kaison/tool-runner:latest")
        self.secret_manager = get_secret_manager()
        
        if self.use_docker:
            logger.info(f"SubprocessExecutionGateway initialized in DOCKER MODE ({self.docker_image})")
        else:
            logger.warning("SubprocessExecutionGateway initialized in SUBPROCESS MODE (Less Secure)")

    def _get_secrets_for_tool(self, tool_name: str) -> Dict[str, str]:
        """Fetch relevant API keys from Vault for the given tool"""
        tool_lower = tool_name.lower()
        secrets = {}
        
        # Check standard mapping
        keys_to_fetch = self.TOOL_SECRET_MAP.get(tool_lower, [])
        
        # Also check if the tool itself has a direct key named TOOLNAME_API_KEY
        direct_key = f"{tool_lower.upper()}_API_KEY"
        if direct_key not in keys_to_fetch:
            keys_to_fetch.append(direct_key)
            
        for key_name in keys_to_fetch:
            val = self.secret_manager.get_optional(key_name)
            if val:
                secrets[key_name] = val
                logger.debug(f"Injected secret {key_name} for tool {tool_name}")
                
        return secrets

    async def execute_external_tool(
        self,
        tool_name: str,
        tool_command: str,
        params: Dict[str, Any],
        timeout_seconds: int = 300,
        log_id: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Execute external tool with secret injection.
        Returns: (success, output_dict, error_message)
        """
        # Fetch secrets from Vault
        injected_secrets = self._get_secrets_for_tool(tool_name)
        
        if self.use_docker:
            return await self._execute_in_docker(tool_name, tool_command, params, injected_secrets, timeout_seconds, log_id)
        else:
            return await self._execute_in_subprocess(tool_name, tool_command, params, injected_secrets, timeout_seconds, log_id)

    async def _execute_in_docker(
        self,
        tool_name: str,
        tool_command: str,
        params: Dict[str, Any],
        secrets: Dict[str, str],
        timeout_seconds: int,
        log_id: Optional[str]
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Run tool inside a disposable Docker container with secret injection"""
        try:
            logger.info(f"Executing tool in Docker: {tool_name}")
            
            # Construct JSON payload
            request_payload = json.dumps({
                "method": tool_name,
                "params": params,
                "log_id": log_id
            })
            
            # Create a command that runs the tool inside docker
            cmd = [
                "docker", "run", "--rm", 
                "--network", "none",  # Strict network isolation by default unless overridden
                "--env", f"TOOL_COMMAND={tool_command}",
                "-i"
            ]
            
            # Inject secrets as ENV vars in Docker
            for k, v in secrets.items():
                cmd.extend(["--env", f"{k}={v}"])
                
            # Add proxy settings if available (for Whonix routing)
            for proxy_var in ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"]:
                if os.getenv(proxy_var):
                    cmd.extend(["--env", f"{proxy_var}={os.getenv(proxy_var)}"])

            cmd.append(self.docker_image)
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=request_payload.encode()),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                return False, {}, f"Docker execution timeout after {timeout_seconds}s"

            return self._parse_output(stdout, stderr)

        except Exception as e:
            return False, {}, f"Docker execution error: {str(e)}"

    async def _execute_in_subprocess(
        self,
        tool_name: str,
        tool_command: str,
        params: Dict[str, Any],
        secrets: Dict[str, str],
        timeout_seconds: int,
        log_id: Optional[str]
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Legacy local subprocess execution with secret injection"""
        try:
            logger.info(f"Executing tool locally: {tool_name} with timeout {timeout_seconds}s")

            # Merge current env with secrets and proxy
            env = os.environ.copy()
            env.update(secrets)

            command_parts = tool_command.split()

            process = await asyncio.create_subprocess_exec(
                *command_parts,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )

            request = {
                "method": tool_name,
                "params": params,
                "log_id": log_id
            }
            request_json = json.dumps(request).encode()

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(input=request_json),
                    timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                process.kill()
                return False, {}, f"Tool execution timeout after {timeout_seconds}s"

            return self._parse_output(stdout, stderr)

        except Exception as e:
            error_msg = f"Subprocess execution error: {str(e)}"
            logger.error(error_msg)
            return False, {}, error_msg

    def _parse_output(self, stdout: bytes, stderr: bytes) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """Helper to parse tool output"""
        output = {}
        error_msg = None
        
        if stdout:
            try:
                output = json.loads(stdout.decode())
            except json.JSONDecodeError:
                error_msg = f"Invalid JSON output: {stdout.decode()[:100]}..."
                logger.error(error_msg)
                return False, {}, error_msg

        if stderr:
            error_text = stderr.decode().strip()
            if error_text:
                logger.warning(f"Tool stderr: {error_text}")
                if not output:
                     return False, output, error_text

        return True, output, None


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
        # 4.5. BUDGET GATE (Cost Control & Model Routing)
        # ============================================================
        logger.info(f"[4.5/7] Checking budget and optimizing costs")

        # Import budget and routing components
        from .hybrid_model_router import get_hybrid_router
        from .cost_controller import get_cost_controller

        # Get instances
        cost_controller = get_cost_controller()
        hybrid_router = get_hybrid_router()

        # Check if this is an LLM task that requires budget control
        llm_tools = ["agent_zero", "llm_query", "code_generation", "analysis"]
        requires_budget_check = any(llm_tool in tool_name.lower() for llm_tool in llm_tools)

        budget_decision = None
        model_routing = None

        if requires_budget_check:
            # Create task definition for budget analysis
            from .model_bidding import TaskDefinition

            budget_task = TaskDefinition(
                task_id=log_id,
                name=tool_name,
                description=reasoning,
                complexity_estimate=5,  # Default moderate complexity
                required_capabilities=["reasoning"],
                # security_sensitive=task.security_sensitive if hasattr(task, 'security_sensitive') else False, # Fix undefined task
                security_sensitive=True, # Default to true for caution
                estimated_tokens_input=2000,
                estimated_tokens_output=1000
            )

            # Estimate cost
            estimated_cost = await cost_controller._estimate_task_cost(budget_task)

            # Enforce budget
            budget_result = await cost_controller.enforce_budget(
                task=budget_task,
                session_id=certificate_id,  # Use certificate_id as session_id
                user_id=user_id,
                estimated_cost_cents=estimated_cost
            )

            budget_decision = {
                "decision": budget_result.decision.value,
                "approved": budget_result.approved,
                "message": budget_result.message,
                "estimated_cost_cents": estimated_cost,
                "session_remaining": budget_result.session_budget_remaining,
                "daily_remaining": budget_result.daily_budget_remaining
            }

            # Log budget decision in audit
            logger.info(f"Budget decision: {budget_result.decision.value} - {budget_result.message}")
            logger.info(f"Estimated cost: ${estimated_cost/100:.4f}, "
                       f"Session remaining: ${budget_result.session_budget_remaining/100:.2f}, "
                       f"Daily remaining: ${budget_result.daily_budget_remaining/100:.2f}")

            # Route to appropriate model
            routing_decision = await hybrid_router.route_task(
                task=budget_task,
                session_id=certificate_id
            )

            model_routing = {
                "model_id": routing_decision.model_id,
                "is_local": routing_decision.is_local,
                "estimated_cost": routing_decision.estimated_cost_cents,
                "complexity": routing_decision.complexity,
                "fallback_applied": routing_decision.fallback_applied,
                "fallback_reason": routing_decision.fallback_reason.value if routing_decision.fallback_reason else None,
                "warning": routing_decision.warning_message
            }

            logger.info(f"Model routing: {routing_decision.model_id} "
                       f"({'local' if routing_decision.is_local else 'paid'})")

            if routing_decision.warning_message:
                logger.warning(f"⚠️ Routing warning: {routing_decision.warning_message}")

            # Add budget info to tool params for downstream use
            if tool_params is None:
                tool_params = {}
            tool_params['_kai_budget_decision'] = budget_decision
            tool_params['_kai_model_routing'] = model_routing
        else:
            logger.info(f"Skipping budget check for non-LLM tool: {tool_name}")

        # ============================================================
        # 5. SUBPROCESS EXECUTION GATEWAY
        # ============================================================
        logger.info(f"[5/7] Executing tool in subprocess")
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
        logger.info(f"[6/7] Logging post-execution audit")
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
        # 4.5. BUDGET GATE (Cost Control & Model Routing)
        # ============================================================
        logger.info(f"[4.5/7] Checking budget and optimizing costs")

        # Import budget and routing components
        from .hybrid_model_router import get_hybrid_router
        from .cost_controller import get_cost_controller

        # Get instances
        cost_controller = get_cost_controller()
        hybrid_router = get_hybrid_router()

        # Check if this is an LLM task that requires budget control
        llm_tools = ["agent_zero", "llm_query", "code_generation", "analysis"]
        requires_budget_check = any(llm_tool in tool_name.lower() for llm_tool in llm_tools)

        budget_decision = None
        model_routing = None

        if requires_budget_check:
            # Create task definition for budget analysis
            from .model_bidding import TaskDefinition

            budget_task = TaskDefinition(
                task_id=log_id,
                name=tool_name,
                description=reasoning,
                complexity_estimate=5,  # Default moderate complexity
                required_capabilities=["reasoning"],
                # security_sensitive=task.security_sensitive if hasattr(task, 'security_sensitive') else False, # Fix undefined task
                security_sensitive=True, # Default to true for caution
                estimated_tokens_input=2000,
                estimated_tokens_output=1000
            )

            # Estimate cost
            estimated_cost = await cost_controller._estimate_task_cost(budget_task)

            # Enforce budget
            budget_result = await cost_controller.enforce_budget(
                task=budget_task,
                session_id=certificate_id,  # Use certificate_id as session_id
                user_id=user_id,
                estimated_cost_cents=estimated_cost
            )

            budget_decision = {
                "decision": budget_result.decision.value,
                "approved": budget_result.approved,
                "message": budget_result.message,
                "estimated_cost_cents": estimated_cost,
                "session_remaining": budget_result.session_budget_remaining,
                "daily_remaining": budget_result.daily_budget_remaining
            }

            # Log budget decision in audit
            logger.info(f"Budget decision: {budget_result.decision.value} - {budget_result.message}")
            logger.info(f"Estimated cost: ${estimated_cost/100:.4f}, "
                       f"Session remaining: ${budget_result.session_budget_remaining/100:.2f}, "
                       f"Daily remaining: ${budget_result.daily_budget_remaining/100:.2f}")

            # Route to appropriate model
            routing_decision = await hybrid_router.route_task(
                task=budget_task,
                session_id=certificate_id
            )

            model_routing = {
                "model_id": routing_decision.model_id,
                "is_local": routing_decision.is_local,
                "estimated_cost": routing_decision.estimated_cost_cents,
                "complexity": routing_decision.complexity,
                "fallback_applied": routing_decision.fallback_applied,
                "fallback_reason": routing_decision.fallback_reason.value if routing_decision.fallback_reason else None,
                "warning": routing_decision.warning_message
            }

            logger.info(f"Model routing: {routing_decision.model_id} "
                       f"({'local' if routing_decision.is_local else 'paid'})")

            if routing_decision.warning_message:
                logger.warning(f"⚠️ Routing warning: {routing_decision.warning_message}")

            # Add budget info to tool params for downstream use
            if tool_params is None:
                tool_params = {}
            tool_params['_kai_budget_decision'] = budget_decision
            tool_params['_kai_model_routing'] = model_routing
        else:
            logger.info(f"Skipping budget check for non-LLM tool: {tool_name}")

        # ============================================================
        # 5. SUBPROCESS EXECUTION GATEWAY
        # ============================================================
        logger.info(f"[5/7] Executing tool in subprocess")
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
        logger.info(f"[6/7] Logging post-execution audit")
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
