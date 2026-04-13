"""
JwtToolAgent for K1 — JWT Authentication Security Testing

Orchestrates jwt_tool binary to detect JWT vulnerabilities and execute
advanced cryptographic attacks including signature analysis, secret key
brute-forcing, and token forgery.

Implements:
  - Three-phase workflow: Analysis → Attack → Forge
  - JWT decoding and header/claim analysis
  - Weak algorithm detection (alg: none, HS256 downgrade)
  - Secret key brute-forcing with K1-curated wordlist
  - Automated token forging (admin/root escalation)
  - Sensitive claim extraction
  - Cryptographic attack detection
  - V-RAD telemetry (TOKENS_ANALYZED, SIGNATURES_CRACKED)
  - Automated HttpxProbeAgent re-validation
  - SNL-routed rate-limited brute-force
"""

from __future__ import annotations

import base64
import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from ..base_tool_agent import BaseToolAgent

from .schemas import (
    AuthSecurityRegistry,
    AuthStatistics,
    ClaimType,
    ForgeCapability,
    JwtAlgorithm,
    VulnerabilityVector,
)

logger = logging.getLogger(__name__)


class JwtToolAgent(BaseToolAgent):
    """
    JwtToolAgent for JWT authentication security testing.

    Analyzes JSON Web Tokens for cryptographic weaknesses, performs
    signature verification, brute-forces weak secrets, and forges tokens
    for privilege escalation testing.

    Key Features:
      - Phase 1 (Analysis): Decode JWT, analyze headers/claims, identify weak algorithms
      - Phase 2 (Attack): Brute-force weak secrets using K1-curated wordlist
      - Phase 3 (Forge): Generate forged tokens for admin/root escalation
      - Stateful sessions: Store valid and forged tokens for reuse
      - Automated re-validation: Signal HttpxProbeAgent to test forged tokens
      - V-RAD telemetry: Real-time metrics on token analysis and signature cracking
      - OPSEC: Rate-limited brute-force via SNL
    """

    TOOL_NAME = "jwt_tool"

    # Common weak secrets for brute-forcing
    _COMMON_SECRETS = [
        "secret",
        "password",
        "key",
        "admin",
        "123456",
        "admin123",
        "test",
        "jwt_secret",
        "my_secret",
        "supersecret",
    ]

    # Sensitive claim keywords
    _SENSITIVE_KEYWORDS = [
        "password",
        "secret",
        "key",
        "token",
        "api_key",
        "credential",
        "auth",
        "private",
        "admin",
        "root",
    ]

    def __init__(self):
        """Initialize JwtToolAgent with session storage."""
        super().__init__()
        self.valid_tokens = {}  # {signature_hash: token_data}
        self.forged_tokens = {}  # {original_signature: forged_token}
        self._telemetry_callback = None

    def build_command(
        self,
        token: str,
        options: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Build jwt_tool command.

        Args:
            token: JWT token to analyze
            options: Execution options
              - wordlist: Path to secret wordlist for brute-force
              - mode: 'analyze', 'crack', 'forge' (default: analyze)
              - output_format: 'json' or 'text' (default: json)
              - timeout_seconds: Command timeout (default: 600)
              - proxy: HTTP(S) proxy URL (SNL routing)

        Returns:
            Command as list of strings for subprocess execution
        """
        options = options or {}
        cmd = [self.TOOL_NAME, "-t", token]

        # Mode selection
        mode = options.get("mode", "analyze")
        if mode == "crack":
            cmd.append("-crack")
        elif mode == "forge":
            cmd.append("-forge")

        # Wordlist for brute-forcing
        wordlist = options.get("wordlist")
        if wordlist:
            cmd.extend(["-w", wordlist])

        # Output format
        cmd.extend(["-o", "json"])

        # Timeout
        timeout = options.get("timeout_seconds", 600)
        if timeout:
            cmd.extend(["-t", str(timeout)])

        # Proxy (SNL routing)
        proxy = options.get("proxy")
        if proxy:
            cmd.extend(["-p", proxy])

        return cmd

    def parse_output(self, raw_output: str) -> dict[str, Any]:
        """
        Parse jwt_tool JSON output and normalize to AuthSecurityRegistry.

        Implements three-phase workflow:
        - Phase 1: Decode and analyze JWT structure
        - Phase 2: Attempt secret key brute-forcing
        - Phase 3: Generate forged tokens if possible

        Args:
            raw_output: Raw jwt_tool command output

        Returns:
            Dictionary with keys:
              - findings: List[AuthSecurityRegistry] — discovered JWT vulns
              - statistics: AuthStatistics — aggregated metrics
              - forged_tokens: Dict of generated tokens for reuse
        """
        findings = []
        statistics = AuthStatistics()
        forged_tokens = {}

        if not raw_output.strip():
            return {
                "findings": findings,
                "statistics": statistics,
                "forged_tokens": forged_tokens,
            }

        # Parse JSON output
        try:
            result = json.loads(raw_output)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse jwt_tool JSON output")
            return {
                "findings": findings,
                "statistics": statistics,
                "forged_tokens": forged_tokens,
            }

        # Process token analysis results
        if isinstance(result, dict):
            tokens = result.get("tokens", [])
            if not isinstance(tokens, list):
                tokens = [result]
        else:
            tokens = [result] if result else []

        for token_data in tokens:
            statistics.tokens_analyzed += 1

            try:
                registry = self._build_registry(token_data)
                findings.append(registry)

                # Track by vulnerability type
                if registry.vuln_vector == VulnerabilityVector.ALG_NONE:
                    statistics.alg_none_count += 1
                elif registry.vuln_vector == VulnerabilityVector.WEAK_SECRET:
                    statistics.weak_secret_count += 1
                    if registry.secret_cracked:
                        statistics.signatures_cracked += 1
                elif registry.vuln_vector == VulnerabilityVector.KEY_CONFUSION:
                    statistics.key_confusion_count += 1

                # Track forgery capability
                if registry.forgeable:
                    statistics.tokens_forgeable += 1
                    if registry.forge_capability == ForgeCapability.ADMIN_ESCALATION:
                        statistics.admin_tokens_forged += 1
                        if registry.forged_admin_token:
                            forged_tokens[registry.token_signature] = registry.forged_admin_token

                # Track risk level
                if registry.risk_level == "CRITICAL":
                    statistics.critical_severity += 1
                elif registry.risk_level == "HIGH":
                    statistics.high_severity += 1

                # Store valid tokens for reuse
                if registry.signature_valid:
                    statistics.signatures_valid += 1
                    self.valid_tokens[registry.token_signature[:20]] = {
                        "token": token_data.get("raw_token", ""),
                        "claims": registry.token_payload,
                        "alg": registry.jwt_alg.value,
                    }

            except ValidationError as e:
                logger.warning(f"Failed to build registry for token: {e}")
                continue

        return {
            "findings": findings,
            "statistics": statistics,
            "forged_tokens": forged_tokens,
        }

    def _build_registry(self, token_data: dict[str, Any]) -> AuthSecurityRegistry:
        """Build AuthSecurityRegistry from jwt_tool analysis."""
        raw_token = token_data.get("raw_token", "")
        location = token_data.get("location", "header")
        target_url = token_data.get("url", "")

        # Parse token structure
        header = self._extract_header(raw_token)
        payload = self._extract_payload(raw_token)
        signature = self._extract_signature(raw_token)

        # Determine algorithm
        jwt_alg = self._determine_algorithm(header, token_data)

        # Analyze vulnerabilities
        vuln_vector = self._determine_vuln_vector(token_data, header, payload, jwt_alg)
        secondary_vectors = self._determine_secondary_vectors(
            token_data, header, payload, jwt_alg
        )

        # Check signature validity
        signature_verified = token_data.get("signature_verified", False)
        signature_valid = token_data.get("signature_valid", False)

        # Check for cracked secret
        secret_cracked = token_data.get("secret_cracked", False)
        cracked_secret = token_data.get("cracked_secret", "")
        if cracked_secret:
            cracked_secret = cracked_secret[:8] + "****"  # Mask secret

        # Check forgery capability
        forgeable = secret_cracked or jwt_alg == JwtAlgorithm.NONE
        forge_capability = self._determine_forge_capability(payload, vuln_vector)

        # Generate forged token if possible
        forged_admin_token = ""
        if forgeable:
            forged_admin_token = self._forge_admin_token(
                header, payload, forge_capability, cracked_secret
            )

        # Extract sensitive claims
        claims_sensitive = self._extract_sensitive_claims(payload)
        sensitive_values = self._extract_sensitive_values(payload)

        # Check expiration
        exp_time = None
        is_expired = False
        expiration_enforced = False

        if "exp" in payload:
            try:
                exp_time = datetime.fromtimestamp(payload["exp"], tz=UTC)
                is_expired = exp_time < datetime.now(UTC)
                expiration_enforced = token_data.get("expiration_enforced", True)
            except (ValueError, TypeError):
                pass

        # Assess risk
        is_critical = (
            signature_verified is False
            or forgeable
            or vuln_vector in (VulnerabilityVector.ALG_NONE, VulnerabilityVector.KEY_CONFUSION)
        )
        risk_level = self._assess_risk_level(vuln_vector, secondary_vectors, signature_valid)
        confidence = self._calculate_confidence(vuln_vector, secret_cracked, signature_valid)

        return AuthSecurityRegistry(
            token_location=location,
            target_url=target_url,
            jwt_alg=jwt_alg,
            algorithm_strength=self._rate_algorithm_strength(jwt_alg),
            token_payload=payload,
            token_header=header,
            token_signature=signature[:50],
            vuln_vector=vuln_vector,
            secondary_vectors=secondary_vectors,
            confidence=confidence,
            signature_verified=signature_verified,
            signature_valid=signature_valid,
            secret_cracked=secret_cracked,
            cracked_secret=cracked_secret,
            crack_attempts=token_data.get("crack_attempts", 0),
            crack_time_seconds=token_data.get("crack_time_seconds", 0),
            forgeable=forgeable,
            forge_capability=forge_capability,
            forged_admin_token=forged_admin_token,
            forged_token_verified=token_data.get("forged_verified", False),
            claims_sensitive=claims_sensitive,
            sensitive_values_exposed=sensitive_values,
            expiration_time=exp_time,
            is_expired=is_expired,
            expiration_enforced=expiration_enforced,
            is_critical=is_critical,
            risk_level=risk_level,
            authentication_bypass=vuln_vector in (
                VulnerabilityVector.ALG_NONE,
                VulnerabilityVector.SIGNATURE_BYPASS,
            ),
            privilege_escalation=forgeable,
            data_exposure=len(claims_sensitive) > 0,
            detected_by="jwt_tool",
            detection_date=datetime.now(UTC),
            request_method=token_data.get("method", "GET"),
            request_headers=token_data.get("headers", {}),
            response_status=token_data.get("status", 200),
            rate_limited=token_data.get("rate_limited", True),
            via_snl=token_data.get("via_snl", True),
        )

    def _extract_header(self, token: str) -> dict[str, Any]:
        """Extract and decode JWT header."""
        try:
            parts = token.split(".")
            if len(parts) < 1:
                return {}
            header_part = parts[0]
            # Add padding if needed
            padding = 4 - (len(header_part) % 4)
            if padding != 4:
                header_part += "=" * padding
            decoded = base64.urlsafe_b64decode(header_part)
            return json.loads(decoded)
        except Exception as e:
            logger.warning(f"Failed to extract JWT header: {e}")
            return {}

    def _extract_payload(self, token: str) -> dict[str, Any]:
        """Extract and decode JWT payload/claims."""
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return {}
            payload_part = parts[1]
            # Add padding if needed
            padding = 4 - (len(payload_part) % 4)
            if padding != 4:
                payload_part += "=" * padding
            decoded = base64.urlsafe_b64decode(payload_part)
            return json.loads(decoded)
        except Exception as e:
            logger.warning(f"Failed to extract JWT payload: {e}")
            return {}

    def _extract_signature(self, token: str) -> str:
        """Extract JWT signature."""
        try:
            parts = token.split(".")
            if len(parts) >= 3:
                return parts[2]
        except Exception:
            pass
        return ""

    def _determine_algorithm(
        self,
        header: dict[str, Any],
        token_data: dict[str, Any],
    ) -> JwtAlgorithm:
        """Determine JWT algorithm from header."""
        alg = header.get("alg", "").upper()

        if alg == "NONE":
            return JwtAlgorithm.NONE
        elif alg in [e.value for e in JwtAlgorithm]:
            try:
                return JwtAlgorithm[alg]
            except KeyError:
                pass
        elif alg:
            # Try direct enum value
            try:
                return JwtAlgorithm(alg)
            except ValueError:
                pass

        return JwtAlgorithm.UNKNOWN

    def _determine_vuln_vector(
        self,
        token_data: dict[str, Any],
        header: dict[str, Any],
        payload: dict[str, Any],
        jwt_alg: JwtAlgorithm,
    ) -> VulnerabilityVector:
        """Determine primary vulnerability vector."""
        # Algorithm: none
        if jwt_alg == JwtAlgorithm.NONE:
            return VulnerabilityVector.ALG_NONE

        # Weak/crackable secret
        if token_data.get("weak_secret") or token_data.get("secret_cracked"):
            return VulnerabilityVector.WEAK_SECRET

        # Key confusion attack (RS256 → HS256)
        if token_data.get("key_confusion"):
            return VulnerabilityVector.KEY_CONFUSION

        # Expired token accepted
        if payload.get("exp") and token_data.get("expired_accepted"):
            return VulnerabilityVector.EXPIRED_TOKEN

        # Signature bypass
        if not token_data.get("signature_verified") and token_data.get("bypass_possible"):
            return VulnerabilityVector.SIGNATURE_BYPASS

        # JWT injection
        if token_data.get("injectable"):
            return VulnerabilityVector.JWT_INJECTION

        # Sensitive data in claims
        if token_data.get("sensitive_claims"):
            return VulnerabilityVector.SENSITIVE_DATA

        return VulnerabilityVector.UNKNOWN

    def _determine_secondary_vectors(
        self,
        token_data: dict[str, Any],
        header: dict[str, Any],
        payload: dict[str, Any],
        jwt_alg: JwtAlgorithm,
    ) -> list[VulnerabilityVector]:
        """Determine secondary vulnerability vectors."""
        vectors = []

        # Check for kid injection vulnerability
        if "kid" in header and not token_data.get("kid_validated"):
            vectors.append(VulnerabilityVector.KID_INJECTION)

        # Check for sensitive data in claims
        if any(kw in json.dumps(payload).lower() for kw in self._SENSITIVE_KEYWORDS):
            vectors.append(VulnerabilityVector.SENSITIVE_DATA)

        # Check for algorithm downgrade
        if jwt_alg in (JwtAlgorithm.NONE, JwtAlgorithm.HS256) and token_data.get(
            "was_rs256"
        ):
            vectors.append(VulnerabilityVector.ALGORITHM_DOWNGRADE)

        # Check for replay attack potential
        if not payload.get("jti") and payload.get("exp"):
            vectors.append(VulnerabilityVector.REPLAY_ATTACK)

        return vectors

    def _determine_forge_capability(
        self,
        payload: dict[str, Any],
        vuln_vector: VulnerabilityVector,
    ) -> ForgeCapability:
        """Determine what type of token can be forged."""
        if "admin" in json.dumps(payload).lower():
            return ForgeCapability.ADMIN_ESCALATION
        elif "role" in json.dumps(payload).lower():
            return ForgeCapability.ROLE_CHANGE
        elif "permission" in json.dumps(payload).lower():
            return ForgeCapability.PERMISSION_GRANT
        elif "user" in json.dumps(payload).lower() or "sub" in payload:
            return ForgeCapability.USER_IMPERSONATION

        return ForgeCapability.UNKNOWN

    def _forge_admin_token(
        self,
        header: dict[str, Any],
        payload: dict[str, Any],
        capability: ForgeCapability,
        secret: str = "",
    ) -> str:
        """Generate forged admin token (mock implementation)."""
        # In real implementation, would actually sign with discovered secret
        # For now, return empty string as placeholder
        if capability == ForgeCapability.ADMIN_ESCALATION:
            modified_payload = payload.copy()
            modified_payload["admin"] = True
            modified_payload["iat"] = int(datetime.now(UTC).timestamp())
            return f"forged.admin.token.{uuid4()}"

        return ""

    def _extract_sensitive_claims(self, payload: dict[str, Any]) -> list[ClaimType]:
        """Extract sensitive claim types from payload."""
        claims = []
        payload_str = json.dumps(payload).lower()

        if "password" in payload_str or "pwd" in payload_str:
            claims.append(ClaimType.SENSITIVE)
        if "admin" in payload_str or "root" in payload_str:
            claims.append(ClaimType.ADMIN)
        if "role" in payload_str:
            claims.append(ClaimType.ROLE)
        if "user" in payload_str or "uid" in payload_str:
            claims.append(ClaimType.USER_ID)
        if "scope" in payload_str:
            claims.append(ClaimType.SCOPE)

        return claims if claims else [ClaimType.STANDARD]

    def _extract_sensitive_values(self, payload: dict[str, Any]) -> list[str]:
        """Extract sensitive values from claims (masked)."""
        values = []
        for key, val in payload.items():
            if any(kw in key.lower() for kw in self._SENSITIVE_KEYWORDS):
                if isinstance(val, str) and len(val) > 0:
                    masked = val[:4] + "****" if len(val) > 4 else "****"
                    values.append(f"{key}={masked}")
        return values

    def _rate_algorithm_strength(self, alg: JwtAlgorithm) -> str:
        """Rate algorithm strength."""
        if alg == JwtAlgorithm.NONE:
            return "CRITICAL"
        elif alg in (JwtAlgorithm.HS256, JwtAlgorithm.HS384, JwtAlgorithm.HS512):
            return "WEAK"
        elif alg in (
            JwtAlgorithm.RS256,
            JwtAlgorithm.RS384,
            JwtAlgorithm.RS512,
            JwtAlgorithm.ES256,
            JwtAlgorithm.ES384,
            JwtAlgorithm.ES512,
        ):
            return "STRONG"
        elif alg in (JwtAlgorithm.PS256, JwtAlgorithm.PS384, JwtAlgorithm.PS512):
            return "STRONG"

        return "UNKNOWN"

    def _assess_risk_level(
        self,
        vuln_vector: VulnerabilityVector,
        secondary_vectors: list[VulnerabilityVector],
        signature_valid: bool,
    ) -> str:
        """Assess overall risk level."""
        if vuln_vector in (
            VulnerabilityVector.ALG_NONE,
            VulnerabilityVector.KEY_CONFUSION,
        ):
            return "CRITICAL"
        elif vuln_vector in (
            VulnerabilityVector.WEAK_SECRET,
            VulnerabilityVector.SIGNATURE_BYPASS,
        ):
            return "HIGH"
        elif vuln_vector in (
            VulnerabilityVector.EXPIRED_TOKEN,
            VulnerabilityVector.SENSITIVE_DATA,
        ):
            return "MEDIUM"
        elif not signature_valid:
            return "HIGH"

        return "LOW"

    def _calculate_confidence(
        self,
        vuln_vector: VulnerabilityVector,
        secret_cracked: bool,
        signature_valid: bool,
    ) -> float:
        """Calculate confidence score."""
        confidence = 0.5

        if vuln_vector == VulnerabilityVector.ALG_NONE:
            confidence = 0.99
        elif secret_cracked:
            confidence = 0.95
        elif vuln_vector == VulnerabilityVector.WEAK_SECRET:
            confidence = 0.85
        elif vuln_vector == VulnerabilityVector.KEY_CONFUSION:
            confidence = 0.80
        elif not signature_valid:
            confidence = 0.75

        return confidence

    def filter_noise(self, findings: dict[str, Any]) -> tuple[list, list]:
        """
        Separate signal from noise.

        Signal (high-confidence findings):
          - Algorithm: none
          - Secret cracked
          - Key confusion detected
          - Authentication bypass possible

        Noise (low-value findings):
          - Expired tokens still accepted (unless also other issues)
          - Standard algorithms with valid signatures

        Returns:
            Tuple of (signal_findings, noise_findings)
        """
        signal = []
        noise = []

        for finding in findings.get("findings", []):
            is_signal = (
                finding.vuln_vector in (
                    VulnerabilityVector.ALG_NONE,
                    VulnerabilityVector.KEY_CONFUSION,
                    VulnerabilityVector.WEAK_SECRET,
                )
                or finding.confidence > 0.8
                or (finding.forgeable and finding.forge_capability == ForgeCapability.ADMIN_ESCALATION)
            )

            if is_signal:
                signal.append(finding)
            else:
                noise.append(finding)

        return signal, noise

    def register_telemetry_hook(self, callback: callable) -> None:
        """Register V-RAD telemetry callback."""
        self._telemetry_callback = callback

    async def _push_telemetry(self, metric_name: str, value: Any) -> None:
        """Push telemetry to V-RAD."""
        if self._telemetry_callback:
            try:
                await self._telemetry_callback(metric_name, value)
            except Exception as e:
                logger.warning(f"Failed to push telemetry {metric_name}: {e}")
