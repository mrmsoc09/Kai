from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
from typing import Any
from urllib import error, parse, request

import yaml


NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
EXPLOITDB_API_BASE = "https://www.exploit-db.com/search"


@dataclass(slots=True)
class CVERecord:
    cve_id: str
    description: str
    affected_software: list[str]
    severity: str
    cvss: float
    published_date: str
    exploit_available: bool
    source: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cve_id": self.cve_id,
            "description": self.description,
            "affected_software": self.affected_software,
            "severity": self.severity,
            "cvss": self.cvss,
            "published_date": self.published_date,
            "exploit_available": self.exploit_available,
            "source": self.source,
        }


class MarketIntelligenceEngine:
    """
    Market intelligence engine for intelligent targeted scanning.

    - Pulls recent CVE/exploit signals when network+credentials are available.
    - Falls back to deterministic local snapshots when external APIs are unavailable.
    - Produces actionable affected-opportunity recommendations.
    """

    def __init__(
        self,
        *,
        cache_path: str | Path = "tools/intelligence/data/market_intelligence_cache.yaml",
        opportunities_path: str | Path = "tools/orchestration/data/opportunities.yaml",
        allow_network_fetch: bool = False,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)

        self.opportunities_path = Path(opportunities_path)
        self.allow_network_fetch = bool(allow_network_fetch)

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(value: str | None) -> str:
        return (value or "").strip().lower()

    @staticmethod
    def _severity_from_cvss(cvss: float) -> str:
        if cvss >= 9.0:
            return "CRITICAL"
        if cvss >= 7.0:
            return "HIGH"
        if cvss >= 4.0:
            return "MEDIUM"
        return "LOW"

    @staticmethod
    def _snapshot_cves() -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        rows = [
            CVERecord(
                cve_id="CVE-2026-24001",
                description="Template sandbox escape risk in popular Node.js rendering libraries.",
                affected_software=["node.js", "express", "react"],
                severity="HIGH",
                cvss=8.2,
                published_date=(now - timedelta(days=2)).isoformat(),
                exploit_available=True,
                source="offline_snapshot",
            ),
            CVERecord(
                cve_id="CVE-2026-24022",
                description="OAuth token validation bypass condition in common SSO middleware.",
                affected_software=["oauth", "sso", "api gateway", "jwt"],
                severity="CRITICAL",
                cvss=9.1,
                published_date=(now - timedelta(days=3)).isoformat(),
                exploit_available=False,
                source="offline_snapshot",
            ),
            CVERecord(
                cve_id="CVE-2026-24110",
                description="WAF normalization bypass in specific enterprise reverse proxy paths.",
                affected_software=["waf", "nginx", "apache", "asp.net"],
                severity="HIGH",
                cvss=7.8,
                published_date=(now - timedelta(days=1)).isoformat(),
                exploit_available=True,
                source="offline_snapshot",
            ),
            CVERecord(
                cve_id="CVE-2026-24208",
                description="Privilege boundary weakness in Kubernetes ingress-controller configurations.",
                affected_software=["kubernetes", "ingress", "api gateway"],
                severity="HIGH",
                cvss=8.0,
                published_date=(now - timedelta(days=4)).isoformat(),
                exploit_available=False,
                source="offline_snapshot",
            ),
            CVERecord(
                cve_id="CVE-2026-24260",
                description="Cryptographic downgrade acceptance in older TLS policy templates.",
                affected_software=["tls", "openssl", "java"],
                severity="MEDIUM",
                cvss=6.4,
                published_date=(now - timedelta(days=5)).isoformat(),
                exploit_available=True,
                source="offline_snapshot",
            ),
        ]
        return [row.as_dict() for row in rows]

    @staticmethod
    def _snapshot_exploits() -> list[dict[str, Any]]:
        now = datetime.now(UTC)
        return [
            {
                "exploit_id": "EDB-900001",
                "cve_id": "CVE-2026-24001",
                "title": "Template sandbox escape proof-of-concept",
                "platform": "webapps",
                "published_date": (now - timedelta(days=1)).isoformat(),
                "source": "offline_snapshot",
            },
            {
                "exploit_id": "EDB-900014",
                "cve_id": "CVE-2026-24110",
                "title": "Proxy normalization bypass verification script",
                "platform": "multiple",
                "published_date": (now - timedelta(days=2)).isoformat(),
                "source": "offline_snapshot",
            },
        ]

    def _http_json(self, url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> dict[str, Any]:
        req = request.Request(url=url, headers=headers or {})
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(raw) if raw else {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _extract_cpe_tokens(cpe_uri: str) -> list[str]:
        parts = cpe_uri.split(":")
        if len(parts) < 6:
            return []
        vendor = parts[3].replace("_", " ").strip().lower()
        product = parts[4].replace("_", " ").strip().lower()
        tokens = [x for x in {vendor, product, f"{vendor} {product}"} if x and x != "*"]
        return tokens

    def query_nvd_api(self, published_start_date: str) -> tuple[list[dict[str, Any]], str]:
        if not self.allow_network_fetch:
            return [], "network_fetch_disabled"

        params = {
            "pubStartDate": f"{published_start_date}T00:00:00.000Z",
            "resultsPerPage": "200",
        }
        url = f"{NVD_API_BASE}?{parse.urlencode(params)}"

        headers = {"Accept": "application/json"}
        api_key = os.getenv("NVD_API_KEY")
        if api_key:
            headers["apiKey"] = api_key

        try:
            payload = self._http_json(url, headers=headers)
        except (error.URLError, TimeoutError, json.JSONDecodeError):
            return [], "nvd_fetch_failed"

        vulns = payload.get("vulnerabilities", []) if isinstance(payload, dict) else []
        if not isinstance(vulns, list):
            return [], "nvd_payload_invalid"

        out: list[dict[str, Any]] = []
        for item in vulns:
            if not isinstance(item, dict):
                continue
            cve = item.get("cve", {}) if isinstance(item.get("cve"), dict) else {}
            cve_id = str(cve.get("id", "")).strip()
            if not cve_id:
                continue

            desc = ""
            descriptions = cve.get("descriptions", [])
            if isinstance(descriptions, list):
                for entry in descriptions:
                    if isinstance(entry, dict) and entry.get("lang") == "en":
                        desc = str(entry.get("value", "")).strip()
                        break

            cvss = 0.0
            severity = "MEDIUM"
            metrics = cve.get("metrics", {}) if isinstance(cve.get("metrics"), dict) else {}
            for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
                rows = metrics.get(key)
                if not isinstance(rows, list) or not rows:
                    continue
                first = rows[0]
                if not isinstance(first, dict):
                    continue
                data = first.get("cvssData", {}) if isinstance(first.get("cvssData"), dict) else {}
                try:
                    cvss = float(data.get("baseScore", 0.0))
                except (TypeError, ValueError):
                    cvss = 0.0
                severity = str(data.get("baseSeverity") or self._severity_from_cvss(cvss)).upper()
                break

            affected: set[str] = set()
            confs = cve.get("configurations", [])
            if isinstance(confs, list):
                for conf in confs:
                    if not isinstance(conf, dict):
                        continue
                    nodes = conf.get("nodes", [])
                    if not isinstance(nodes, list):
                        continue
                    for node in nodes:
                        if not isinstance(node, dict):
                            continue
                        cpe_matches = node.get("cpeMatch", [])
                        if not isinstance(cpe_matches, list):
                            continue
                        for cpe in cpe_matches:
                            if not isinstance(cpe, dict):
                                continue
                            crit = bool(cpe.get("vulnerable", True))
                            if not crit:
                                continue
                            cpe_uri = str(cpe.get("criteria", ""))
                            for token in self._extract_cpe_tokens(cpe_uri):
                                affected.add(token)

            exploit_available = any(marker in desc.lower() for marker in ("exploit", "poc", "proof of concept"))
            out.append(
                CVERecord(
                    cve_id=cve_id,
                    description=desc or "NVD description unavailable",
                    affected_software=sorted(affected),
                    severity=severity or self._severity_from_cvss(cvss),
                    cvss=cvss,
                    published_date=str(cve.get("published", self._now())),
                    exploit_available=exploit_available,
                    source="nvd_api",
                ).as_dict()
            )

        return out, "nvd_api"

    def fetch_nvd_recent_cves(self, days: int = 7) -> dict[str, Any]:
        cutoff_date = (datetime.now(UTC) - timedelta(days=max(1, int(days)))).date().isoformat()
        rows, mode = self.query_nvd_api(cutoff_date)
        if rows:
            return {
                "source_mode": mode,
                "days": days,
                "records": rows,
                "record_count": len(rows),
            }

        snap = self._snapshot_cves()
        return {
            "source_mode": "offline_snapshot",
            "days": days,
            "records": snap,
            "record_count": len(snap),
            "fallback_reason": mode,
        }

    def fetch_exploitdb_recent(self, days: int = 7) -> dict[str, Any]:
        # ExploitDB does not provide a simple stable unauthenticated JSON API for this use.
        # For deterministic operation we use offline snapshots unless a custom source is wired.
        _ = days
        return {
            "source_mode": "offline_snapshot",
            "days": days,
            "records": self._snapshot_exploits(),
            "record_count": len(self._snapshot_exploits()),
            "fallback_reason": "exploitdb_remote_fetch_not_configured",
            "source_hint": EXPLOITDB_API_BASE,
        }

    @staticmethod
    def _opportunity_tech_stack(opportunity: dict[str, Any]) -> list[str]:
        tech = opportunity.get("detected_tech_stack") or opportunity.get("tech_stack") or []
        if isinstance(tech, str):
            return [tech]
        if isinstance(tech, list):
            return [str(x) for x in tech]
        return []

    def opportunity_has_affected_software(self, opportunity: dict[str, Any], affected_software: list[str]) -> bool:
        opp_tokens = " ".join(self._opportunity_tech_stack(opportunity)).lower()
        if not opp_tokens.strip():
            return False
        return any(self._normalize(token) in opp_tokens for token in affected_software if str(token).strip())

    def find_matching_cves(self, tech_stack: list[str], nvd_recent: list[dict[str, Any]]) -> list[dict[str, Any]]:
        haystack = " ".join(str(x) for x in tech_stack).lower()
        out: list[dict[str, Any]] = []
        for row in nvd_recent:
            affected = row.get("affected_software", [])
            if not isinstance(affected, list):
                continue
            if any(self._normalize(token) in haystack for token in affected if str(token).strip()):
                out.append(row)
        return out

    @staticmethod
    def recommend_narrow_scan(matching_cves: list[dict[str, Any]]) -> dict[str, Any]:
        cve_ids = [str(c.get("cve_id")) for c in matching_cves if c.get("cve_id")]
        high = [c for c in matching_cves if str(c.get("severity", "")).upper() in {"HIGH", "CRITICAL"}]
        return {
            "focus_cves": cve_ids,
            "priority": "high" if high else "medium",
            "scan_focus": "targeted_cve_validation",
            "recommended_playbook_profile": "intelligent_targeted",
        }

    @staticmethod
    def _severity_weight(severity: str) -> float:
        level = (severity or "").upper()
        if level == "CRITICAL":
            return 1.0
        if level == "HIGH":
            return 0.8
        if level == "MEDIUM":
            return 0.5
        return 0.3

    def calculate_priority(self, cve: dict[str, Any], affected_count: int) -> float:
        severity = self._severity_weight(str(cve.get("severity", "MEDIUM")))
        cvss = min(10.0, max(0.0, float(cve.get("cvss", 0.0)))) / 10.0
        exploit = 1.0 if bool(cve.get("exploit_available", False)) else 0.4
        scope_scale = min(1.0, affected_count / 15.0)
        return round((severity * 0.35) + (cvss * 0.30) + (exploit * 0.20) + (scope_scale * 0.15), 4)

    def identify_intelligent_scan_opportunities(
        self,
        all_opportunities: list[dict[str, Any]],
        market_intel: dict[str, Any],
    ) -> list[dict[str, Any]]:
        cves = market_intel.get("sources", {}).get("nvd", {}).get("records", [])
        if not isinstance(cves, list):
            cves = []

        intelligent_scans: list[dict[str, Any]] = []
        for cve in cves:
            affected = [
                opp
                for opp in all_opportunities
                if self.opportunity_has_affected_software(opp, cve.get("affected_software", []))
            ]
            if len(affected) < 2:
                continue

            intelligent_scans.append(
                {
                    "scan_type": "intelligent_targeted",
                    "trigger_cve": cve.get("cve_id"),
                    "affected_opportunities": [str(opp.get("id") or opp.get("opportunity_id")) for opp in affected],
                    "number_affected": len(affected),
                    "priority": self.calculate_priority(cve, len(affected)),
                    "narrow_scan_focus": f"validate indicators for {cve.get('cve_id')}",
                    "recommended_narrow_scan": self.recommend_narrow_scan([cve]),
                    "source": cve.get("source", "unknown"),
                }
            )

        intelligent_scans.sort(key=lambda row: float(row.get("priority", 0.0)), reverse=True)
        return intelligent_scans

    def load_all_opportunities(self) -> list[dict[str, Any]]:
        if not self.opportunities_path.exists():
            return []
        payload = yaml.safe_load(self.opportunities_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return []
        opportunities = payload.get("opportunities", [])
        if not isinstance(opportunities, list):
            return []
        return [x for x in opportunities if isinstance(x, dict)]

    def update_market_intelligence_daily(
        self,
        opportunities: list[dict[str, Any]] | None = None,
        *,
        days: int = 7,
    ) -> dict[str, Any]:
        all_opps = opportunities if opportunities is not None else self.load_all_opportunities()

        nvd_recent = self.fetch_nvd_recent_cves(days=days)
        exploitdb_recent = self.fetch_exploitdb_recent(days=days)

        opportunities_affected: list[dict[str, Any]] = []
        nvd_rows = nvd_recent.get("records", []) if isinstance(nvd_recent, dict) else []
        for opp in all_opps:
            tech_stack = self._opportunity_tech_stack(opp)
            matching = self.find_matching_cves(tech_stack, nvd_rows if isinstance(nvd_rows, list) else [])
            if not matching:
                continue

            opportunities_affected.append(
                {
                    "opportunity_id": opp.get("id") or opp.get("opportunity_id"),
                    "matching_cves": [m.get("cve_id") for m in matching],
                    "recommended_narrow_scan": self.recommend_narrow_scan(matching),
                }
            )

        intelligence = {
            "update_timestamp": self._now(),
            "sources": {
                "nvd": nvd_recent,
                "exploitdb": exploitdb_recent,
            },
            "opportunities_with_market_intelligence": opportunities_affected,
            "intelligent_scan_candidates": self.identify_intelligent_scan_opportunities(
                all_opps,
                {
                    "sources": {
                        "nvd": nvd_recent,
                        "exploitdb": exploitdb_recent,
                    }
                },
            ),
        }

        self.cache_path.write_text(yaml.safe_dump(intelligence, sort_keys=False), encoding="utf-8")
        return intelligence


__all__ = ["MarketIntelligenceEngine", "CVERecord", "NVD_API_BASE", "EXPLOITDB_API_BASE"]
