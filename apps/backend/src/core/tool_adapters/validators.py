"""
Subprocess argument validator framework for KAISON AI security tool adapters.

Every option dict passed to a tool adapter's execute() call should be run
through validate_tool_options() *before* any command list is constructed.
Validators coerce types (e.g. string "100" → int 100) and raise ValueError
with a descriptive message on the first bad value found.

Usage
-----
    from core.tool_adapters.validators import validate_tool_options

    options = validate_tool_options("nuclei", raw_options)
    # options is now a sanitised copy; ValueError raised on bad input

Registering a new tool
----------------------
    from core.tool_adapters.validators import ToolValidator, register

    @register("mytool")
    class MyToolValidator(ToolValidator):
        def validate(self, options: dict) -> dict:
            out = dict(options)
            if "port" in out:
                out["port"] = self._coerce_int(out["port"], "port", 1, 65535)
            return out

Error contract
--------------
- ValueError  – invalid input value; catch at call site, log, and reject the request
- KeyError    – tool_name is not registered; indicates a programming error
"""

import ipaddress
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: dict[str, type["ToolValidator"]] = {}


def register(tool_name: str):
    """Class decorator that self-registers a ToolValidator subclass in the global registry."""
    def decorator(cls: type["ToolValidator"]) -> type["ToolValidator"]:
        _REGISTRY[tool_name] = cls
        return cls
    return decorator


def validate_tool_options(tool_name: str, options: dict) -> dict:
    """Validate and coerce *options* for *tool_name*.

    Returns a sanitised copy of *options*.
    Raises ValueError on invalid input, KeyError for an unregistered tool.
    """
    cls = _REGISTRY.get(tool_name)
    if cls is None:
        raise KeyError(f"No validator registered for tool: {tool_name!r}")
    return cls().validate(options)


# ---------------------------------------------------------------------------
# Base class + shared primitives
# ---------------------------------------------------------------------------

class ToolValidator(ABC):
    """Abstract base class for per-tool option validators."""

    @abstractmethod
    def validate(self, options: dict) -> dict:
        """Return a sanitised copy of *options* or raise ValueError."""

    # --- Numeric ---

    @staticmethod
    def _coerce_int(value: Any, name: str, min_val: int, max_val: int) -> int:
        """Cast *value* to int and enforce [min_val, max_val] bounds.

        Accepts int or digit-string ("100" → 100).
        Rejects float, None, non-numeric strings, and out-of-range values.
        Threat: prevents integer overflow or DoS via unbounded numeric parameters
        (e.g. rate_limit=999999999 flooding a target).
        """
        if isinstance(value, float):
            raise ValueError(f"{name}: float not accepted, use an integer")
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{name}: expected integer, got {value!r}")
        if not (min_val <= v <= max_val):
            raise ValueError(f"{name}: must be {min_val}–{max_val}, got {v}")
        return v

    # --- String pattern ---

    @staticmethod
    def _require_pattern(value: str, name: str, pattern: str, description: str) -> str:
        """Require *value* to be a str fully matching *pattern*.

        Threat: rejects shell metacharacters injected into CLI string arguments
        (semicolons, pipes, backticks, dollar signs, newlines, etc.).
        """
        if not isinstance(value, str):
            raise ValueError(f"{name}: expected str, got {type(value).__name__}")
        if not re.fullmatch(pattern, value):
            raise ValueError(f"{name}: {description}, got {value!r}")
        return value

    # --- Enum ---

    @staticmethod
    def _require_enum(value: str, name: str, allowed: frozenset) -> str:
        """Require *value* to be a member of *allowed*.

        Threat: prevents unknown option values from reaching the tool CLI,
        which could enable undocumented or dangerous behaviour.
        """
        if value not in allowed:
            raise ValueError(f"{name}: must be one of {sorted(allowed)}, got {value!r}")
        return value

    # --- URL ---

    @staticmethod
    def _require_http_url(value: str, name: str) -> str:
        """Require an http:// or https:// URL with a non-empty host.

        Threat: prevents SSRF via file://, ftp://, gopher://, data:, and other
        schemes that would cause the tool to access local or internal resources.
        """
        if not isinstance(value, str):
            raise ValueError(f"{name}: expected str URL")
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"{name}: only http/https schemes accepted, got {parsed.scheme!r}"
            )
        if not parsed.netloc:
            raise ValueError(f"{name}: missing host in URL {value!r}")
        return value

    # --- CIDR ---

    @staticmethod
    def _require_cidr(value: str, name: str) -> str:
        """Require a valid IPv4 or IPv6 CIDR notation string.

        Threat: prevents arbitrary strings from being passed to tools that
        embed them in kernel-level network exclusion lists (e.g. masscan --exclude).
        """
        if not isinstance(value, str):
            raise ValueError(f"{name}: expected CIDR string")
        try:
            ipaddress.ip_network(value, strict=False)
        except ValueError:
            raise ValueError(f"{name}: invalid CIDR notation {value!r}")
        return value

    # --- Path ---

    @staticmethod
    def _require_safe_path(value: str, name: str, base_dir: str) -> str:
        """Resolve *value* relative to *base_dir* and reject path traversal.

        Uses os.path.realpath before comparison so that both ../ sequences and
        symlinks pointing outside base_dir are caught.
        Absolute paths in *value* are rejected unless they resolve inside base_dir.

        Threat: prevents directory traversal attacks that would allow an attacker
        to reference templates, configs, or data outside the designated directory
        (e.g. /etc/passwd, ~/.ssh/id_rsa via ../../ or a malicious symlink).
        """
        if not isinstance(value, str):
            raise ValueError(f"{name}: expected str path")
        base = os.path.realpath(base_dir)
        resolved = os.path.realpath(os.path.join(base, value))
        if resolved != base and not resolved.startswith(base + os.sep):
            raise ValueError(f"{name}: path traversal detected {value!r}")
        return resolved

    # --- Port specification ---

    @staticmethod
    def _validate_ports(value: str, name: str, max_segments: int = 100) -> str:
        """Validate nmap/masscan port specification (e.g. "80,443,8080-9090").

        Enforces:
        - Digit and separator characters only (no shell metacharacters)
        - Each port in [1, 65535]
        - Range start ≤ range end
        - At most *max_segments* comma-separated entries (memory guard)

        Threat: prevents shell injection via port strings and prevents
        pathologically large port lists that could exhaust process memory.
        """
        if not isinstance(value, str):
            raise ValueError(f"{name}: expected str port specification")
        if not value:
            raise ValueError(f"{name}: port specification must not be empty")
        # Allow only digits, commas, and dashes before further parsing
        if not re.fullmatch(r'[\d,\-]+', value):
            raise ValueError(f"{name}: invalid characters in port spec {value!r}")
        segments = value.split(',')
        if len(segments) > max_segments:
            raise ValueError(
                f"{name}: too many port segments ({len(segments)} > {max_segments})"
            )
        for seg in segments:
            parts = seg.split('-')
            if len(parts) == 1:
                try:
                    port = int(parts[0])
                except ValueError:
                    raise ValueError(f"{name}: malformed port segment {seg!r}")
                if not (1 <= port <= 65535):
                    raise ValueError(f"{name}: port {port} out of range 1–65535")
            elif len(parts) == 2:
                try:
                    start, end = int(parts[0]), int(parts[1])
                except ValueError:
                    raise ValueError(f"{name}: malformed port range {seg!r}")
                if not (1 <= start <= 65535):
                    raise ValueError(f"{name}: start port {start} out of range 1–65535")
                if not (1 <= end <= 65535):
                    raise ValueError(f"{name}: end port {end} out of range 1–65535")
                if start > end:
                    raise ValueError(f"{name}: range start {start} > end {end}")
            else:
                raise ValueError(f"{name}: malformed port segment {seg!r}")
        return value


# ---------------------------------------------------------------------------
# NucleiValidator
# ---------------------------------------------------------------------------

@register("nuclei")
class NucleiValidator(ToolValidator):
    """Validates options for the nuclei vulnerability scanner.

    Threat model:
    - tags: shell metacharacter injection into CLI argument
    - rate_limit: DoS via unbounded request rate to the target
    - timeout: interaction with tool defaults; extremely large values can pin workers
    - severity: injection of unknown values that bypass intended filter
    - templates: directory traversal to load attacker-controlled templates
    """

    _VALID_SEVERITY: frozenset = frozenset({"critical", "high", "medium", "low", "info"})

    # Configurable via environment variable; evaluated at import time so the
    # value is stable for the lifetime of the process.
    _TEMPLATES_BASE: str = os.environ.get(
        "NUCLEI_TEMPLATES_BASE",
        str(Path.home() / "nuclei-templates"),
    )

    def validate(self, options: dict) -> dict:
        out = dict(options)

        if "tags" in out:
            # Allowlist: alphanumeric, comma (separator), underscore, dash only.
            # Threat: semicolon, pipe, backtick, dollar, etc. would inject commands.
            self._require_pattern(
                out["tags"],
                "tags",
                r"[a-zA-Z0-9,_\-]+",
                "only alphanumeric, comma, underscore, and dash allowed",
            )

        if "rate_limit" in out:
            # Nuclei documentation max is ~1000 rps for responsible scanning.
            out["rate_limit"] = self._coerce_int(out["rate_limit"], "rate_limit", 1, 1000)

        if "timeout" in out:
            # Cap at 300 s (5 min) per request; nuclei default is 5 s.
            out["timeout"] = self._coerce_int(out["timeout"], "timeout", 1, 300)

        if "retries" in out:
            out["retries"] = self._coerce_int(out["retries"], "retries", 0, 10)

        if "severity" in out:
            # Accepts a single value or comma-separated list ("critical,high").
            for sev in out["severity"].split(","):
                self._require_enum(sev.strip(), "severity", self._VALID_SEVERITY)

        if "templates" in out:
            # Resolves symlinks before comparison to prevent symlink-based traversal.
            out["templates"] = self._require_safe_path(
                out["templates"], "templates", self._TEMPLATES_BASE
            )

        return out


# ---------------------------------------------------------------------------
# NmapValidator
# ---------------------------------------------------------------------------

@register("nmap")
class NmapValidator(ToolValidator):
    """Validates options for the nmap network scanner.

    Threat model:
    - ports: shell injection or memory exhaustion via huge port lists
    - timing: timing template must be one of nmap's defined levels (T0–T5)
    - script: loading arbitrary NSE scripts via path separators or special chars
    """

    def validate(self, options: dict) -> dict:
        out = dict(options)

        if "ports" in out:
            self._validate_ports(out["ports"], "ports")

        if "timing" in out:
            # nmap timing templates: T0 (slowest) through T5 (insane).
            out["timing"] = self._coerce_int(out["timing"], "timing", 0, 5)

        if "script" in out:
            # Allow script names and comma-separated lists only.
            # Rejects slashes/backslashes that would load scripts from arbitrary paths.
            # Threat: --script ../../../etc/cron.d/evil could execute attacker code.
            self._require_pattern(
                out["script"],
                "script",
                r"[a-zA-Z0-9_,\-]+",
                "only alphanumeric, underscore, comma, and dash allowed (no path separators)",
            )

        return out


# ---------------------------------------------------------------------------
# SqlmapValidator
# ---------------------------------------------------------------------------

@register("sqlmap")
class SqlmapValidator(ToolValidator):
    """Validates options for the sqlmap SQL injection tool.

    Threat model:
    - url/target: SSRF via non-HTTP schemes (file://, ftp://, gopher://)
    - level: out-of-spec values cause undefined sqlmap behaviour
    - risk: risk=3 enables destructive tests; clamp caller-provided values
    - technique: unknown characters could enable unintended injection techniques
    - threads: unbounded thread counts can exhaust the local system
    - cookie: null bytes or control chars can corrupt the HTTP request or exploit parsers
    """

    _VALID_TECHNIQUE_CHARS: frozenset = frozenset("BEUSTQ")
    _MAX_COOKIE_LEN: int = 4096

    def validate(self, options: dict) -> dict:
        out = dict(options)

        # Accept both "url" (SQLMapAgent) and "target" (generic executor) keys.
        for url_key in ("url", "target"):
            if url_key in out:
                self._require_http_url(out[url_key], url_key)

        if "level" in out:
            out["level"] = self._coerce_int(out["level"], "level", 1, 5)

        if "risk" in out:
            out["risk"] = self._coerce_int(out["risk"], "risk", 1, 3)

        if "threads" in out:
            # Cap at 10 to avoid overwhelming the local network stack.
            out["threads"] = self._coerce_int(out["threads"], "threads", 1, 10)

        if "technique" in out:
            technique = out["technique"]
            if not isinstance(technique, str):
                raise ValueError(f"technique: expected str, got {type(technique).__name__}")
            upper = technique.upper()
            invalid = set(upper) - self._VALID_TECHNIQUE_CHARS
            if invalid:
                raise ValueError(
                    f"technique: unknown technique characters {sorted(invalid)}, "
                    f"allowed: {sorted(self._VALID_TECHNIQUE_CHARS)}"
                )
            out["technique"] = upper

        if "cookie" in out:
            cookie = out["cookie"]
            if not isinstance(cookie, str):
                raise ValueError("cookie: expected str")
            # Null bytes can truncate strings in C-based HTTP parsers.
            if "\x00" in cookie:
                raise ValueError("cookie: null bytes not allowed")
            # Non-printable ASCII can corrupt HTTP headers or exploit parser bugs.
            if not all(0x20 <= ord(c) <= 0x7E for c in cookie):
                raise ValueError("cookie: only printable ASCII characters allowed")
            if len(cookie) > self._MAX_COOKIE_LEN:
                raise ValueError(
                    f"cookie: too long ({len(cookie)} > {self._MAX_COOKIE_LEN} chars)"
                )

        return out


# ---------------------------------------------------------------------------
# MasscanValidator
# ---------------------------------------------------------------------------

@register("masscan")
class MasscanValidator(ToolValidator):
    """Validates options for the masscan high-speed port scanner.

    Threat model:
    - ports: shell injection or memory-exhaustion via huge port lists
    - rate: values above 10000 pps risk saturating network links or crashing targets
    - excludes: non-CIDR strings could be misinterpreted by masscan's network stack
    """

    def validate(self, options: dict) -> dict:
        out = dict(options)

        if "ports" in out:
            self._validate_ports(out["ports"], "ports")

        if "rate" in out:
            # 10000 pps is a conservative cap; masscan can do millions but that
            # risks saturating links and is inappropriate for authorised testing.
            out["rate"] = self._coerce_int(out["rate"], "rate", 1, 10000)

        if "excludes" in out:
            excludes = out["excludes"]
            if not isinstance(excludes, list):
                raise ValueError("excludes: expected list of CIDR strings, got non-list")
            out["excludes"] = [
                self._require_cidr(entry, f"excludes[{i}]")
                for i, entry in enumerate(excludes)
            ]

        return out
