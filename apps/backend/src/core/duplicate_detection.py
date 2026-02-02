"""
K1 Duplicate Finding Detection System
Prevents resubmitting previously reported vulnerabilities
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import json
import hashlib
from difflib import SequenceMatcher


class VulnerabilityType(str, Enum):
    """Types of vulnerabilities"""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    CSRF = "csrf"
    BROKEN_AUTH = "broken_auth"
    INSECURE_DESERIALIZATION = "insecure_deserialization"
    XXE = "xxe"
    BROKEN_ACCESS_CONTROL = "broken_access_control"
    SSRF = "ssrf"
    RACE_CONDITION = "race_condition"
    WEAK_CRYPTO = "weak_crypto"
    BUSINESS_LOGIC = "business_logic"
    RATE_LIMITING = "rate_limiting"
    API_ENUMERATION = "api_enumeration"
    INFORMATION_DISCLOSURE = "information_disclosure"
    ARBITRARY_FILE_UPLOAD = "arbitrary_file_upload"
    RCE = "rce"
    OTHER = "other"


@dataclass
class PreviouslyReportedFinding:
    """Record of a previously reported finding"""
    finding_id: str
    program_name: str
    target_domain: str
    vulnerability_type: VulnerabilityType
    endpoint: str
    description: str
    cvss_score: float
    reported_date: datetime
    platform: str  # HackerOne, Bugcrowd, Intigriti, etc.
    status: str  # "disclosed", "fixed", "pending", "rejected", "paid"
    bounty_paid: Optional[float] = None
    report_url: Optional[str] = None
    techniques: List[str] = field(default_factory=list)  # Techniques used
    affected_parameters: List[str] = field(default_factory=list)
    payload_signature: Optional[str] = None  # Hash of payload for similarity


@dataclass
class DuplicateDetectionResult:
    """Result of duplicate detection check"""
    is_duplicate: bool
    similarity_score: float  # 0-1, how similar to existing finding
    matched_finding: Optional[PreviouslyReportedFinding] = None
    confidence: float = 0.0  # How confident in the duplicate match
    chainable_with: List[PreviouslyReportedFinding] = field(default_factory=list)  # Other findings this could chain with
    reason: Optional[str] = None


class DuplicateDetectionSystem:
    """Detects and prevents submission of duplicate findings"""

    def __init__(self):
        self.finding_database: Dict[str, PreviouslyReportedFinding] = {}
        self.domain_findings: Dict[str, List[str]] = {}  # domain -> finding_ids
        self.type_findings: Dict[VulnerabilityType, List[str]] = {}  # vuln_type -> finding_ids
        self.endpoint_signatures: Dict[str, List[str]] = {}  # endpoint_hash -> finding_ids
        self.payload_signatures: Dict[str, List[str]] = {}  # payload_hash -> finding_ids

    def register_finding(self, finding: PreviouslyReportedFinding):
        """Register a previously reported finding"""
        self.finding_database[finding.finding_id] = finding

        # Index by domain
        if finding.target_domain not in self.domain_findings:
            self.domain_findings[finding.target_domain] = []
        self.domain_findings[finding.target_domain].append(finding.finding_id)

        # Index by type
        if finding.vulnerability_type not in self.type_findings:
            self.type_findings[finding.vulnerability_type] = []
        self.type_findings[finding.vulnerability_type].append(finding.finding_id)

        # Index by endpoint
        endpoint_sig = self._hash_endpoint(finding.endpoint)
        if endpoint_sig not in self.endpoint_signatures:
            self.endpoint_signatures[endpoint_sig] = []
        self.endpoint_signatures[endpoint_sig].append(finding.finding_id)

        # Index by payload
        if finding.payload_signature:
            if finding.payload_signature not in self.payload_signatures:
                self.payload_signatures[finding.payload_signature] = []
            self.payload_signatures[finding.payload_signature].append(finding.finding_id)

    def _hash_endpoint(self, endpoint: str) -> str:
        """Create hash of endpoint for quick comparison"""
        return hashlib.sha256(endpoint.lower().encode()).hexdigest()[:16]

    def _calculate_similarity(
        self,
        endpoint1: str,
        endpoint2: str,
        tech1: List[str],
        tech2: List[str],
        param1: List[str],
        param2: List[str]
    ) -> float:
        """Calculate similarity between findings (0-1)"""
        # Endpoint similarity (40% weight)
        endpoint_sim = SequenceMatcher(None, endpoint1.lower(), endpoint2.lower()).ratio()

        # Technique similarity (30% weight)
        if tech1 and tech2:
            common_tech = len(set(tech1) & set(tech2))
            total_tech = len(set(tech1) | set(tech2))
            tech_sim = common_tech / total_tech if total_tech > 0 else 0.0
        else:
            tech_sim = 0.0

        # Parameter similarity (30% weight)
        if param1 and param2:
            common_params = len(set(param1) & set(param2))
            total_params = len(set(param1) | set(param2))
            param_sim = common_params / total_params if total_params > 0 else 0.0
        else:
            param_sim = 0.0

        # Weighted average
        return (endpoint_sim * 0.4) + (tech_sim * 0.3) + (param_sim * 0.3)

    async def check_duplicate(
        self,
        target_domain: str,
        vulnerability_type: VulnerabilityType,
        endpoint: str,
        techniques: List[str],
        affected_parameters: List[str],
        description: str,
        payload_hash: Optional[str] = None
    ) -> DuplicateDetectionResult:
        """Check if finding is duplicate of previously reported"""

        candidates = []

        # Strategy 1: Exact payload match (fastest)
        if payload_hash and payload_hash in self.payload_signatures:
            for finding_id in self.payload_signatures[payload_hash]:
                finding = self.finding_database[finding_id]
                if finding.target_domain == target_domain:
                    candidates.append((finding, 1.0))  # 100% match

        # Strategy 2: Same domain + same type + similar endpoint (fast)
        if target_domain in self.domain_findings:
            for finding_id in self.domain_findings[target_domain]:
                finding = self.finding_database[finding_id]
                if finding.vulnerability_type == vulnerability_type:
                    similarity = self._calculate_similarity(
                        endpoint, finding.endpoint,
                        techniques, finding.techniques,
                        affected_parameters, finding.affected_parameters
                    )
                    if similarity > 0.7:  # Significant similarity
                        candidates.append((finding, similarity))

        # Strategy 3: Same vulnerability type globally (slower, broader search)
        if vulnerability_type in self.type_findings:
            for finding_id in self.type_findings[vulnerability_type]:
                finding = self.finding_database[finding_id]
                if finding.target_domain != target_domain:
                    # Different domain but same type - might be similar pattern
                    similarity = self._calculate_similarity(
                        endpoint, finding.endpoint,
                        techniques, finding.techniques,
                        affected_parameters, finding.affected_parameters
                    )
                    if similarity > 0.85:  # Very high similarity needed
                        candidates.append((finding, similarity))

        if not candidates:
            return DuplicateDetectionResult(
                is_duplicate=False,
                similarity_score=0.0,
                confidence=0.95
            )

        # Sort by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_match, best_similarity = candidates[0]

        # Determine if truly duplicate based on similarity and status
        is_duplicate = False
        confidence = best_similarity

        if best_similarity > 0.9:
            # Very high similarity
            is_duplicate = True
        elif best_similarity > 0.75 and best_match.status in ["paid", "disclosed", "fixed"]:
            # High similarity and already accepted/paid
            is_duplicate = True
        elif best_similarity > 0.8:
            # Good similarity
            is_duplicate = True

        # Find chainable findings (other findings on same domain)
        chainable = []
        if target_domain in self.domain_findings:
            for finding_id in self.domain_findings[target_domain]:
                finding = self.finding_database[finding_id]
                if finding.finding_id != best_match.finding_id:
                    chainable.append(finding)

        return DuplicateDetectionResult(
            is_duplicate=is_duplicate,
            similarity_score=best_similarity,
            matched_finding=best_match,
            confidence=confidence,
            chainable_with=chainable,
            reason=f"Matched to {best_match.vulnerability_type.value} on {best_match.target_domain}" if is_duplicate else None
        )

    def get_findings_by_domain(self, domain: str) -> List[PreviouslyReportedFinding]:
        """Get all findings for a domain"""
        finding_ids = self.domain_findings.get(domain, [])
        return [self.finding_database[fid] for fid in finding_ids if fid in self.finding_database]

    def get_findings_by_type(self, vuln_type: VulnerabilityType) -> List[PreviouslyReportedFinding]:
        """Get all findings of a type"""
        finding_ids = self.type_findings.get(vuln_type, [])
        return [self.finding_database[fid] for fid in finding_ids if fid in self.finding_database]

    def import_from_hackerone(self, reports: List[Dict[str, Any]]):
        """Import findings from HackerOne API"""
        for report in reports:
            finding = PreviouslyReportedFinding(
                finding_id=f"h1_{report.get('id')}",
                program_name=report.get('program', {}).get('name', 'unknown'),
                target_domain=self._extract_domain(report.get('target', {}).get('name', '')),
                vulnerability_type=self._parse_vulnerability_type(report.get('vulnerability_type', '')),
                endpoint=report.get('vulnerability_endpoint', ''),
                description=report.get('vulnerability_description', ''),
                cvss_score=float(report.get('cvss_score', 0.0)) if report.get('cvss_score') else 0.0,
                reported_date=datetime.fromisoformat(report.get('submitted_at', '')),
                platform='hackerone',
                status=report.get('state', ''),
                bounty_paid=float(report.get('bounty_amount', 0)) if report.get('bounty_amount') else None,
                report_url=report.get('url', ''),
                techniques=report.get('techniques', []),
                affected_parameters=report.get('affected_parameters', [])
            )
            self.register_finding(finding)

    def _extract_domain(self, target_name: str) -> str:
        """Extract domain from target name"""
        if '://' in target_name:
            target_name = target_name.split('://')[1]
        return target_name.split('/')[0].lower()

    def _parse_vulnerability_type(self, type_string: str) -> VulnerabilityType:
        """Parse vulnerability type string"""
        type_string = type_string.lower().replace(' ', '_')
        try:
            return VulnerabilityType[type_string.upper()]
        except KeyError:
            return VulnerabilityType.OTHER

    def to_dict(self) -> Dict[str, Any]:
        """Get system statistics"""
        return {
            "total_findings": len(self.finding_database),
            "domains_tracked": len(self.domain_findings),
            "vulnerability_types": len(self.type_findings),
            "endpoint_signatures": len(self.endpoint_signatures),
            "payload_signatures": len(self.payload_signatures)
        }


# Global instance
duplicate_detection_system = None


def initialize_duplicate_detection() -> DuplicateDetectionSystem:
    """Initialize duplicate detection system"""
    global duplicate_detection_system

    duplicate_detection_system = DuplicateDetectionSystem()
    print("✓ Duplicate detection system initialized")

    return duplicate_detection_system
