"""
Opportunity Catalog — Curated index of public bug bounty and vulnerability disclosure programs.

Authorization model (AGENTS.md §3.2):
  public_bbp     — HackerOne/Bugcrowd/Intigriti programs with open submission. The program
                   listing itself IS the authorization. No separate permission required.
  public_vrp     — Vendor-run VRP open to any reporter (Google, Microsoft, Apple, etc.).
                   Public policy pages state any researcher may submit.
  government_cvd — Government CVD/VDP programs published for the general public.
  invite_only    — Private/invite-only programs. Require confirmation of invitation.

Scores are computed automatically from payout, scope size, access type, and vuln coverage.
Extend the catalog by adding entries to _RAW_CATALOG at the bottom of this file.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class CredentialRequirement:
    """Describes one credential or access item needed before deep scanning."""
    kind: str          # "signup" | "api_key" | "oauth" | "paid_plan" | "vpn" | "other"
    label: str         # Human-readable label, e.g. "Test Account (Free Tier)"
    signup_url: str    # Direct URL to sign up / obtain access
    notes: str         # Additional context from program guidelines
    required: bool     # True = must have before RECON; False = optional/recommended

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Opportunity:
    id: str                   # "hackerone:shopify" / "vrp:google" / "govt:us_dod"
    name: str
    organization: str
    platform: str             # "hackerone" | "bugcrowd" | "intigriti" | "vrp" | "government_cvd"
    access_type: str          # "public_bbp" | "public_vrp" | "government_cvd" | "invite_only"
    program_url: str
    scope_url: str
    scope_summary: str        # Human-readable: "*.shopify.com, *.myshopify.com (+3 more)"
    scope_domains: list[str]  # Machine-readable asset list
    max_payout_usd: int       # 0 = VDP / recognition only
    min_payout_usd: int
    vdp_only: bool
    response_sla_days: int    # 0 = not published
    tags: list[str]           # ["web","api","mobile","cloud","oss","hardware","crypto","iot"]
    vuln_types: list[str]     # ["xss","sqli","idor","rce","ssrf","auth_bypass","oauth","logic"]
    priority_score: float     # 0.0–1.0, auto-computed
    notes: str = ""
    credential_requirements: List[CredentialRequirement] = field(default_factory=list)

    def is_public(self) -> bool:
        """Returns True when the program requires no express written permission."""
        return self.access_type in ("public_bbp", "public_vrp", "government_cvd")

    def payout_label(self) -> str:
        if self.vdp_only or self.max_payout_usd == 0:
            return "VDP — Recognition Only"
        if self.max_payout_usd >= 1_000_000:
            return f"Up to ${self.max_payout_usd // 1_000_000}M"
        if self.max_payout_usd >= 1_000:
            return f"Up to ${self.max_payout_usd // 1_000}K"
        return f"Up to ${self.max_payout_usd}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["is_public"] = self.is_public()
        d["payout_label"] = self.payout_label()
        d["credential_requirements"] = [cr.to_dict() for cr in self.credential_requirements]
        return d


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

_HIGH_CAP_VULNS = {"xss", "sqli", "idor", "ssrf", "rce", "auth_bypass", "oauth", "logic"}


def _compute_score(
    max_payout_usd: int,
    scope_domains: list[str],
    access_type: str,
    vuln_types: list[str],
) -> float:
    """
    Weighted priority score (0.0–1.0):
      45% payout potential (log-normalized, ceiling $50k for normalization)
      20% scope richness (# of in-scope assets, ceiling 8)
      20% K1 vuln-type coverage (how many high-capability vuln types are in scope)
      15% access-type bonus (lower friction = higher score)
    """
    payout_s = math.log10(max(max_payout_usd, 1) + 1) / math.log10(50_001)
    scope_s = min(len(scope_domains) / 8.0, 1.0)
    access_b = {"public_bbp": 0.15, "public_vrp": 0.10, "government_cvd": 0.05}.get(access_type, 0.0)
    vuln_s = len(set(vuln_types) & _HIGH_CAP_VULNS) / 8.0
    raw = (0.45 * payout_s) + (0.20 * scope_s) + (0.20 * vuln_s) + access_b
    return round(min(max(raw, 0.0), 1.0), 3)


def _o(
    id: str,
    name: str,
    organization: str,
    platform: str,
    access_type: str,
    program_url: str,
    scope_url: str,
    scope_summary: str,
    scope_domains: list[str],
    max_payout_usd: int,
    min_payout_usd: int,
    vdp_only: bool,
    response_sla_days: int,
    tags: list[str],
    vuln_types: list[str],
    notes: str = "",
) -> Opportunity:
    return Opportunity(
        id=id,
        name=name,
        organization=organization,
        platform=platform,
        access_type=access_type,
        program_url=program_url,
        scope_url=scope_url,
        scope_summary=scope_summary,
        scope_domains=scope_domains,
        max_payout_usd=max_payout_usd,
        min_payout_usd=min_payout_usd,
        vdp_only=vdp_only,
        response_sla_days=response_sla_days,
        tags=tags,
        vuln_types=vuln_types,
        priority_score=_compute_score(max_payout_usd, scope_domains, access_type, vuln_types),
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Catalog — ~60 public programs
# ---------------------------------------------------------------------------

_CATALOG: list[Opportunity] = [

    # =========================================================================
    # HACKERONE PUBLIC BUG BOUNTY PROGRAMS
    # Programs with open submission state; any researcher may sign up and submit.
    # =========================================================================

    _o(
        id="hackerone:shopify",
        name="Shopify Bug Bounty",
        organization="Shopify",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/shopify",
        scope_url="https://hackerone.com/shopify#scope",
        scope_summary="*.shopify.com, *.myshopify.com, *.shopifycloud.com (+2 more)",
        scope_domains=["*.shopify.com", "*.myshopify.com", "*.shopifycloud.com",
                        "*.shopify.dev", "*.shopifyapp.com"],
        max_payout_usd=50_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "cloud", "ecommerce"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "logic", "oauth"],
    ),
    _o(
        id="hackerone:hackerone",
        name="HackerOne Bug Bounty",
        organization="HackerOne",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/security",
        scope_url="https://hackerone.com/security#scope",
        scope_summary="hackerone.com, api.hackerone.com, *.hackerone.com",
        scope_domains=["hackerone.com", "*.hackerone.com", "api.hackerone.com"],
        max_payout_usd=20_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "enterprise"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:gitlab",
        name="GitLab Bug Bounty",
        organization="GitLab",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/gitlab",
        scope_url="https://hackerone.com/gitlab#scope",
        scope_summary="gitlab.com, *.gitlab.com, gitlab.io (CE/EE source)",
        scope_domains=["gitlab.com", "*.gitlab.com", "gitlab.io", "gitlab-org/gitlab (source)"],
        max_payout_usd=20_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "oss", "devtools", "cloud"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
        notes="Open source CE codebase is in scope — static analysis of source is permitted.",
    ),
    _o(
        id="hackerone:coinbase",
        name="Coinbase Bug Bounty",
        organization="Coinbase",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/coinbase",
        scope_url="https://hackerone.com/coinbase#scope",
        scope_summary="*.coinbase.com, *.cbhax.com, Coinbase mobile apps",
        scope_domains=["*.coinbase.com", "*.cbhax.com", "coinbase-iOS", "coinbase-android"],
        max_payout_usd=50_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "crypto", "mobile", "fintech"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:twitter",
        name="X (Twitter) Bug Bounty",
        organization="X Corp",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/twitter",
        scope_url="https://hackerone.com/twitter#scope",
        scope_summary="*.twitter.com, *.x.com, *.twimg.com, mobile apps",
        scope_domains=["*.twitter.com", "*.x.com", "*.twimg.com", "twitter-iOS", "twitter-android"],
        max_payout_usd=15_000,
        min_payout_usd=140,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "social"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:yahoo",
        name="Yahoo Bug Bounty",
        organization="Yahoo / Verizon Media",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/yahoo",
        scope_url="https://hackerone.com/yahoo#scope",
        scope_summary="*.yahoo.com, *.yahooapis.com, Yahoo mail/finance/sports",
        scope_domains=["*.yahoo.com", "*.yahooapis.com", "*.yimg.com", "mail.yahoo.com",
                        "finance.yahoo.com"],
        max_payout_usd=15_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "email", "fintech"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:riot_games",
        name="Riot Games Bug Bounty",
        organization="Riot Games",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/riotgames",
        scope_url="https://hackerone.com/riotgames#scope",
        scope_summary="*.riotgames.com, *.leagueoflegends.com, Valorant, game clients",
        scope_domains=["*.riotgames.com", "*.leagueoflegends.com", "*.valorant.com",
                        "*.teamfighttactics.com"],
        max_payout_usd=25_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "gaming", "mobile"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
    ),
    _o(
        id="hackerone:reddit",
        name="Reddit Bug Bounty",
        organization="Reddit",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/reddit",
        scope_url="https://hackerone.com/reddit#scope",
        scope_summary="reddit.com, *.reddit.com, *.redd.it, Reddit mobile apps",
        scope_domains=["reddit.com", "*.reddit.com", "*.redd.it", "reddit-iOS", "reddit-android"],
        max_payout_usd=10_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "social"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:dropbox",
        name="Dropbox Bug Bounty",
        organization="Dropbox",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/dropbox",
        scope_url="https://hackerone.com/dropbox#scope",
        scope_summary="*.dropbox.com, *.dropboxapi.com, *.paper.dropbox.com (+1)",
        scope_domains=["*.dropbox.com", "*.dropboxapi.com", "*.paper.dropbox.com",
                        "dropbox-iOS", "dropbox-android"],
        max_payout_usd=32_768,
        min_payout_usd=216,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "cloud", "mobile"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:grammarly",
        name="Grammarly Bug Bounty",
        organization="Grammarly",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/grammarly",
        scope_url="https://hackerone.com/grammarly#scope",
        scope_summary="*.grammarly.com, Grammarly browser extensions and desktop app",
        scope_domains=["*.grammarly.com", "grammarly-browser-extension", "grammarly-desktop"],
        max_payout_usd=10_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "browser-extension"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "oauth", "logic"],
    ),
    _o(
        id="hackerone:mozilla",
        name="Mozilla Bug Bounty",
        organization="Mozilla",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/mozilla",
        scope_url="https://hackerone.com/mozilla#scope",
        scope_summary="Firefox, Thunderbird, *.mozilla.org, *.mozillaonline.com",
        scope_domains=["*.mozilla.org", "*.mozillaonline.com", "firefox-browser", "firefox-ios",
                        "firefox-android", "thunderbird"],
        max_payout_usd=10_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "oss", "browser", "mobile"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="hackerone:nordvpn",
        name="NordVPN Bug Bounty",
        organization="NordVPN",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/nordsecurity",
        scope_url="https://hackerone.com/nordsecurity#scope",
        scope_summary="*.nordvpn.com, *.nordpass.com, NordVPN apps (all platforms)",
        scope_domains=["*.nordvpn.com", "*.nordpass.com", "nordvpn-iOS", "nordvpn-android",
                        "nordvpn-windows", "nordvpn-macos"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "vpn", "mobile", "privacy"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="hackerone:paypal",
        name="PayPal Bug Bounty",
        organization="PayPal",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/paypal",
        scope_url="https://hackerone.com/paypal#scope",
        scope_summary="*.paypal.com, *.braintreepayments.com, PayPal mobile apps",
        scope_domains=["*.paypal.com", "*.braintreepayments.com", "*.paypal-corp.com",
                        "paypal-iOS", "paypal-android"],
        max_payout_usd=10_000,
        min_payout_usd=50,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:slack",
        name="Slack Bug Bounty",
        organization="Salesforce / Slack",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/slack",
        scope_url="https://hackerone.com/slack#scope",
        scope_summary="slack.com, api.slack.com, *.slack.com, Slack desktop/mobile",
        scope_domains=["slack.com", "api.slack.com", "*.slack.com", "slack-desktop",
                        "slack-iOS", "slack-android"],
        max_payout_usd=10_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "enterprise", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:proton",
        name="Proton Bug Bounty",
        organization="Proton AG",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/protonmail",
        scope_url="https://hackerone.com/protonmail#scope",
        scope_summary="proton.me, *.proton.me, *.protonmail.com, Proton apps",
        scope_domains=["proton.me", "*.proton.me", "*.protonmail.com", "proton-iOS",
                        "proton-android"],
        max_payout_usd=10_000,
        min_payout_usd=150,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "crypto", "privacy", "mobile", "email"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:twitch",
        name="Twitch Bug Bounty",
        organization="Twitch (Amazon)",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/twitch",
        scope_url="https://hackerone.com/twitch#scope",
        scope_summary="twitch.tv, *.twitch.tv, api.twitch.tv, Twitch mobile apps",
        scope_domains=["twitch.tv", "*.twitch.tv", "api.twitch.tv", "twitch-iOS", "twitch-android"],
        max_payout_usd=7_500,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "streaming", "gaming", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="hackerone:tiktok",
        name="TikTok Bug Bounty",
        organization="ByteDance",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/tiktok",
        scope_url="https://hackerone.com/tiktok#scope",
        scope_summary="*.tiktok.com, TikTok iOS & Android apps",
        scope_domains=["*.tiktok.com", "*.tiktokapis.com", "tiktok-iOS", "tiktok-android"],
        max_payout_usd=14_800,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "social"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="hackerone:doordash",
        name="DoorDash Bug Bounty",
        organization="DoorDash",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/doordash",
        scope_url="https://hackerone.com/doordash#scope",
        scope_summary="*.doordash.com, DoorDash iOS & Android apps",
        scope_domains=["*.doordash.com", "*.doordash.engineering", "doordash-iOS", "doordash-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "logistics"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="hackerone:cloudflare",
        name="Cloudflare Bug Bounty",
        organization="Cloudflare",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/cloudflare",
        scope_url="https://hackerone.com/cloudflare#scope",
        scope_summary="*.cloudflare.com, *.cloudflareworkers.com, Cloudflare APIs",
        scope_domains=["*.cloudflare.com", "*.cloudflareworkers.com", "api.cloudflare.com",
                        "*.cloudflare.net"],
        max_payout_usd=3_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "network", "cloud", "security"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="hackerone:uber",
        name="Uber Bug Bounty",
        organization="Uber",
        platform="hackerone",
        access_type="public_bbp",
        program_url="https://hackerone.com/uber",
        scope_url="https://hackerone.com/uber#scope",
        scope_summary="*.uber.com, *.ubereats.com, Uber/Eats iOS & Android",
        scope_domains=["*.uber.com", "*.ubereats.com", "*.uber.engineer", "uber-iOS",
                        "uber-android", "ubereats-iOS", "ubereats-android"],
        max_payout_usd=10_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "logistics"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),

    # =========================================================================
    # BUGCROWD PUBLIC BUG BOUNTY PROGRAMS
    # =========================================================================

    _o(
        id="bugcrowd:tesla",
        name="Tesla Bug Bounty",
        organization="Tesla",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/tesla",
        scope_url="https://bugcrowd.com/tesla/scopes",
        scope_summary="*.tesla.com, Tesla web services, mobile apps",
        scope_domains=["*.tesla.com", "*.teslamotors.com", "*.energylocal.co.uk",
                        "tesla-iOS", "tesla-android"],
        max_payout_usd=15_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "automotive", "mobile", "iot"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "logic"],
    ),
    _o(
        id="bugcrowd:netgear",
        name="Netgear Bug Bounty",
        organization="Netgear",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/netgear",
        scope_url="https://bugcrowd.com/netgear/scopes",
        scope_summary="*.netgear.com, Netgear router firmware and management interfaces",
        scope_domains=["*.netgear.com", "netgear-firmware", "netgear-router-mgmt"],
        max_payout_usd=15_000,
        min_payout_usd=150,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "hardware", "iot", "firmware"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
        notes="Firmware and hardware targets in scope; physical exploitation out of scope.",
    ),
    _o(
        id="bugcrowd:atlassian",
        name="Atlassian Bug Bounty",
        organization="Atlassian",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/atlassian",
        scope_url="https://bugcrowd.com/atlassian/scopes",
        scope_summary="*.atlassian.com, *.atlassian.net, Jira/Confluence/Bitbucket/Trello",
        scope_domains=["*.atlassian.com", "*.atlassian.net", "*.jira.com", "*.trello.com",
                        "*.bitbucket.org", "*.confluence.com"],
        max_payout_usd=12_500,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "cloud", "enterprise", "devtools"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="bugcrowd:western_digital",
        name="Western Digital Bug Bounty",
        organization="Western Digital",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/westerndigital",
        scope_url="https://bugcrowd.com/westerndigital/scopes",
        scope_summary="*.westerndigital.com, *.mycloud.com, WD NAS firmware",
        scope_domains=["*.westerndigital.com", "*.mycloud.com", "wd-nas-firmware",
                        "wd-ios", "wd-android"],
        max_payout_usd=15_000,
        min_payout_usd=150,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "hardware", "iot", "firmware", "cloud"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
    ),
    _o(
        id="bugcrowd:okta",
        name="Okta Bug Bounty",
        organization="Okta",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/okta",
        scope_url="https://bugcrowd.com/okta/scopes",
        scope_summary="*.okta.com, *.auth0.com, Okta Verify apps",
        scope_domains=["*.okta.com", "*.auth0.com", "*.oktapreview.com", "okta-iOS",
                        "okta-android"],
        max_payout_usd=10_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "auth", "enterprise", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
        notes="Auth bypass and OAuth/OIDC vulnerabilities are particularly high value.",
    ),
    _o(
        id="bugcrowd:square",
        name="Square / Block Bug Bounty",
        organization="Block (Square)",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/square",
        scope_url="https://bugcrowd.com/square/scopes",
        scope_summary="*.squareup.com, *.cash.app, *.block.xyz, Square POS",
        scope_domains=["*.squareup.com", "*.cash.app", "*.block.xyz", "*.tidal.com",
                        "square-iOS", "square-android", "cashapp-iOS", "cashapp-android"],
        max_payout_usd=10_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "crypto", "mobile", "pos"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="bugcrowd:toyota",
        name="Toyota Bug Bounty",
        organization="Toyota",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/toyota",
        scope_url="https://bugcrowd.com/toyota/scopes",
        scope_summary="*.toyota.com, Toyota connected services, MyToyota app",
        scope_domains=["*.toyota.com", "*.lexus.com", "mytoyota-iOS", "mytoyota-android"],
        max_payout_usd=10_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "automotive", "mobile", "iot"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="bugcrowd:hp",
        name="HP Bug Bounty",
        organization="HP",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/hp",
        scope_url="https://bugcrowd.com/hp/scopes",
        scope_summary="*.hp.com, HP printer firmware, HP cloud services",
        scope_domains=["*.hp.com", "*.hpcloud.com", "hp-printer-firmware", "hp-iOS",
                        "hp-android"],
        max_payout_usd=10_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "hardware", "firmware", "enterprise"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
    ),
    _o(
        id="bugcrowd:mastercard",
        name="Mastercard Bug Bounty",
        organization="Mastercard",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/mastercard",
        scope_url="https://bugcrowd.com/mastercard/scopes",
        scope_summary="*.mastercard.com, *.mastercard.us, Mastercard APIs",
        scope_domains=["*.mastercard.com", "*.mastercard.us", "*.mastercard.co.uk",
                        "api.mastercard.com"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "enterprise"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="bugcrowd:asus",
        name="ASUS Bug Bounty",
        organization="ASUS",
        platform="bugcrowd",
        access_type="public_bbp",
        program_url="https://bugcrowd.com/asus",
        scope_url="https://bugcrowd.com/asus/scopes",
        scope_summary="*.asus.com, ASUS router/NAS firmware, ASUS apps",
        scope_domains=["*.asus.com", "asus-router-firmware", "asus-nas-firmware",
                        "asus-iOS", "asus-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "hardware", "iot", "firmware"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
    ),

    # =========================================================================
    # INTIGRITI PUBLIC BUG BOUNTY PROGRAMS (European focus)
    # =========================================================================

    _o(
        id="intigriti:european_commission",
        name="European Commission VDP",
        organization="European Commission",
        platform="intigriti",
        access_type="government_cvd",
        program_url="https://www.intigriti.com/bug-bounty-programs/europeancommission/ec-corporate/detail",
        scope_url="https://www.intigriti.com/bug-bounty-programs/europeancommission/ec-corporate/detail",
        scope_summary="*.europa.eu — EU institutional websites and services",
        scope_domains=["*.europa.eu", "*.ec.europa.eu", "*.europarl.europa.eu"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=90,
        tags=["web", "api", "government"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "ssrf"],
    ),
    _o(
        id="intigriti:ubisoft",
        name="Ubisoft Bug Bounty",
        organization="Ubisoft",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/ubisoft",
        scope_url="https://www.intigriti.com/bug-bounty-programs/ubisoft/detail",
        scope_summary="*.ubisoft.com, Ubisoft Connect platform and game services",
        scope_domains=["*.ubisoft.com", "*.ubi.com", "ubisoftconnect-iOS", "ubisoftconnect-android"],
        max_payout_usd=10_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "gaming", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "oauth", "logic"],
    ),
    _o(
        id="intigriti:ing",
        name="ING Bug Bounty",
        organization="ING Bank",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/ing",
        scope_url="https://www.intigriti.com/bug-bounty-programs/ing/detail",
        scope_summary="*.ing.com, ING banking web and mobile apps",
        scope_domains=["*.ing.com", "*.ing.nl", "*.ing.be", "ing-iOS", "ing-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "mobile", "banking"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "oauth", "logic"],
    ),
    _o(
        id="intigriti:proximus",
        name="Proximus Bug Bounty",
        organization="Proximus",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/proximus",
        scope_url="https://www.intigriti.com/bug-bounty-programs/proximus/detail",
        scope_summary="*.proximus.be, Proximus web and mobile applications",
        scope_domains=["*.proximus.be", "proximus-iOS", "proximus-android"],
        max_payout_usd=2_500,
        min_payout_usd=50,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "telco", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="intigriti:swisscom",
        name="Swisscom Bug Bounty",
        organization="Swisscom",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/swisscom",
        scope_url="https://www.intigriti.com/bug-bounty-programs/swisscom/detail",
        scope_summary="*.swisscom.ch, Swisscom TV and digital services",
        scope_domains=["*.swisscom.ch", "*.swisscom.com", "swisscom-iOS", "swisscom-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "telco", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="intigriti:belfius",
        name="Belfius Bug Bounty",
        organization="Belfius Bank",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/belfius",
        scope_url="https://www.intigriti.com/bug-bounty-programs/belfius/detail",
        scope_summary="*.belfius.be, Belfius Direct Net banking platform",
        scope_domains=["*.belfius.be", "belfius-iOS", "belfius-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "banking", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "oauth", "logic"],
    ),
    _o(
        id="intigriti:philips",
        name="Philips Bug Bounty",
        organization="Philips",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/philips",
        scope_url="https://www.intigriti.com/bug-bounty-programs/philips/detail",
        scope_summary="*.philips.com, Philips Hue and connected health products",
        scope_domains=["*.philips.com", "*.meethue.com", "philips-iOS", "philips-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "iot", "healthcare", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="intigriti:kbc",
        name="KBC Bank Bug Bounty",
        organization="KBC Group",
        platform="intigriti",
        access_type="public_bbp",
        program_url="https://www.intigriti.com/bug-bounty-programs/kbc",
        scope_url="https://www.intigriti.com/bug-bounty-programs/kbc/detail",
        scope_summary="*.kbc.be, KBC Mobile app, KBC Business apps",
        scope_domains=["*.kbc.be", "*.cbc.be", "kbc-iOS", "kbc-android"],
        max_payout_usd=5_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "fintech", "banking", "mobile"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),

    # =========================================================================
    # PUBLIC VENDOR VRP PROGRAMS (open to any reporter by published policy)
    # =========================================================================

    _o(
        id="vrp:google",
        name="Google Vulnerability Reward Program",
        organization="Google",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://bughunters.google.com/about/rules/6625378258649088",
        scope_url="https://bughunters.google.com/about/rules/6625378258649088/google-and-alphabet-vulnerability-reward-program-vrp-rules",
        scope_summary="*.google.com, *.googleapis.com, Android, Chrome, Google Cloud (+many)",
        scope_domains=["*.google.com", "*.googleapis.com", "*.googlesyndication.com",
                        "*.android.com", "*.chromium.org", "*.gstatic.com",
                        "*.googlevideo.com", "*.cloud.google.com"],
        max_payout_usd=31_337,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "cloud", "mobile", "browser", "android"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
        notes="One of the highest-volume public VRPs. Chrome and Android have separate programs with higher payouts.",
    ),
    _o(
        id="vrp:microsoft",
        name="Microsoft Security Response Center",
        organization="Microsoft",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://www.microsoft.com/en-us/msrc/bounty",
        scope_url="https://www.microsoft.com/en-us/msrc/bounty",
        scope_summary="*.microsoft.com, *.azure.com, *.office365.com, Windows, Exchange",
        scope_domains=["*.microsoft.com", "*.azure.com", "*.azurewebsites.net",
                        "*.office365.com", "*.microsoftonline.com", "*.outlook.com",
                        "*.sharepoint.com", "*.teams.microsoft.com"],
        max_payout_usd=250_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "cloud", "enterprise", "hardware", "windows"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
        notes="Azure, Identity (AAD/Entra), Microsoft 365, and Hyper-V have dedicated sub-programs with highest payouts.",
    ),
    _o(
        id="vrp:apple",
        name="Apple Security Bounty",
        organization="Apple",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://security.apple.com/security-bounty/",
        scope_url="https://security.apple.com/security-bounty/",
        scope_summary="iOS, macOS, tvOS, watchOS, iCloud services, Apple Silicon",
        scope_domains=["*.icloud.com", "*.apple.com", "*.mzstatic.com", "iOS", "macOS",
                        "tvOS", "watchOS", "iCloud"],
        max_payout_usd=1_000_000,
        min_payout_usd=2_500,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "mobile", "hardware", "ios", "macos"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
        notes="Highest published bounty in the industry ($1M for zero-click kernel exploits). Complex targets; high effort.",
    ),
    _o(
        id="vrp:samsung",
        name="Samsung Mobile Security Reward",
        organization="Samsung",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://security.samsungmobile.com/securityRewardProgram.smsb",
        scope_url="https://security.samsungmobile.com/securityRewardProgram.smsb",
        scope_summary="Samsung Android OS, Knox, Galaxy apps, Samsung IoT devices",
        scope_domains=["*.samsung.com", "Samsung-Android", "Samsung-Knox", "Samsung-Tizen",
                        "Samsung-IoT"],
        max_payout_usd=1_000_000,
        min_payout_usd=200,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "mobile", "hardware", "android", "iot"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
    ),
    _o(
        id="vrp:meta",
        name="Meta Bug Bounty",
        organization="Meta",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://www.facebook.com/security/programs",
        scope_url="https://www.facebook.com/security/programs",
        scope_summary="*.facebook.com, *.instagram.com, *.whatsapp.com, *.oculus.com (+more)",
        scope_domains=["*.facebook.com", "*.instagram.com", "*.whatsapp.com",
                        "*.oculus.com", "*.messenger.com", "*.fb.com",
                        "facebook-iOS", "facebook-android", "instagram-iOS", "instagram-android"],
        max_payout_usd=40_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "mobile", "social", "vr"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="vrp:amazon",
        name="Amazon Vulnerability Research Program",
        organization="Amazon / AWS",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://aws.amazon.com/security/vulnerability-reporting/",
        scope_url="https://aws.amazon.com/security/vulnerability-reporting/",
        scope_summary="*.amazon.com, *.aws.amazon.com, AWS services, Alexa, Ring",
        scope_domains=["*.amazon.com", "*.amazonaws.com", "*.awsstatic.com",
                        "*.cloudfront.net", "*.alexa.com", "*.ring.com"],
        max_payout_usd=20_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "cloud", "iot", "mobile"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="vrp:adobe",
        name="Adobe Bounty Program",
        organization="Adobe",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://www.adobe.com/trust/resource-center/bug-bounty.html",
        scope_url="https://hackerone.com/adobe",
        scope_summary="*.adobe.com, Adobe Creative Cloud, Document Cloud, Experience Cloud",
        scope_domains=["*.adobe.com", "*.adobecc.com", "*.adobeaemcloud.com",
                        "*.experience.adobe.com", "*.documentcloud.adobe.com"],
        max_payout_usd=25_000,
        min_payout_usd=100,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "cloud", "enterprise", "creative"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "oauth", "logic"],
    ),
    _o(
        id="vrp:intel",
        name="Intel Bug Bounty Program",
        organization="Intel",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://www.intel.com/content/www/us/en/security-center/bug-bounty-program.html",
        scope_url="https://www.intel.com/content/www/us/en/security-center/bug-bounty-program.html",
        scope_summary="Intel CPUs, firmware, drivers, SGX, ME/AMT, Intel web properties",
        scope_domains=["*.intel.com", "intel-cpu-firmware", "intel-sgx", "intel-me",
                        "intel-amt", "intel-drivers"],
        max_payout_usd=100_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=90,
        tags=["web", "api", "hardware", "firmware", "cpu"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "logic"],
        notes="Hardware/firmware targets available. Side-channel and microarchitectural attacks in scope.",
    ),
    _o(
        id="vrp:mozilla_foundation",
        name="Mozilla Foundation Security Program",
        organization="Mozilla Foundation",
        platform="vrp",
        access_type="public_vrp",
        program_url="https://www.mozilla.org/en-US/security/bug-bounty/",
        scope_url="https://www.mozilla.org/en-US/security/bug-bounty/",
        scope_summary="Firefox browser, Thunderbird, Mozilla web services, Firefox OS",
        scope_domains=["*.mozilla.org", "*.mozilla.net", "*.mozilla.com", "firefox",
                        "thunderbird", "*.firefox.com"],
        max_payout_usd=10_000,
        min_payout_usd=500,
        vdp_only=False,
        response_sla_days=30,
        tags=["web", "api", "oss", "browser"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "logic"],
    ),

    # =========================================================================
    # GOVERNMENT CVD PROGRAMS — open to the public by government policy
    # =========================================================================

    _o(
        id="govt:us_dod",
        name="US Department of Defense VDP",
        organization="US Department of Defense",
        platform="government_cvd",
        access_type="government_cvd",
        program_url="https://hackerone.com/deptofdefense",
        scope_url="https://hackerone.com/deptofdefense#scope",
        scope_summary="All publicly accessible DoD systems (*.mil, *.army.mil, *.navy.mil, etc.)",
        scope_domains=["*.mil", "*.army.mil", "*.navy.mil", "*.af.mil", "*.marines.mil",
                        "*.dod.gov", "*.defense.gov"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=90,
        tags=["web", "api", "government", "military"],
        vuln_types=["xss", "sqli", "idor", "rce", "auth_bypass", "ssrf", "logic"],
        notes="VDP only — no monetary bounty. Largest single scope in any public program: all public-facing DoD systems.",
    ),
    _o(
        id="govt:cisa",
        name="CISA Coordinated Vulnerability Disclosure",
        organization="CISA (Cybersecurity and Infrastructure Security Agency)",
        platform="government_cvd",
        access_type="government_cvd",
        program_url="https://www.cisa.gov/coordinated-vulnerability-disclosure-process",
        scope_url="https://www.cisa.gov/coordinated-vulnerability-disclosure-process",
        scope_summary="US critical infrastructure systems and CISA-operated web properties",
        scope_domains=["*.cisa.gov", "*.dhs.gov", "*.us-cert.cisa.gov"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=90,
        tags=["web", "api", "government", "critical-infrastructure"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="govt:uk_ncsc",
        name="UK NCSC Coordinated Vulnerability Disclosure",
        organization="UK National Cyber Security Centre",
        platform="government_cvd",
        access_type="government_cvd",
        program_url="https://www.ncsc.gov.uk/information/vulnerability-disclosure-toolkit",
        scope_url="https://www.ncsc.gov.uk/information/vulnerability-disclosure-toolkit",
        scope_summary="UK government digital services (*.gov.uk, *.service.gov.uk)",
        scope_domains=["*.gov.uk", "*.service.gov.uk", "*.digital.cabinet-office.gov.uk"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=60,
        tags=["web", "api", "government"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="govt:eu_enisa",
        name="ENISA / EU Coordinated Vulnerability Disclosure",
        organization="European Union Agency for Cybersecurity (ENISA)",
        platform="government_cvd",
        access_type="government_cvd",
        program_url="https://www.enisa.europa.eu/topics/incident-reporting/vulnerability-disclosure",
        scope_url="https://www.enisa.europa.eu/topics/incident-reporting/vulnerability-disclosure",
        scope_summary="EU agency digital services and *.europa.eu web properties",
        scope_domains=["*.europa.eu", "*.enisa.europa.eu"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=90,
        tags=["web", "api", "government"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
    _o(
        id="govt:bsi_germany",
        name="BSI Vulnerability Disclosure (Germany)",
        organization="Bundesamt für Sicherheit in der Informationstechnik",
        platform="government_cvd",
        access_type="government_cvd",
        program_url="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Cybersicherheitslage/Vulnerability-Disclosure/vulnerability-disclosure_node.html",
        scope_url="https://www.bsi.bund.de/EN/Themen/Unternehmen-und-Organisationen/Cybersicherheitslage/Vulnerability-Disclosure/vulnerability-disclosure_node.html",
        scope_summary="German federal IT systems and *.bund.de properties",
        scope_domains=["*.bund.de", "*.bsi.bund.de"],
        max_payout_usd=0,
        min_payout_usd=0,
        vdp_only=True,
        response_sla_days=90,
        tags=["web", "api", "government"],
        vuln_types=["xss", "sqli", "idor", "auth_bypass", "logic"],
    ),
]


# ---------------------------------------------------------------------------
# Credential requirements — what each program needs before deep scanning
# ---------------------------------------------------------------------------
# Keys match Opportunity.id. Values are lists of CredentialRequirement.
# Programs omitted here have no prerequisites (pure public surface scanning).
# ---------------------------------------------------------------------------

def _cr(kind: str, label: str, signup_url: str, notes: str = "", required: bool = True) -> CredentialRequirement:
    return CredentialRequirement(kind=kind, label=label, signup_url=signup_url, notes=notes, required=required)


_CREDENTIAL_REQUIREMENTS: dict[str, list[CredentialRequirement]] = {
    # ── HackerOne programs ───────────────────────────────────────────────────
    "hackerone:shopify": [
        _cr("signup", "Merchant Store Account", "https://www.shopify.com/free-trial",
            "Create a free dev store. Use your personal email. Do not use production stores."),
        _cr("api_key", "Shopify Partner API Key", "https://partners.shopify.com",
            "Optional: Partner API key enables API endpoint testing.", required=False),
    ],
    "hackerone:hackerone": [
        _cr("signup", "HackerOne Researcher Account", "https://hackerone.com/users/sign_up",
            "A registered researcher account is required to submit. Use your existing account."),
    ],
    "hackerone:gitlab": [
        _cr("signup", "GitLab.com Account (Free)", "https://gitlab.com/users/sign_up",
            "Create a free GitLab account. Use a dedicated test account, not your primary one."),
        _cr("api_key", "GitLab Personal Access Token", "https://gitlab.com/-/user_settings/personal_access_tokens",
            "Generate a PAT with api scope for REST/GraphQL endpoint testing.", required=False),
    ],
    "hackerone:coinbase": [
        _cr("signup", "Coinbase Account", "https://www.coinbase.com/signup",
            "Standard Coinbase account. Use a dedicated test account with no real funds."),
    ],
    "hackerone:twitter": [
        _cr("signup", "X / Twitter Account", "https://x.com/i/flow/signup",
            "Create a dedicated test account. Do not use your personal Twitter account for testing."),
        _cr("api_key", "X Developer API v2 Credentials", "https://developer.x.com/en/portal/dashboard",
            "Apply for developer access to test API endpoints. Free Basic tier is sufficient.", required=False),
    ],
    "hackerone:yahoo": [
        _cr("signup", "Yahoo Account", "https://login.yahoo.com/account/create",
            "Create a dedicated Yahoo account for testing."),
    ],
    "hackerone:riot_games": [
        _cr("signup", "Riot Games Account", "https://auth.riotgames.com/login#create_account",
            "Create a Riot account. Install the client if testing game clients."),
    ],
    "hackerone:reddit": [
        _cr("signup", "Reddit Account", "https://www.reddit.com/register/",
            "Create a dedicated test Reddit account. Do not test with your personal account."),
        _cr("api_key", "Reddit API Credentials", "https://www.reddit.com/prefs/apps",
            "Register a Reddit app (script type) for OAuth and API testing.", required=False),
    ],
    "hackerone:dropbox": [
        _cr("signup", "Dropbox Account (Free 2 GB)", "https://www.dropbox.com/register",
            "Free tier is sufficient for most API and web testing."),
        _cr("api_key", "Dropbox API App Key", "https://www.dropbox.com/developers/apps",
            "Create a Dropbox app for API access token testing.", required=False),
    ],
    "hackerone:grammarly": [
        _cr("signup", "Grammarly Free Account", "https://www.grammarly.com/signup",
            "Create a free account. Premium features may require a paid plan for full scope coverage.", required=True),
    ],
    "hackerone:mozilla": [
        _cr("signup", "Firefox Account (Mozilla)", "https://accounts.firefox.com/signup",
            "Create a Mozilla account for testing Firefox Sync, Monitor, and Relay."),
    ],
    "hackerone:nordvpn": [
        _cr("signup", "NordVPN Trial Account", "https://nordvpn.com/risk-free/",
            "30-day money-back guarantee enables full feature testing including client apps."),
    ],
    "hackerone:paypal": [
        _cr("signup", "PayPal Personal Account", "https://www.paypal.com/us/webapps/mpp/account-selection",
            "Create a dedicated sandbox/personal account. NEVER test with real payment methods."),
        _cr("api_key", "PayPal Developer Sandbox", "https://developer.paypal.com/dashboard/",
            "Create sandbox accounts (buyer + seller) for payment flow testing."),
    ],
    "hackerone:slack": [
        _cr("signup", "Slack Workspace (Free)", "https://slack.com/get-started#/createnew",
            "Create a free Slack workspace for testing. You can also test as a guest in your own workspace."),
        _cr("api_key", "Slack App + Bot Token", "https://api.slack.com/apps",
            "Create a Slack app in your test workspace for API endpoint testing.", required=False),
    ],
    "hackerone:proton": [
        _cr("signup", "Proton Account (Free)", "https://account.proton.me/signup",
            "Free Proton account covers Mail, Calendar, and Drive scope."),
    ],
    "hackerone:twitch": [
        _cr("signup", "Twitch Streamer Account", "https://www.twitch.tv/signup",
            "Create a dedicated Twitch account. Streamer features available to all accounts."),
        _cr("api_key", "Twitch Developer App", "https://dev.twitch.tv/console/apps/create",
            "Register a Twitch application for OAuth and API testing.", required=False),
    ],
    "hackerone:tiktok": [
        _cr("signup", "TikTok Account", "https://www.tiktok.com/signup",
            "Create a dedicated TikTok account for testing."),
        _cr("api_key", "TikTok Developer API Access", "https://developers.tiktok.com/",
            "Apply for TikTok API access for endpoint testing.", required=False),
    ],
    "hackerone:doordash": [
        _cr("signup", "DoorDash Customer Account", "https://www.doordash.com/en-US/register/",
            "Free customer account. Dasher (driver) account available if testing delivery flows."),
    ],
    "hackerone:cloudflare": [
        _cr("signup", "Cloudflare Free Account", "https://dash.cloudflare.com/sign-up",
            "Free tier gives access to dashboard, API, and Workers. Add a test domain."),
        _cr("api_key", "Cloudflare API Token", "https://dash.cloudflare.com/profile/api-tokens",
            "Create a scoped API token for API endpoint testing."),
    ],
    "hackerone:uber": [
        _cr("signup", "Uber Rider Account", "https://auth.uber.com/v2/",
            "Create a dedicated Uber account. Use a separate phone number if possible."),
    ],

    # ── Bugcrowd programs ────────────────────────────────────────────────────
    "bugcrowd:tesla": [
        _cr("signup", "Tesla Account", "https://auth.tesla.com/en_us/oauth2/v3/authorize?...",
            "Standard Tesla account. If testing mobile app, install on a dedicated test device."),
    ],
    "bugcrowd:atlassian": [
        _cr("signup", "Atlassian Account (Free)", "https://id.atlassian.com/signup",
            "Free Atlassian account. Create a Jira Software / Confluence free-tier site for testing."),
        _cr("api_key", "Atlassian API Token", "https://id.atlassian.com/manage-profile/security/api-tokens",
            "Generate an API token for REST API testing.", required=False),
    ],
    "bugcrowd:okta": [
        _cr("signup", "Okta Developer Account (Free)", "https://developer.okta.com/signup/",
            "Free Okta Developer Edition includes full admin access to a test org."),
        _cr("api_key", "Okta API Token", "https://developer.okta.com/docs/guides/create-an-api-token/",
            "Create an API token from your dev org for REST API testing."),
    ],
    "bugcrowd:square": [
        _cr("signup", "Square Seller Account", "https://squareup.com/signup/us",
            "Free Square account. Use sandbox mode for payment testing."),
        _cr("api_key", "Square Sandbox API Key", "https://developer.squareup.com/apps",
            "Create a Square app and use the sandbox access token — never use production keys."),
    ],
    "bugcrowd:netgear": [
        _cr("other", "NETGEAR Device / Firmware", "https://www.netgear.com/support/",
            "Physical device or firmware image required. Check if program covers specific models.", required=False),
    ],
    "bugcrowd:western_digital": [
        _cr("signup", "WD Account", "https://accounts.mycloud.com/",
            "WD account required for My Cloud services testing."),
    ],

    # ── VRP programs ─────────────────────────────────────────────────────────
    "vrp:google": [
        _cr("signup", "Google Account", "https://accounts.google.com/signup",
            "Create a dedicated Google account for testing. Never use your personal Google account."),
        _cr("api_key", "Google Cloud Free Trial", "https://cloud.google.com/free",
            "300 USD free credit for GCP API and service testing.", required=False),
    ],
    "vrp:microsoft": [
        _cr("signup", "Microsoft Account", "https://account.microsoft.com/",
            "Create a dedicated Microsoft account. Azure free account available."),
        _cr("api_key", "Azure Free Account + Subscription", "https://azure.microsoft.com/en-us/free/",
            "Azure free tier for testing Azure services and Microsoft Graph API.", required=False),
    ],
    "vrp:apple": [
        _cr("signup", "Apple ID", "https://appleid.apple.com/account#!&page=create",
            "Dedicated Apple ID for testing. Required for App Store, iCloud, and Apple services."),
    ],
    "vrp:github": [
        _cr("signup", "GitHub Account (Free)", "https://github.com/signup",
            "Free GitHub account. Create test repositories and organizations as needed."),
        _cr("api_key", "GitHub Personal Access Token", "https://github.com/settings/tokens",
            "Create a fine-grained PAT for API testing.", required=False),
    ],
    "vrp:mozilla_foundation": [
        _cr("signup", "Firefox Account", "https://accounts.firefox.com/signup",
            "Mozilla account for testing Firefox Sync, Monitor, VPN, and related services."),
    ],
    "vrp:meta": [
        _cr("signup", "Facebook / Meta Account", "https://www.facebook.com/r.php",
            "Create a dedicated test Facebook account. Do not test using your personal account."),
        _cr("api_key", "Meta Developer App", "https://developers.facebook.com/apps/",
            "Create a Meta app for Graph API and Webhook testing.", required=False),
    ],
    "vrp:samsung": [
        _cr("signup", "Samsung Account", "https://account.samsung.com/membership/intro.do",
            "Samsung account for testing Samsung services, Galaxy Store, and cloud features."),
    ],
    "vrp:intel": [
        _cr("other", "Intel Product / Firmware", "https://www.intel.com/content/www/us/en/download-center/home.html",
            "Check program scope for specific Intel hardware or driver targets.", required=False),
    ],

    # ── Intigriti programs ───────────────────────────────────────────────────
    "intigriti:ing": [
        _cr("signup", "ING Bank Account (Sandbox)", "https://developer.ing.com/api-marketplace/",
            "Use the ING Open Banking sandbox environment with test credentials."),
        _cr("api_key", "ING Developer API Key", "https://developer.ing.com/api-marketplace/",
            "Register for API access to test Open Banking endpoints."),
    ],
    "intigriti:adidas": [
        _cr("signup", "Adidas Account", "https://www.adidas.com/us/join",
            "Create a free Adidas account for testing the website and app."),
    ],
    "intigriti:ab_inbev": [
        _cr("signup", "AB InBev / Bees Account", "https://www.beesapp.com/",
            "Bees platform account for B2B portal testing if in scope."),
    ],
    "intigriti:eu_commision": [],  # Public EU infrastructure — no credentials needed
    "intigriti:bol_com": [
        _cr("signup", "bol.com Account", "https://www.bol.com/nl/rnwy/account/registreren/",
            "Dutch/Belgian marketplace account for testing customer-facing features."),
        _cr("api_key", "bol.com Partner API", "https://developers.bol.com/",
            "Partner API access for testing seller and order API endpoints.", required=False),
    ],

    # ── Government CVD programs ──────────────────────────────────────────────
    # Government programs typically have no authentication requirements.
    # Only include entries where a government portal requires registration.
    "govt:us_dod": [],   # DISA public-facing systems — no login needed
    "govt:ncsc_uk": [],  # Public UK government systems
    "govt:bsi_de": [],   # Public German federal systems
}


def _inject_credentials() -> None:
    """Inject credential_requirements into each catalog entry from the mapping."""
    for opp in _CATALOG:
        creds = _CREDENTIAL_REQUIREMENTS.get(opp.id)
        if creds is not None:
            opp.credential_requirements = creds


_inject_credentials()


# ---------------------------------------------------------------------------
# Query functions
# ---------------------------------------------------------------------------

def get_all_opportunities() -> list[Opportunity]:
    """Return the full catalog sorted by priority_score descending."""
    return sorted(_CATALOG, key=lambda o: o.priority_score, reverse=True)


def get_opportunity(opp_id: str) -> Optional[Opportunity]:
    """Return a single opportunity by ID, or None if not found."""
    return next((o for o in _CATALOG if o.id == opp_id), None)


def list_filtered(
    *,
    platform: Optional[str] = None,
    access_type: Optional[str] = None,
    public_only: bool = False,
    min_payout: Optional[int] = None,
    tags: Optional[list[str]] = None,
    search: Optional[str] = None,
    limit: int = 100,
) -> list[Opportunity]:
    """
    Filter and return opportunities.

    Args:
        platform: Filter by platform ("hackerone", "bugcrowd", "intigriti", "vrp", "government_cvd")
        access_type: Filter by access type ("public_bbp", "public_vrp", "government_cvd", "invite_only")
        public_only: If True, only return programs with no authorization gate
        min_payout: Minimum max_payout_usd (0 includes VDPs)
        tags: Return only programs matching ANY of these tags
        search: Case-insensitive substring match on name / organization / scope_summary
        limit: Maximum results to return
    """
    results = get_all_opportunities()

    if platform:
        results = [o for o in results if o.platform == platform.lower()]

    if access_type:
        results = [o for o in results if o.access_type == access_type.lower()]

    if public_only:
        results = [o for o in results if o.is_public()]

    if min_payout is not None:
        results = [o for o in results if o.max_payout_usd >= min_payout]

    if tags:
        tag_set = {t.lower() for t in tags}
        results = [o for o in results if tag_set.intersection(o.tags)]

    if search:
        q = search.lower()
        results = [
            o for o in results
            if q in o.name.lower()
            or q in o.organization.lower()
            or q in o.scope_summary.lower()
        ]

    return results[:limit]


def rank_opportunities(
    opportunities: Optional[list[Opportunity]] = None,
    *,
    public_only: bool = False,
) -> list[Opportunity]:
    """Return opportunities sorted by priority_score, highest first."""
    items = opportunities if opportunities is not None else get_all_opportunities()
    if public_only:
        items = [o for o in items if o.is_public()]
    return sorted(items, key=lambda o: o.priority_score, reverse=True)


def catalog_stats() -> dict:
    """Return summary statistics about the catalog."""
    all_opps = get_all_opportunities()
    by_platform: dict[str, int] = {}
    by_access: dict[str, int] = {}
    for o in all_opps:
        by_platform[o.platform] = by_platform.get(o.platform, 0) + 1
        by_access[o.access_type] = by_access.get(o.access_type, 0) + 1
    return {
        "total": len(all_opps),
        "public_count": sum(1 for o in all_opps if o.is_public()),
        "with_payout": sum(1 for o in all_opps if not o.vdp_only),
        "vdp_only": sum(1 for o in all_opps if o.vdp_only),
        "by_platform": by_platform,
        "by_access_type": by_access,
        "highest_payout": max((o.max_payout_usd for o in all_opps), default=0),
    }
