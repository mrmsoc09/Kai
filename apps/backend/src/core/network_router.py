"""
Network Router — Intelligent VPN/proxy selection per scan phase.

Reads routing_policy.yaml, selects the right egress provider for each
scan phase, manages WireGuard interface rotation via vpn_rotate.sh,
and builds proxy environment dicts for subprocess tool invocations.

Vault holds all credentials. This module never stores secrets in memory
longer than the duration of a single call.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_POLICY_PATH = Path(__file__).parents[4] / "config" / "network" / "routing_policy.yaml"

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class ScanPhase(str, Enum):
    PASSIVE_RECON   = "passive_recon"
    ACTIVE_RECON    = "active_recon"
    OSINT_API       = "osint_api_calls"
    DARK_WEB        = "dark_web"
    CLOUD_AUDIT     = "cloud_audit"
    VULN_SCAN       = "vuln_scan"
    REPORT          = "report_generation"


@dataclass
class EgressConfig:
    """Resolved egress configuration for one scan phase."""
    provider: str          # "mullvad" | "protonvpn" | "decodo" | "direct" | "tor"
    proxy_env: dict[str, str] = field(default_factory=dict)
    proxy_url: str | None = None
    current_ip: str | None = None
    wg_interface: str | None = None


# ---------------------------------------------------------------------------
# Policy loader
# ---------------------------------------------------------------------------

def _load_policy() -> dict[str, Any]:
    if not _POLICY_PATH.exists():
        logger.warning("routing_policy.yaml not found — defaulting to direct")
        return {}
    with _POLICY_PATH.open() as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# Vault credential fetcher
# ---------------------------------------------------------------------------

def _vault_get(vault_key: str) -> str | None:
    """Fetch a single secret value from Vault synchronously.

    Returns None on any failure — callers MUST treat None as credential unavailable
    and abort the operation.  No environment variable fallback is attempted; doing
    so would silently downgrade credential security on Vault outages.
    """
    try:
        from apps.backend.src.core.vault_client import VaultClient
        client = VaultClient()
        path = f"secret/data/k1/network/{vault_key}"
        return client.get_secret(path, "value")
    except Exception as exc:
        logger.error(
            "Vault fetch FAILED for %s — credential unavailable, operation blocked: %s",
            vault_key, exc,
        )
        return None  # caller must handle None and abort — no env fallback


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class NetworkRouter:
    """
    Select and activate the correct egress path for a given scan phase.

    Usage::

        router = NetworkRouter()
        egress = await router.get_egress(ScanPhase.PASSIVE_RECON)
        # inject egress.proxy_env into tool subprocess environment
    """

    def __init__(self) -> None:
        self._policy: dict[str, Any] = _load_policy()
        self._ua_manager = _UAFingerprintManager(
            pool_size=self._policy.get("fingerprint", {}).get("ua_pool_size", 50)
        )
        self._last_rotation: dict[str, float] = {}
        self._current_ip: str | None = None
        self._active_provider: str | None = None

    # ------------------------------------------------------------------
    # Core public method
    # ------------------------------------------------------------------

    async def get_egress(self, phase: ScanPhase, target: str = "") -> EgressConfig:
        """Return a ready-to-use EgressConfig for the given scan phase."""
        phase_policy = self._policy.get("phase_routing", {}).get(phase.value, {})
        preferred = phase_policy.get("preferred", ["direct"])
        fallback  = phase_policy.get("fallback", ["direct"])
        allow_direct = phase_policy.get("allow_direct", True)

        providers_to_try = preferred + fallback
        if allow_direct and "direct" not in providers_to_try:
            providers_to_try.append("direct")

        for provider in providers_to_try:
            try:
                egress = await self._activate(provider, target)
                if egress:
                    logger.info("Phase %s → provider=%s ip=%s", phase.value, provider, egress.current_ip)
                    return egress
            except Exception as exc:
                logger.warning("Provider %s failed: %s", provider, exc)

        logger.warning("All providers failed for phase %s — using direct", phase.value)
        return EgressConfig(provider="direct")

    async def rotate(self, provider: str | None = None, country: str = "us") -> str | None:
        """Trigger an IP rotation. Returns new IP or None on failure."""
        target_provider = provider or self._active_provider or "mullvad"
        try:
            return await self._activate_vpn(target_provider, country)
        except Exception as exc:
            logger.error("Rotation failed: %s", exc)
            return None

    def get_ua_headers(self, target: str = "") -> dict[str, str]:
        """Return a consistent User-Agent + supporting headers for a session."""
        return self._ua_manager.headers_for(target)

    def build_proxychains_conf(self, egress: EgressConfig) -> str | None:
        """Generate proxychains4.conf content for CLI tool injection."""
        if not egress.proxy_url:
            return None
        return (
            "strict_chain\n"
            "proxy_dns\n"
            "[ProxyList]\n"
            f"http  {self._parse_proxy_host(egress.proxy_url)}\n"
        )

    # ------------------------------------------------------------------
    # Internal activation
    # ------------------------------------------------------------------

    async def _activate(self, provider: str, target: str) -> EgressConfig | None:
        if provider == "direct":
            return EgressConfig(provider="direct")
        if provider == "tor":
            return EgressConfig(
                provider="tor",
                proxy_env={"http_proxy": "socks5h://127.0.0.1:9050",
                           "https_proxy": "socks5h://127.0.0.1:9050",
                           "ALL_PROXY": "socks5h://127.0.0.1:9050"},
                proxy_url="socks5h://127.0.0.1:9050",
            )
        if provider in ("mullvad", "protonvpn"):
            ip = await self._activate_vpn(provider, "us")
            return EgressConfig(provider=provider, current_ip=ip)
        if provider in ("decodo", "scrapingbee", "openproxy"):
            return await self._activate_proxy(provider)
        return None

    async def _activate_vpn(self, provider: str, country: str) -> str | None:
        """Bring up a VPN interface and return the new public IP."""
        providers_cfg = self._policy.get("providers", {}).get("vpn", {})
        cfg = providers_cfg.get(provider, {})
        if not cfg.get("enabled", False):
            logger.debug("VPN provider %s disabled in routing_policy.yaml", provider)
            return None

        rotation_minutes = cfg.get("rotate_every_minutes", 30)
        last = self._last_rotation.get(provider, 0)
        if time.time() - last < rotation_minutes * 60:
            logger.debug("VPN %s still within rotation window", provider)
            return self._current_ip

        slot = "1" if provider == "protonvpn" else country
        if provider == "protonvpn":
            slot = str(random.randint(1, 2))

        vpn_script = Path(__file__).parents[4] / "scripts" / "network" / "vpn_rotate.sh"
        if not vpn_script.exists():
            logger.error("vpn_rotate.sh not found at %s", vpn_script)
            return None

        # jitter before rotation
        await asyncio.sleep(random.uniform(0.5, 2.5))

        proc = await asyncio.create_subprocess_exec(
            "bash", str(vpn_script), provider.replace("vpn", ""), slot,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode != 0:
            logger.warning("vpn_rotate.sh failed: %s", stderr.decode())
            return None

        new_ip = stdout.decode().strip().split("\n")[-1]
        self._current_ip = new_ip
        self._active_provider = provider
        self._last_rotation[provider] = time.time()
        return new_ip

    async def _activate_proxy(self, provider: str) -> EgressConfig | None:
        providers_cfg = self._policy.get("providers", {}).get("proxy", {})
        cfg = providers_cfg.get(provider, {})
        if not cfg.get("enabled", False):
            logger.debug("Proxy provider %s disabled", provider)
            return None

        if provider == "scrapingbee":
            api_key = _vault_get(cfg.get("api_key_vault_key", "scrapingbee_api_key"))
            if not api_key:
                logger.error(
                    "ScrapingBee API key unavailable from Vault — egress via scrapingbee blocked"
                )
                return None
            proxy_url = f"https://proxy.scrapingbee.com?api_key={api_key}&render_js=false"
            return EgressConfig(
                provider="scrapingbee",
                proxy_url=proxy_url,
                proxy_env={"http_proxy": proxy_url, "https_proxy": proxy_url},
            )

        username = _vault_get(cfg.get("username_vault_key", f"{provider}_username"))
        password = _vault_get(cfg.get("password_vault_key", f"{provider}_password"))
        endpoint = _vault_get(cfg.get("endpoint_vault_key", f"{provider}_endpoint"))
        if not all([username, password, endpoint]):
            missing = [k for k, v in (("username", username), ("password", password), ("endpoint", endpoint)) if not v]
            logger.error(
                "Proxy %s credentials incomplete — missing fields: %s — egress blocked",
                provider, missing,
            )
            return None

        proxy_url = f"http://{username}:{password}@{endpoint}"
        return EgressConfig(
            provider=provider,
            proxy_url=proxy_url,
            proxy_env={"http_proxy": proxy_url, "https_proxy": proxy_url,
                       "HTTP_PROXY": proxy_url, "HTTPS_PROXY": proxy_url},
        )

    @staticmethod
    def _parse_proxy_host(proxy_url: str) -> str:
        """Extract host port from proxy URL for proxychains4 format."""
        import re
        m = re.search(r"@?([^@/]+):(\d+)/?$", proxy_url)
        if m:
            return f"{m.group(1)} {m.group(2)}"
        return proxy_url


# ---------------------------------------------------------------------------
# User-Agent fingerprint manager
# ---------------------------------------------------------------------------

_REAL_UAS: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.7; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 18_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 OPR/121.0.0.0",
]


class _UAFingerprintManager:
    def __init__(self, pool_size: int = 50) -> None:
        pool = _REAL_UAS * ((pool_size // len(_REAL_UAS)) + 1)
        self._pool = pool[:pool_size]
        self._session_cache: dict[str, dict[str, str]] = {}

    def headers_for(self, session_key: str) -> dict[str, str]:
        if session_key not in self._session_cache:
            ua = random.choice(self._pool)
            self._session_cache[session_key] = self._build_headers(ua)
        return self._session_cache[session_key]

    def _build_headers(self, ua: str) -> dict[str, str]:
        is_chrome = "Chrome" in ua and "Firefox" not in ua
        is_firefox = "Firefox" in ua
        is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua

        headers: dict[str, str] = {
            "User-Agent": ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Cache-Control": "no-cache",
        }
        if is_chrome:
            version = "136" if "136" in ua else "135"
            headers["sec-ch-ua"] = f'"Chromium";v="{version}", "Google Chrome";v="{version}", "Not-A.Brand";v="99"'
            headers["sec-ch-ua-mobile"] = "?1" if is_mobile else "?0"
            headers["sec-ch-ua-platform"] = '"Android"' if "Android" in ua else ('"iPhone"' if "iPhone" in ua else '"Windows"' if "Windows" in ua else '"macOS"')
            headers["sec-fetch-dest"] = "document"
            headers["sec-fetch-mode"] = "navigate"
            headers["sec-fetch-site"] = "none"
        if is_firefox:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        return headers


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_router: NetworkRouter | None = None


def get_network_router() -> NetworkRouter:
    global _router
    if _router is None:
        _router = NetworkRouter()
    return _router
