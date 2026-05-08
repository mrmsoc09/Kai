"""
K1 Wordlist Manager — single source of truth for all wordlist paths.

Knows the full SecLists catalog, maps scan phases + tech stacks to the right
lists, and provides graceful fallback to bundled minimal lists when SecLists
is not yet installed.

Environment:
  K1_SECLISTS_PATH   — root of SecLists clone (default: /opt/seclists)
                        Falls back to: {KAI_ROOT}/wordlists/SecLists
  K1_SECLISTS_SPARSE — "1" if only high-priority lists were cloned
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ── Resolve SecLists root ─────────────────────────────────────────────────

def _seclists_root() -> Path:
    env = os.getenv("K1_SECLISTS_PATH", "").strip()
    if env and Path(env).is_dir():
        return Path(env)
    # Relative to this file: KAI/apps/backend/src/core/ → KAI/wordlists/SecLists
    local = Path(__file__).parents[4] / "wordlists" / "SecLists"
    if local.is_dir():
        return local
    # System install (Kali / Parrot)
    system = Path("/usr/share/seclists")
    if system.is_dir():
        return system
    # Default Docker install path
    return Path("/opt/seclists")


SECLISTS = _seclists_root()

# ── Bundled minimal fallback wordlists (committed to repo) ────────────────
_BUNDLED_ROOT = Path(__file__).parents[4] / "wordlists" / "bundled"

# ─────────────────────────────────────────────────────────────────────────────
# Catalog — maps logical name → path relative to SECLISTS root
# ─────────────────────────────────────────────────────────────────────────────

CATALOG: dict[str, str] = {
    # ── Content Discovery ──────────────────────────────────────────────────
    "content/common":             "Discovery/Web-Content/common.txt",
    "content/big":                "Discovery/Web-Content/big.txt",
    "content/quickhits":          "Discovery/Web-Content/quickhits.txt",
    "content/dir-small":          "Discovery/Web-Content/directory-list-2.3-small.txt",
    "content/dir-medium":         "Discovery/Web-Content/directory-list-2.3-medium.txt",
    "content/dir-large":          "Discovery/Web-Content/directory-list-2.3-big.txt",
    "content/raft-small":         "Discovery/Web-Content/raft-small-words.txt",
    "content/raft-medium":        "Discovery/Web-Content/raft-medium-words.txt",
    "content/raft-large":         "Discovery/Web-Content/raft-large-words.txt",
    "content/raft-small-dirs":    "Discovery/Web-Content/raft-small-directories.txt",
    "content/raft-medium-dirs":   "Discovery/Web-Content/raft-medium-directories.txt",

    # ── API Discovery ──────────────────────────────────────────────────────
    "api/endpoints":              "Discovery/Web-Content/api/api-endpoints.txt",
    "api/endpoints-res":          "Discovery/Web-Content/api/api-endpoints-res.txt",
    "api/objects":                "Discovery/Web-Content/api/objects.txt",
    "api/actions":                "Discovery/Web-Content/api/actions.txt",

    # ── CMS ────────────────────────────────────────────────────────────────
    "cms/wordpress":              "Discovery/Web-Content/CMS/wordpress.fuzz.txt",
    "cms/drupal":                 "Discovery/Web-Content/CMS/drupal.txt",
    "cms/joomla":                 "Discovery/Web-Content/CMS/joomla.txt",
    "cms/magento":                "Discovery/Web-Content/CMS/magento.txt",
    "cms/sharepoint":             "Discovery/Web-Content/CMS/sharepoint.txt",

    # ── DNS / Subdomains ───────────────────────────────────────────────────
    "dns/subdomains-5k":          "Discovery/DNS/subdomains-top1million-5000.txt",
    "dns/subdomains-20k":         "Discovery/DNS/subdomains-top1million-20000.txt",
    "dns/subdomains-110k":        "Discovery/DNS/subdomains-top1million-110000.txt",
    "dns/bitquark-100k":          "Discovery/DNS/bitquark-subdomains-top100000.txt",
    "dns/fierce":                 "Discovery/DNS/fierce-hostlist.txt",
    "dns/shubs-subdomains":       "Discovery/DNS/shubs-subdomains.txt",

    # ── Fuzzing payloads ───────────────────────────────────────────────────
    "fuzz/sqli":                  "Fuzzing/SQLi/Generic-SQLi.txt",
    "fuzz/sqli-quick":            "Fuzzing/SQLi/quick-SQLi.txt",
    "fuzz/xss":                   "Fuzzing/XSS/XSS-Jhaddix.txt",
    "fuzz/xss-brutal":            "Fuzzing/XSS/XSS-BruteLogic.txt",
    "fuzz/lfi":                   "Fuzzing/LFI/LFI-Jhaddix.txt",
    "fuzz/lfi-linux":             "Fuzzing/LFI/LFI-gracefulsecurity-linux.txt",
    "fuzz/lfi-windows":           "Fuzzing/LFI/LFI-gracefulsecurity-windows.txt",
    "fuzz/ssrf":                  "Fuzzing/SSRF/Ssrf.php.txt",
    "fuzz/xxe":                   "Fuzzing/XXE/XXEFuzzing.txt",
    "fuzz/ssti":                  "Fuzzing/SSTI/ssti.txt",
    "fuzz/traversal":             "Fuzzing/traversal.txt",
    "fuzz/polyglots":             "Fuzzing/polyglots.txt",
    "fuzz/open-redirect":         "Fuzzing/Open-Redirect/Open-Redirect.txt",

    # ── Passwords ──────────────────────────────────────────────────────────
    "passwords/10k":              "Passwords/Common-Credentials/10k-most-common.txt",
    "passwords/100k":             "Passwords/Common-Credentials/100k-most-common.txt",
    "passwords/top-20":           "Passwords/Common-Credentials/top-20-common-SSH-passwords.txt",
    "passwords/windows":          "Passwords/Common-Credentials/common-passwords-win.txt",
    "passwords/rockyou-75":       "Passwords/Leaked-Databases/rockyou-75.txt",

    # ── Usernames ──────────────────────────────────────────────────────────
    "usernames/top-shortlist":    "Usernames/top-usernames-shortlist.txt",
    "usernames/names":            "Usernames/Names/names.txt",
    "usernames/10m":              "Usernames/xato-net-10-million-usernames.txt",
}

# ── Bundled minimal fallbacks (tracked in repo, tiny) ─────────────────────
_FALLBACKS: dict[str, list[str]] = {
    "content/common":   ["wordlists/bundled/content-common.txt"],
    "dns/subdomains-5k": ["wordlists/bundled/subdomains-5k.txt"],
    "fuzz/sqli":        ["wordlists/bundled/sqli-quick.txt"],
    "fuzz/xss":         ["wordlists/bundled/xss-quick.txt"],
}

# ── Phase → wordlist key mapping ───────────────────────────────────────────

_PHASE_DEFAULTS: dict[str, list[str]] = {
    "recon":           ["dns/subdomains-5k", "dns/subdomains-20k"],
    "fingerprinting":  ["content/quickhits", "content/common"],
    "discovery":       ["content/dir-medium", "api/endpoints", "content/raft-medium"],
    "osint":           ["dns/subdomains-20k", "usernames/top-shortlist"],
    "vuln_scanning":   ["fuzz/sqli", "fuzz/xss", "fuzz/lfi", "fuzz/ssrf", "fuzz/xxe"],
    "api_testing":     ["api/endpoints", "api/objects", "api/actions", "fuzz/sqli", "fuzz/ssti"],
    "brute_force":     ["passwords/10k", "usernames/top-shortlist"],
    "aggregation":     ["content/common"],
}

# ── Tech stack → additional wordlist keys ──────────────────────────────────

_TECH_EXTRAS: dict[str, list[str]] = {
    "wordpress":   ["cms/wordpress"],
    "drupal":      ["cms/drupal"],
    "joomla":      ["cms/joomla"],
    "magento":     ["cms/magento"],
    "sharepoint":  ["cms/sharepoint"],
    "php":         ["content/common"],
    "django":      ["api/endpoints"],
    "rails":       ["api/endpoints"],
    "spring":      ["api/endpoints", "api/objects"],
    "graphql":     ["api/actions", "api/objects"],
    "rest":        ["api/endpoints", "api/endpoints-res"],
    "laravel":     ["content/common"],
    "nginx":       ["content/quickhits"],
    "apache":      ["content/quickhits"],
}


# ─────────────────────────────────────────────────────────────────────────────
# WordlistManager
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class WordlistEntry:
    key: str
    path: Path
    exists: bool
    size_lines: Optional[int] = None
    category: str = ""

    @property
    def name(self) -> str:
        return self.key.split("/")[-1]


class WordlistManager:
    """
    Single source of truth for wordlist resolution across the K1 platform.

    Tools should call:
        wm = get_wordlist_manager()
        path = wm.get("content/common")          # single wordlist
        paths = wm.for_phase("discovery")        # all lists for a phase
        paths = wm.for_phase("discovery", tech_stack=["wordpress", "php"])
    """

    def __init__(self, seclists_root: Optional[Path] = None) -> None:
        self._root = seclists_root or SECLISTS
        self._available: Optional[bool] = None

    # ── Availability ───────────────────────────────────────────────────────

    def is_available(self) -> bool:
        if self._available is None:
            marker = self._root / ".kai_installed"
            readme = self._root / "README.md"
            self._available = marker.is_file() or readme.is_file()
            if self._available:
                logger.info("WordlistManager: SecLists found at %s", self._root)
            else:
                logger.warning(
                    "WordlistManager: SecLists not found at %s — "
                    "run: scripts/install_seclists.sh",
                    self._root,
                )
        return self._available

    # ── Path resolution ────────────────────────────────────────────────────

    def get(self, key: str, require: bool = False) -> Optional[Path]:
        """
        Return the absolute path for a wordlist key (e.g. "content/common").
        Returns None if the file does not exist and *require* is False.
        Falls back to bundled minimal wordlist if available.
        """
        rel = CATALOG.get(key)
        if rel is None:
            logger.warning("WordlistManager: unknown key %r", key)
            return None

        full = self._root / rel
        if full.is_file():
            return full

        # Bundled fallback
        for fb_rel in _FALLBACKS.get(key, []):
            fb = Path(__file__).parents[4] / fb_rel
            if fb.is_file():
                logger.debug("WordlistManager: using bundled fallback for %s", key)
                return fb

        if require:
            raise FileNotFoundError(
                f"Wordlist {key!r} not found at {full}. "
                "Run: scripts/install_seclists.sh"
            )
        logger.debug("WordlistManager: wordlist not found: %s", full)
        return None

    def get_or_fallback(self, key: str, fallback_key: str) -> Optional[Path]:
        """Try *key*, return *fallback_key* if not found."""
        return self.get(key) or self.get(fallback_key)

    # ── Phase / tech-stack selection ───────────────────────────────────────

    def for_phase(
        self,
        phase: str,
        tech_stack: Optional[list[str]] = None,
    ) -> list[Path]:
        """
        Return available wordlist paths for a scan phase, optionally
        enriched with tech-stack-specific lists.
        """
        keys = list(_PHASE_DEFAULTS.get(phase, _PHASE_DEFAULTS["discovery"]))

        for tech in (tech_stack or []):
            for k in _TECH_EXTRAS.get(tech.lower(), []):
                if k not in keys:
                    keys.append(k)

        paths = []
        for k in keys:
            p = self.get(k)
            if p:
                paths.append(p)

        if not paths:
            # Last-resort: return bundled common list if we have it
            p = self.get("content/common")
            if p:
                paths.append(p)

        return paths

    # ── Catalog ────────────────────────────────────────────────────────────

    def catalog(self, only_existing: bool = True) -> list[WordlistEntry]:
        """List all wordlists, optionally filtering to only installed files."""
        entries = []
        for key, rel in CATALOG.items():
            full = self._root / rel
            exists = full.is_file()
            if only_existing and not exists:
                continue
            category = key.split("/")[0]
            size = None
            if exists:
                try:
                    with open(full, "rb") as f:
                        size = sum(1 for _ in f)
                except OSError:
                    pass
            entries.append(WordlistEntry(
                key=key, path=full, exists=exists,
                size_lines=size, category=category,
            ))
        return entries

    # ── Convenience: best content-discovery list ──────────────────────────

    def best_content_list(self, prefer_speed: bool = False) -> Optional[Path]:
        """Return the best available content-discovery wordlist."""
        if prefer_speed:
            order = ["content/quickhits", "content/common", "content/dir-small"]
        else:
            order = ["content/dir-medium", "content/raft-medium", "content/common"]
        for key in order:
            p = self.get(key)
            if p:
                return p
        return None

    def best_subdomain_list(self, size: str = "medium") -> Optional[Path]:
        """Return best available subdomain wordlist. size: small|medium|large"""
        mapping = {
            "small":  "dns/subdomains-5k",
            "medium": "dns/subdomains-20k",
            "large":  "dns/subdomains-110k",
        }
        key = mapping.get(size, "dns/subdomains-20k")
        return self.get(key) or self.get("dns/subdomains-5k")

    def status(self) -> dict:
        """Return install status dict for health/status endpoints."""
        installed_count = sum(
            1 for rel in CATALOG.values() if (self._root / rel).is_file()
        )
        return {
            "available": self.is_available(),
            "path": str(self._root),
            "total_catalog_entries": len(CATALOG),
            "installed_entries": installed_count,
            "install_command": "scripts/install_seclists.sh",
        }


# ── Singleton ─────────────────────────────────────────────────────────────

_WM: Optional[WordlistManager] = None


def get_wordlist_manager() -> WordlistManager:
    global _WM
    if _WM is None:
        _WM = WordlistManager()
    return _WM


def reset_wordlist_manager() -> None:
    """Force re-initialisation (for tests)."""
    global _WM
    _WM = None
