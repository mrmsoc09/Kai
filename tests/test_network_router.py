"""Tests for network_router — UA fingerprinting, policy loading, egress config."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from apps.backend.src.core.network_router import (
    NetworkRouter,
    ScanPhase,
    EgressConfig,
    _UAFingerprintManager,
    _REAL_UAS,
)


@pytest.fixture
def router():
    r = NetworkRouter()
    # Override policy to avoid reading disk in fast tests
    r._policy = {
        "phase_routing": {
            "passive_recon": {"preferred": ["direct"], "fallback": [], "allow_direct": True},
            "dark_web":      {"preferred": ["tor"],    "fallback": [], "allow_direct": False},
            "osint_api_calls": {"preferred": ["direct"], "fallback": [], "allow_direct": True},
        },
        "providers": {"vpn": {}, "proxy": {}},
        "fingerprint": {"ua_pool_size": 10},
        "rotation": {"health_check_url": "https://ifconfig.me/ip"},
    }
    return r


# 1. Direct egress returned when direct is preferred and allowed
@pytest.mark.asyncio
async def test_direct_egress_returned(router):
    egress = await router.get_egress(ScanPhase.OSINT_API)
    assert egress.provider == "direct"


# 2. Tor egress for dark web phase
@pytest.mark.asyncio
async def test_tor_egress_for_dark_web(router):
    egress = await router.get_egress(ScanPhase.DARK_WEB)
    assert egress.provider == "tor"
    assert "socks5h" in egress.proxy_url


# 3. Tor proxy_env has correct keys
@pytest.mark.asyncio
async def test_tor_proxy_env_keys(router):
    egress = await router.get_egress(ScanPhase.DARK_WEB)
    assert "http_proxy" in egress.proxy_env
    assert "https_proxy" in egress.proxy_env


# 4. UA manager returns consistent headers for same session key
def test_ua_manager_session_sticky():
    mgr = _UAFingerprintManager(pool_size=10)
    h1 = mgr.headers_for("target-example.com")
    h2 = mgr.headers_for("target-example.com")
    assert h1["User-Agent"] == h2["User-Agent"]


# 5. Different session keys may get different UAs
def test_ua_manager_different_sessions():
    mgr = _UAFingerprintManager(pool_size=len(_REAL_UAS))
    # With enough sessions, at least two should differ
    uas = {mgr.headers_for(f"target{i}.com")["User-Agent"] for i in range(20)}
    assert len(uas) >= 2


# 6. UA headers always include required fields
def test_ua_headers_required_fields():
    mgr = _UAFingerprintManager(pool_size=10)
    headers = mgr.headers_for("test.com")
    assert "User-Agent" in headers
    assert "Accept-Language" in headers
    assert "Accept-Encoding" in headers


# 7. Chrome UAs get sec-ch-ua headers
def test_chrome_ua_gets_sec_ch_ua():
    mgr = _UAFingerprintManager.__new__(_UAFingerprintManager)
    chrome_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/136.0.0.0 Safari/537.36"
    headers = mgr._build_headers(chrome_ua)
    assert "sec-ch-ua" in headers


# 8. Firefox UAs do NOT get sec-ch-ua
def test_firefox_ua_no_sec_ch_ua():
    mgr = _UAFingerprintManager.__new__(_UAFingerprintManager)
    ff_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:138.0) Gecko/20100101 Firefox/138.0"
    headers = mgr._build_headers(ff_ua)
    assert "sec-ch-ua" not in headers


# 9. proxychains conf generated for proxy egress
def test_proxychains_conf_generated():
    r = NetworkRouter()
    egress = EgressConfig(
        provider="decodo",
        proxy_url="http://user:pass@proxy.decodo.com:10000",
    )
    conf = r.build_proxychains_conf(egress)
    assert conf is not None
    assert "ProxyList" in conf
    assert "10000" in conf


# 10. No proxychains conf for direct egress
def test_no_proxychains_for_direct():
    r = NetworkRouter()
    egress = EgressConfig(provider="direct")
    conf = r.build_proxychains_conf(egress)
    assert conf is None
