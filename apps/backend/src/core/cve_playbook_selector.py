from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import re
from typing import Any

import yaml

from apps.backend.src.tools.knowledge.cve_base import CVEKnowledgeBase

logger = logging.getLogger(__name__)


_VERSION_RE = re.compile(r"\b\d+(?:\.\d+){1,3}\b")

# Lightweight canonicalization map from observed service/tech labels to
# CVE KB product labels.
_PRODUCT_ALIASES: dict[str, str] = {
    "nginx": "Nginx",
    "apache": "Apache HTTP Server",
    "apache http server": "Apache HTTP Server",
    "httpd": "Apache HTTP Server",
    "openssl": "OpenSSL",
    "wordpress": "WordPress",
    "php": "PHP",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mariadb": "MariaDB",
    "node": "Node.js",
    "nodejs": "Node.js",
    "django": "Django",
    "flask": "Flask",
    "drupal": "Drupal",
    "joomla": "Joomla",
    "grafana": "Grafana",
    "prometheus": "Prometheus",
    "kubernetes": "Kubernetes",
    "redis": "Redis",
    "elasticsearch": "Elasticsearch",
    "mongodb": "MongoDB",
    "tomcat": "Apache Tomcat",
}


@dataclass(frozen=True)
class _Fingerprint:
    product: str
    version: str | None
    source: str


class CVEPlaybookSelector:
    """
    Maps discovered service/technology signals to CVE intelligence and playbooks.
    Utilizes O(1) JSON indices for high-velocity lookup.
    """

    def __init__(
        self,
        *,
        cve_knowledge_path: str | None = None,
        playbook_registry_path: str | None = None,
        playbook_index_path: str | None = None,
        cve_index_path: str | None = None,
    ) -> None:
        root = Path(__file__).resolve().parents[3]
        cve_path = Path(
            cve_knowledge_path
            or os.getenv("K1_CVE_KNOWLEDGE_PATH", "tools/knowledge/cve_knowledge.yaml")
        )
        registry_path = Path(
            playbook_registry_path
            or os.getenv("K1_PLAYBOOK_REGISTRY_PATH", "tools/playbooks/playbook_registry.yaml")
        )
        pb_index_path = Path(
            playbook_index_path or "tools/playbooks/playbook_index.json"
        )
        cv_index_path = Path(
            cve_index_path or "tools/playbooks/chain_orchestration/cve_index.json"
        )

        self._kb = CVEKnowledgeBase(cve_path)
        self._registry_rows = self._load_registry(registry_path)
        
        # Load O(1) indices
        self._playbook_index = self._load_json_index(pb_index_path)
        self._cve_index = self._load_json_index(cv_index_path)
        
        # Build success weight map for prioritization
        self._success_weights = {
            item["id"]: item.get("success_weight", 0.5)
            for item in self._playbook_index.get("playbooks_by_success_weight", [])
        }

    @staticmethod
    def _load_registry(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            registry = payload.get("playbook_registry") or {}
            rows = registry.get("playbooks")
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.error(f"Failed to load playbook registry: {e}")
            return []

    @staticmethod
    def _load_json_index(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load JSON index {path}: {e}")
            return {}

    def select_for_signals(
        self,
        *,
        signals: list[dict[str, Any]],
        prioritized_findings: list[dict[str, Any]] | None = None,
        max_recommendations: int = 6,
    ) -> dict[str, Any]:
        fingerprints = self._extract_fingerprints(signals, prioritized_findings or [])
        cve_matches = self._find_matching_cves(fingerprints)
        recommendations = self._rank_recommendations(cve_matches)

        selected = recommendations[:max(1, max_recommendations)]
        chain = [entry["playbook_id"] for entry in selected]
        return {
            "fingerprints": [fp.__dict__ for fp in fingerprints],
            "cve_matches": cve_matches[:24],
            "playbook_recommendations": selected,
            "chain_plan": chain,
        }

    def _extract_fingerprints(
        self,
        signals: list[dict[str, Any]],
        prioritized_findings: list[dict[str, Any]],
    ) -> list[_Fingerprint]:
        items: list[_Fingerprint] = []

        def add_candidate(raw_label: str, source: str) -> None:
            label = str(raw_label or "").strip()
            if not label:
                return
            version_match = _VERSION_RE.search(label)
            version = version_match.group(0) if version_match else None
            normalized = label.lower()
            if version:
                normalized = normalized.replace(version, "").strip(" -_/")
            product = _PRODUCT_ALIASES.get(normalized)
            if not product:
                # Best-effort title normalization fallback.
                product = normalized.replace("_", " ").replace("-", " ").title()
            items.append(_Fingerprint(product=product, version=version, source=source))

        for row in signals:
            source_tool = str(row.get("source_tool") or "unknown")
            for key in ("service", "technology", "title"):
                value = row.get(key)
                if isinstance(value, str):
                    add_candidate(value, source_tool)
            technologies = row.get("technologies")
            if isinstance(technologies, list):
                for tech in technologies:
                    if isinstance(tech, str):
                        add_candidate(tech, source_tool)

        for finding in prioritized_findings:
            reason = finding.get("reason")
            if isinstance(reason, str):
                add_candidate(reason, "priority_reason")

        # Deduplicate while preserving order.
        seen: set[tuple[str, str | None]] = set()
        unique: list[_Fingerprint] = []
        for fp in items:
            key = (fp.product.lower(), fp.version)
            if key in seen:
                continue
            seen.add(key)
            unique.append(fp)
        return unique

    def _find_matching_cves(self, fingerprints: list[_Fingerprint]) -> list[dict[str, Any]]:
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()

        for fp in fingerprints:
            # 1. Try O(1) lookup in cve_index.json first if we have a direct CVE ID (rare in fingerprints)
            # 2. Use KB for product/version matching
            try:
                cves = self._kb.find_cves_by_product(fp.product, fp.version)
            except Exception as exc:
                logger.debug("CVE lookup failed for %s: %s", fp.product, exc)
                continue

            for cve in cves[:20]:
                meta = cve.get("metadata", {}) if isinstance(cve, dict) else {}
                vuln = cve.get("vulnerability", {}) if isinstance(cve, dict) else {}
                cve_id = str(meta.get("cve_id") or "").strip()
                if not cve_id or cve_id in seen:
                    continue
                seen.add(cve_id)
                
                # Enrich with index data if present
                indexed_playbooks = self._cve_index.get(cve_id, [])
                playbook_ids = [p["playbook_id"] for p in indexed_playbooks] if indexed_playbooks else self._extract_cve_playbooks(cve)

                matches.append(
                    {
                        "cve_id": cve_id,
                        "product": vuln.get("product"),
                        "affected_versions": vuln.get("affected_versions", []),
                        "vulnerability_type": vuln.get("vulnerability_type"),
                        "severity": str(meta.get("severity") or "UNKNOWN").upper(),
                        "cvss_score": float(meta.get("cvss_score") or 0.0),
                        "fingerprint_source": fp.source,
                        "playbooks": playbook_ids,
                    }
                )

        matches.sort(
            key=lambda row: (float(row.get("cvss_score", 0.0)), str(row.get("severity", ""))),
            reverse=True,
        )
        return matches

    @staticmethod
    def _extract_cve_playbooks(cve: dict[str, Any]) -> list[str]:
        persona_mapping = cve.get("persona_mapping", {})
        if not isinstance(persona_mapping, dict):
            return []
        playbooks = persona_mapping.get("playbooks")
        if not isinstance(playbooks, list):
            return []
        out: list[str] = []
        for entry in playbooks:
            if isinstance(entry, dict):
                name = str(entry.get("playbook") or "").strip()
                if name:
                    out.append(name)
        return out

    def _rank_recommendations(self, cve_matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_playbook: dict[str, dict[str, Any]] = {}
        id_lookup = {
            str(row.get("id") or ""): row
            for row in self._registry_rows
            if isinstance(row, dict)
        }

        for match in cve_matches:
            linked = match.get("playbooks")
            if not isinstance(linked, list):
                continue
            for playbook_id in linked:
                registry = id_lookup.get(str(playbook_id))
                if not registry:
                    continue
                row = by_playbook.setdefault(
                    playbook_id,
                    {
                        "playbook_id": playbook_id,
                        "playbook_name": registry.get("name", playbook_id),
                        "path": registry.get("path"),
                        "score": 0.0,
                        "supporting_cves": [],
                        "chainable": self._is_chainable_playbook(registry),
                        "success_weight": self._success_weights.get(playbook_id, 0.5),
                    },
                )
                
                # Priority Logic: Success Weight * CVSS Score
                score = float(match.get("cvss_score") or 0.0) * row["success_weight"]
                
                if row["chainable"]:
                    score += 2.0  # Increased bonus for chainable logic
                
                row["score"] += score
                row["supporting_cves"].append(
                    {
                        "cve_id": match.get("cve_id"),
                        "severity": match.get("severity"),
                        "cvss_score": match.get("cvss_score"),
                        "vulnerability_type": match.get("vulnerability_type"),
                    }
                )

        recs = list(by_playbook.values())
        # Final sort prioritizing score and successful observed history
        recs.sort(key=lambda row: (float(row["score"]), row["success_weight"]), reverse=True)
        return recs

    @staticmethod
    def _is_chainable_playbook(registry_row: dict[str, Any]) -> bool:
        tags = registry_row.get("tags")
        if not isinstance(tags, list):
            return False
        # Extended needles for chainable logic
        needles = (
            "auth-bypass",
            "auth",
            "lateral",
            "privilege",
            "rce",
            "sqli",
            "xss",
            "data-exfiltration",
            "info-leak",
            "config-disclosure",
        )
        lowered = " ".join(str(tag).lower() for tag in tags)
        return any(needle in lowered for needle in needles)
