"""Finding deduplication engine using multiple matching strategies."""

import hashlib
import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from difflib import SequenceMatcher


class FindingDeduplicator:
    """Deduplicate findings using multiple hashing and similarity strategies."""

    # Similarity threshold for fuzzy matching (0-1)
    SIMILARITY_THRESHOLD = 0.85

    # Exact match weight
    EXACT_MATCH_WEIGHT = 1.0

    # Fuzzy match weight
    FUZZY_MATCH_WEIGHT = 0.8

    def __init__(self):
        """Initialize deduplicator."""
        self.finding_hashes: Dict[str, Dict[str, Any]] = {}
        self.normalized_findings: Dict[str, Dict[str, Any]] = {}

    def compute_finding_hash(
        self,
        finding: Dict[str, Any],
        hash_type: str = "primary",
    ) -> str:
        """
        Compute hash of a finding for deduplication.

        Hash types:
        - primary: Full finding (URL + vulnerability type + severity)
        - shallow: Just URL and type
        - deep: URL + type + description snippet
        """
        if hash_type == "shallow":
            key_parts = [
                finding.get("url", ""),
                finding.get("vulnerability_type", ""),
            ]
        elif hash_type == "deep":
            key_parts = [
                finding.get("url", ""),
                finding.get("vulnerability_type", ""),
                finding.get("description", "")[:100],  # First 100 chars
            ]
        else:  # primary (default)
            key_parts = [
                finding.get("url", ""),
                finding.get("vulnerability_type", ""),
                finding.get("severity", "medium"),
                finding.get("parameter", ""),
            ]

        hash_input = "|".join(str(p) for p in key_parts)
        return hashlib.sha256(hash_input.encode()).hexdigest()

    def normalize_finding(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize a finding for comparison.

        Handles:
        - URL normalization (remove query params, fragments)
        - Vulnerability type standardization
        - Description cleaning
        """
        normalized = finding.copy()

        # Normalize URL
        if "url" in normalized:
            url = normalized["url"]
            # Remove fragment
            url = url.split("#")[0]
            # Keep query params for now but remove trailing slashes
            url = url.rstrip("/")
            normalized["url"] = url

        # Standardize vulnerability type
        if "vulnerability_type" in normalized:
            vuln_type = normalized["vulnerability_type"].lower()
            # Map common variations
            type_mappings = {
                "sql": "sql_injection",
                "sqli": "sql_injection",
                "xss": "cross_site_scripting",
                "csrf": "cross_site_request_forgery",
                "lfi": "local_file_inclusion",
                "rfi": "remote_file_inclusion",
                "xxe": "xml_external_entity",
                "oscommand": "os_command_injection",
                "path_traversal": "directory_traversal",
                "auth": "authentication_bypass",
                "authbypass": "authentication_bypass",
            }
            normalized["vulnerability_type"] = type_mappings.get(vuln_type, vuln_type)

        # Clean description
        if "description" in normalized:
            normalized["description"] = normalized["description"].strip()

        return normalized

    def is_duplicate(
        self,
        finding: Dict[str, Any],
        existing_findings: List[Dict[str, Any]],
        strategy: str = "multi",
    ) -> Tuple[bool, Optional[Dict[str, Any]], float]:
        """
        Check if finding is duplicate using specified strategy.

        Strategies:
        - exact: Primary hash match only
        - shallow: Primary + shallow hash match
        - fuzzy: Similarity-based matching
        - multi: All strategies (most thorough)

        Returns: (is_duplicate, matching_finding, confidence_score)
        """
        normalized_finding = self.normalize_finding(finding)
        primary_hash = self.compute_finding_hash(normalized_finding, "primary")
        shallow_hash = self.compute_finding_hash(normalized_finding, "shallow")

        for existing in existing_findings:
            normalized_existing = self.normalize_finding(existing)
            existing_primary = self.compute_finding_hash(normalized_existing, "primary")
            existing_shallow = self.compute_finding_hash(normalized_existing, "shallow")

            # Exact match on primary hash
            if strategy in ["exact", "shallow", "multi"]:
                if primary_hash == existing_primary:
                    return True, existing, self.EXACT_MATCH_WEIGHT

            # Exact match on shallow hash (same URL + type)
            if strategy in ["shallow", "multi"]:
                if shallow_hash == existing_shallow:
                    # Verify not just by hash but also by URL+type match
                    if (
                        normalized_finding.get("url") == normalized_existing.get("url")
                        and normalized_finding.get("vulnerability_type")
                        == normalized_existing.get("vulnerability_type")
                    ):
                        return True, existing, self.EXACT_MATCH_WEIGHT * 0.9

            # Fuzzy matching
            if strategy in ["fuzzy", "multi"]:
                similarity = self._compute_similarity(normalized_finding, normalized_existing)
                if similarity >= self.SIMILARITY_THRESHOLD:
                    return True, existing, similarity

        return False, None, 0.0

    def deduplicate(
        self,
        findings: List[Dict[str, Any]],
        strategy: str = "multi",
        keep_older: bool = True,
    ) -> Dict[str, Any]:
        """
        Deduplicate a batch of findings.

        Args:
            findings: List of findings to deduplicate
            strategy: Deduplication strategy (exact, shallow, fuzzy, multi)
            keep_older: Keep older duplicates or newer ones

        Returns:
            {
                'unique_findings': [...],
                'duplicate_groups': {hash: [finding1, finding2, ...]},
                'dedup_ratio': float (0-1),
                'dedup_summary': {...}
            }
        """
        unique_findings = []
        duplicate_groups = {}
        duplicates_by_hash = {}

        for finding in findings:
            normalized = self.normalize_finding(finding)
            primary_hash = self.compute_finding_hash(normalized, "primary")

            is_dup, matched_finding, confidence = self.is_duplicate(
                finding, unique_findings, strategy
            )

            if is_dup and matched_finding:
                matched_hash = self.compute_finding_hash(
                    self.normalize_finding(matched_finding), "primary"
                )
                if matched_hash not in duplicate_groups:
                    duplicate_groups[matched_hash] = [matched_finding]
                duplicate_groups[matched_hash].append(finding)
                duplicates_by_hash[primary_hash] = matched_hash
            else:
                unique_findings.append(finding)

        # Compute deduplication ratio
        total_input = len(findings)
        removed = total_input - len(unique_findings)
        dedup_ratio = removed / total_input if total_input > 0 else 0

        return {
            "unique_findings": unique_findings,
            "duplicate_groups": duplicate_groups,
            "duplicate_count": removed,
            "dedup_ratio": dedup_ratio,
            "strategy_used": strategy,
            "unique_count": len(unique_findings),
            "total_input": total_input,
            "dedup_summary": {
                "received": total_input,
                "unique": len(unique_findings),
                "removed": removed,
                "efficiency": f"{dedup_ratio*100:.1f}%",
            },
        }

    def merge_findings(
        self,
        duplicate_group: List[Dict[str, Any]],
        strategy: str = "latest",
    ) -> Dict[str, Any]:
        """
        Merge duplicate findings into single enhanced finding.

        Strategies:
        - latest: Keep latest finding, append metadata
        - earliest: Keep earliest, aggregate later findings
        - highest_severity: Keep highest severity
        - most_detailed: Keep most detailed description
        """
        if not duplicate_group:
            return {}

        if strategy == "latest":
            merged = duplicate_group[-1].copy()
            merged["source_count"] = len(duplicate_group)
            merged["duplicate_sources"] = [
                {
                    "timestamp": f.get("found_at", "unknown"),
                    "source": f.get("source", "unknown"),
                }
                for f in duplicate_group[:-1]
            ]

        elif strategy == "earliest":
            merged = duplicate_group[0].copy()
            merged["source_count"] = len(duplicate_group)
            merged["duplicate_sources"] = [
                {
                    "timestamp": f.get("found_at", "unknown"),
                    "source": f.get("source", "unknown"),
                }
                for f in duplicate_group[1:]
            ]

        elif strategy == "highest_severity":
            severity_order = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
            merged = max(
                duplicate_group,
                key=lambda x: severity_order.get(x.get("severity", "low"), 0),
            ).copy()
            merged["source_count"] = len(duplicate_group)

        elif strategy == "most_detailed":
            merged = max(
                duplicate_group,
                key=lambda x: len(x.get("description", "")),
            ).copy()
            merged["source_count"] = len(duplicate_group)

        else:
            merged = duplicate_group[0].copy()

        merged["deduplicated_at"] = datetime.now(timezone.utc).isoformat()
        merged["dedup_strategy"] = strategy
        return merged

    def _compute_similarity(
        self, finding1: Dict[str, Any], finding2: Dict[str, Any]
    ) -> float:
        """
        Compute similarity score between two findings (0-1).

        Considers:
        - URL similarity
        - Vulnerability type match
        - Description similarity
        """
        url_sim = self._string_similarity(
            finding1.get("url", ""), finding2.get("url", "")
        )
        type_match = 1.0 if finding1.get("vulnerability_type") == finding2.get("vulnerability_type") else 0.0
        desc_sim = self._string_similarity(
            finding1.get("description", "")[:200],
            finding2.get("description", "")[:200],
        )

        # Weighted average
        similarity = (url_sim * 0.5) + (type_match * 0.3) + (desc_sim * 0.2)
        return similarity

    @staticmethod
    def _string_similarity(s1: str, s2: str) -> float:
        """Compute string similarity using SequenceMatcher."""
        return SequenceMatcher(None, s1, s2).ratio()

    def get_dedup_stats(self) -> Dict[str, Any]:
        """Get deduplication statistics."""
        return {
            "total_hashes": len(self.finding_hashes),
            "total_normalized": len(self.normalized_findings),
            "hash_types": ["primary", "shallow", "deep"],
            "similarity_threshold": self.SIMILARITY_THRESHOLD,
        }
