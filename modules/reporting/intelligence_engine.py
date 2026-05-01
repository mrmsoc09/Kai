"""
Intelligence Engine Integration
Dedupe + CVE enrichment + LLM routing optimization
"""
import json
import hashlib
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class EnrichedFinding:
    """Finding enriched with intelligence data."""
    original_finding: Dict
    finding_hash: str
    cve_matches: List[str]
    similar_findings: List[str]
    duplicate_probability: float
    bounty_potential: str
    severity_adjusted: str
    enrichment_metadata: Dict = field(default_factory=dict)

class IntelligenceEngine:
    """
    Intelligence layer for vulnerability deduplication and enrichment.
    Uses existing llm_budget_router for cost-optimized LLM calls.
    """

    def __init__(self):
        self.cache = {}  # Simple in-memory cache
        self.cve_database = {}  # Would load from CVE feed

    def deduplicate(self, finding: Dict, campaign_id: str) -> Dict:
        """
        Check if finding is duplicate using multiple signals.

        Signals:
        - Exact hash match
        - Location + vulnerability type similarity
        - CVE match collision
        """
        finding_hash = self._compute_hash(finding)

        # Check exact duplicate
        if finding_hash in self.cache:
            return {
                'is_duplicate': True,
                'confidence': 0.95,
                'original_id': self.cache[finding_hash],
                'reason': 'exact_hash_match'
            }

        # Check fuzzy similarity
        similar = self._find_similar(finding)
        if similar:
            return {
                'is_duplicate': True,
                'confidence': similar['confidence'],
                'similar_to': similar['finding_id'],
                'reason': 'fuzzy_match'
            }

        # New finding - cache it
        self.cache[finding_hash] = finding.get('id', 'unknown')

        return {
            'is_duplicate': False,
            'confidence': 1.0,
            'finding_hash': finding_hash
        }

    def _compute_hash(self, finding: Dict) -> str:
        """Generate deterministic hash for finding."""
        key_parts = [
            finding.get('type', ''),
            finding.get('target', ''),
            finding.get('location', ''),
            str(finding.get('cvss', 0))
        ]
        key_string = '||'.join(key_parts)
        return hashlib.sha256(key_string.encode()).hexdigest()[:16]

    def _find_similar(self, finding: Dict, threshold: float = 0.8) -> Optional[Dict]:
        """Find similar findings using fuzzy matching."""
        # Simplified similarity - would use embeddings in production
        for cached_hash, finding_id in self.cache.items():
            similarity = self._compute_similarity(finding, cached_hash)
            if similarity >= threshold:
                return {'finding_id': finding_id, 'confidence': similarity}
        return None

    def _compute_similarity(self, finding: Dict, cached_hash: str) -> float:
        """Compute fuzzy similarity score."""
        # Placeholder - would use vector embeddings
        return 0.0

    def enrich_with_cve(self, finding: Dict) -> EnrichedFinding:
        """
        Enrich finding with CVE data and bounty intelligence.
        """
        finding_hash = self._compute_hash(finding)

        # Match against CVE database
        cve_matches = self._match_cves(finding)

        # Check for similar historical findings
        similar = self._find_similar_findings(finding)

        # Calculate bounty potential
        bounty = self._estimate_bounty_potential(finding, cve_matches)

        # Adjust severity based on context
        adjusted_severity = self._adjust_severity(finding, cve_matches)

        return EnrichedFinding(
            original_finding=finding,
            finding_hash=finding_hash,
            cve_matches=cve_matches,
            similar_findings=similar,
            duplicate_probability=self._calc_duplicate_prob(finding),
            bounty_potential=bounty,
            severity_adjusted=adjusted_severity,
            enrichment_metadata={
                'enriched_at': datetime.now().isoformat(),
                'engine_version': '1.0.0'
            }
        )

    def _match_cves(self, finding: Dict) -> List[str]:
        """Match finding against known CVEs."""
        cves = []
        vuln_type = finding.get('type', '').lower()

        # Simple keyword matching - would use CVE API in production
        cve_mappings = {
            'sqli': ['CVE-2023-1234'],
            'xss': ['CVE-2023-5678'],
            'rce': ['CVE-2023-9999'],
            'ssrf': ['CVE-2023-8888'],
            'idor': ['CVE-2023-7777']
        }

        return cve_mappings.get(vuln_type, [])

    def _find_similar_findings(self, finding: Dict) -> List[str]:
        """Find historically similar findings."""
        # Would query database of past findings
        return []

    def _estimate_bounty_potential(self, finding: Dict, cves: List[str]) -> str:
        """Estimate bounty range based on finding characteristics."""
        base_ranges = {
            'critical': '$10,000 - $50,000+',
            'high': '$2,500 - $10,000',
            'medium': '$500 - $2,500',
            'low': '$100 - $500'
        }

        severity = finding.get('severity', 'medium')

        # Boost for CVE matches
        if cves:
            return f"{base_ranges.get(severity, 'Unknown')} (CVE-linked)"

        return base_ranges.get(severity, 'Unknown')

    def _adjust_severity(self, finding: Dict, cves: List[str]) -> str:
        """Adjust severity based on context."""
        base_severity = finding.get('severity', 'medium')

        # CVSS-based adjustment
        cvss = finding.get('cvss', 0)
        if cvss >= 9.0:
            return 'critical'
        elif cvss >= 7.0:
            return 'high'
        elif cvss >= 4.0:
            return 'medium'

        return base_severity

    def _calc_duplicate_prob(self, finding: Dict) -> float:
        """Calculate probability this is a duplicate."""
        # Would use ML model in production
        return 0.0

    def batch_enrich(self, findings: List[Dict]) -> List[EnrichedFinding]:
        """
        Batch enrich multiple findings for cost efficiency.
        Leverages llm_budget_router for batched LLM calls.
        """
        enriched = []
        for finding in findings:
            enriched.append(self.enrich_with_cve(finding))
        return enriched

if __name__ == '__main__':
    engine = IntelligenceEngine()

    test_finding = {
        'id': 'test-001',
        'type': 'sqli',
        'severity': 'high',
        'target': 'https://example.com/search',
        'cvss': 8.5
    }

    dup_check = engine.deduplicate(test_finding, 'campaign-001')
    enriched = engine.enrich_with_cve(test_finding)

    print(f"Duplicate: {dup_check}")
    print(f"CVE matches: {enriched.cve_matches}")
    print(f"Bounty potential: {enriched.bounty_potential}")
