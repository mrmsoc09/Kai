"""Evidence integrity tracking with immutability guarantees."""

import hashlib
import json
from typing import Dict, Any, List, Optional
from datetime import datetime


class EvidenceTracker:
    """Track evidence with cryptographic integrity guarantees."""

    def __init__(self):
        """Initialize evidence tracker."""
        self.evidence_chain: List[Dict[str, Any]] = []
        self.merkle_tree_hashes: Dict[str, str] = {}

    def record_evidence(
        self,
        evidence_type: str,
        content: Dict[str, Any],
        source: str,
        finding_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Record evidence with cryptographic hash.

        Evidence types:
        - scan_output: Raw scan output
        - screenshot: Visual evidence
        - metadata: Metadata about finding
        - analysis: LLM or analyst analysis
        - validation: Human validation
        """
        evidence_record = {
            "id": self._generate_evidence_id(),
            "type": evidence_type,
            "source": source,
            "finding_id": finding_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "content_hash": self._compute_content_hash(content),
            "chain_index": len(self.evidence_chain),
        }

        # Compute hash linking to previous evidence (blockchain-style)
        if self.evidence_chain:
            previous_hash = self.evidence_chain[-1].get("chain_hash")
            evidence_record["previous_hash"] = previous_hash
            evidence_record["chain_hash"] = self._compute_chain_hash(
                evidence_record, previous_hash
            )
        else:
            evidence_record["chain_hash"] = self._compute_content_hash(evidence_record)
            evidence_record["previous_hash"] = None

        self.evidence_chain.append(evidence_record)
        return evidence_record

    def verify_evidence_integrity(
        self, evidence_id: str
    ) -> Dict[str, Any]:
        """
        Verify evidence hasn't been tampered with.

        Checks:
        - Content hash unchanged
        - Chain integrity from root to this evidence
        """
        # Find evidence
        evidence = next((e for e in self.evidence_chain if e.get("id") == evidence_id), None)
        if not evidence:
            return {"valid": False, "reason": "evidence_not_found"}

        # Verify content hash
        current_content_hash = self._compute_content_hash(evidence.get("content"))
        stored_content_hash = evidence.get("content_hash")

        if current_content_hash != stored_content_hash:
            return {"valid": False, "reason": "content_tampered"}

        # Verify chain integrity
        if not self._verify_chain_integrity(evidence):
            return {"valid": False, "reason": "chain_integrity_violation"}

        return {
            "valid": True,
            "evidence_id": evidence_id,
            "verified_at": datetime.utcnow().isoformat(),
            "chain_index": evidence.get("chain_index"),
        }

    def get_evidence_trail(
        self, finding_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get evidence trail for a finding or all evidence."""
        if finding_id:
            trail = [e for e in self.evidence_chain if e.get("finding_id") == finding_id]
        else:
            trail = self.evidence_chain

        return [
            {
                "id": e.get("id"),
                "type": e.get("type"),
                "source": e.get("source"),
                "timestamp": e.get("timestamp"),
                "chain_index": e.get("chain_index"),
                "valid": self.verify_evidence_integrity(e.get("id")).get("valid"),
            }
            for e in trail
        ]

    def create_evidence_report(
        self, finding_id: str
    ) -> Dict[str, Any]:
        """
        Create integrity report for a finding's evidence.

        Reports:
        - All evidence collected
        - Integrity verification
        - Timeline
        - Chain validity
        """
        trail = self.get_evidence_trail(finding_id)
        all_valid = all(e.get("valid") for e in trail)

        chain_hashes = [
            self.evidence_chain[i].get("chain_hash")
            for i in range(len(self.evidence_chain))
            if self.evidence_chain[i].get("finding_id") == finding_id
        ]

        return {
            "finding_id": finding_id,
            "evidence_count": len(trail),
            "chain_valid": all_valid,
            "evidence_trail": trail,
            "chain_hashes": chain_hashes,
            "merkle_root": self._compute_merkle_root(chain_hashes) if chain_hashes else None,
            "report_generated_at": datetime.utcnow().isoformat(),
        }

    def compute_finding_fingerprint(
        self, finding: Dict[str, Any]
    ) -> str:
        """
        Compute unique fingerprint of a finding.

        Fingerprint is immutable commitment to finding at point in time.
        """
        # Use consistent key ordering
        finding_json = json.dumps(finding, sort_keys=True, ensure_ascii=False)
        fingerprint = hashlib.sha256(finding_json.encode()).hexdigest()
        return fingerprint

    def validate_finding_unchanged(
        self, finding: Dict[str, Any], original_fingerprint: str
    ) -> bool:
        """Verify finding hasn't been modified since original fingerprint."""
        current_fingerprint = self.compute_finding_fingerprint(finding)
        return current_fingerprint == original_fingerprint

    def _compute_content_hash(self, content: Dict[str, Any]) -> str:
        """Compute SHA256 hash of content."""
        content_json = json.dumps(content, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_json.encode()).hexdigest()

    def _compute_chain_hash(
        self, evidence: Dict[str, Any], previous_hash: Optional[str]
    ) -> str:
        """Compute blockchain-style hash linking to previous evidence."""
        chain_input = f"{previous_hash or ''}|{evidence.get('content_hash')}|{evidence.get('timestamp')}"
        return hashlib.sha256(chain_input.encode()).hexdigest()

    def _verify_chain_integrity(self, evidence: Dict[str, Any]) -> bool:
        """Verify evidence is correctly linked in chain."""
        chain_index = evidence.get("chain_index", -1)

        if chain_index == 0:
            # First element, no previous hash to check
            return True

        if chain_index <= 0 or chain_index >= len(self.evidence_chain):
            return False

        previous_evidence = self.evidence_chain[chain_index - 1]
        expected_previous_hash = previous_evidence.get("chain_hash")
        actual_previous_hash = evidence.get("previous_hash")

        return expected_previous_hash == actual_previous_hash

    def _generate_evidence_id(self) -> str:
        """Generate unique evidence ID."""
        timestamp = datetime.utcnow().isoformat()
        counter = len(self.evidence_chain)
        evidence_id = f"ev_{counter}_{hashlib.sha256(timestamp.encode()).hexdigest()[:12]}"
        return evidence_id

    def _compute_merkle_root(self, hashes: List[str]) -> str:
        """Compute Merkle tree root from list of hashes."""
        if not hashes:
            return ""
        if len(hashes) == 1:
            return hashes[0]

        # Build Merkle tree
        tree = hashes.copy()
        while len(tree) > 1:
            new_level = []
            for i in range(0, len(tree), 2):
                left = tree[i]
                right = tree[i + 1] if i + 1 < len(tree) else left
                parent = hashlib.sha256(f"{left}{right}".encode()).hexdigest()
                new_level.append(parent)
            tree = new_level

        return tree[0]

    def get_chain_stats(self) -> Dict[str, Any]:
        """Get statistics about evidence chain."""
        chain_length = len(self.evidence_chain)

        evidence_by_type = {}
        for evidence in self.evidence_chain:
            ev_type = evidence.get("type", "unknown")
            evidence_by_type[ev_type] = evidence_by_type.get(ev_type, 0) + 1

        evidence_by_source = {}
        for evidence in self.evidence_chain:
            source = evidence.get("source", "unknown")
            evidence_by_source[source] = evidence_by_source.get(source, 0) + 1

        return {
            "chain_length": chain_length,
            "evidence_by_type": evidence_by_type,
            "evidence_by_source": evidence_by_source,
            "chain_valid": self._verify_full_chain_integrity(),
        }

    def _verify_full_chain_integrity(self) -> bool:
        """Verify entire evidence chain is valid."""
        for i, evidence in enumerate(self.evidence_chain):
            if not self.verify_evidence_integrity(evidence.get("id")).get("valid"):
                return False
        return True
