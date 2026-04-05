from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class AuditEntry:
    """A single leaf node in the Intention Merkle Tree."""
    mission_id: str
    stage: str
    consensus_id: str  # References the 3-Vote Consensus event
    action_taken: str
    result_hash: str
    timestamp: float = field(default_factory=time.time)
    previous_hash: str = ""
    entry_hash: str = ""

    def compute_hash(self) -> str:
        """Computes the SHA-256 hash of this entry combined with the previous entry."""
        data = f"{self.mission_id}{self.stage}{self.consensus_id}{self.action_taken}{self.result_hash}{self.timestamp}{self.previous_hash}"
        return hashlib.sha256(data.encode()).hexdigest()

class MerkleIntentionLedger:
    """
    Maintains a cryptographically linked chain of mission intentions and outcomes.
    Ensures 'Intentional Fidelity' across autonomous operations.
    """

    def __init__(self):
        self.chain: List[AuditEntry] = []
        self.root_hash: str = ""

    def commit_action(
        self, 
        mission_id: str, 
        stage: str, 
        consensus_id: str, 
        action: str, 
        result_data: Any
    ) -> str:
        """
        Commits a new action to the ledger and updates the chain hash.
        """
        # 1. Serialize result for hashing
        result_str = json.dumps(result_data, sort_keys=True)
        result_hash = hashlib.sha256(result_str.encode()).hexdigest()

        # 2. Get previous hash
        prev_hash = self.chain[-1].entry_hash if self.chain else "PRIMORDIAL_GENESIS"

        # 3. Create entry
        entry = AuditEntry(
            mission_id=mission_id,
            stage=stage,
            consensus_id=consensus_id,
            action_taken=action,
            result_hash=result_hash,
            previous_hash=prev_hash
        )
        
        # 4. Finalize entry hash
        entry.entry_hash = entry.compute_hash()
        
        # 5. Commit to chain
        self.chain.append(entry)
        self.root_hash = entry.entry_hash
        
        logger.info(f"Audit: Committed Stage '{stage}' to Merkle Ledger. Root: {self.root_hash[:16]}...")
        return self.root_hash

    def verify_integrity(self) -> bool:
        """
        Validates the entire chain by re-computing hashes from the genesis block.
        """
        if not self.chain:
            return True
        
        expected_prev = "PRIMORDIAL_GENESIS"
        for entry in self.chain:
            if entry.previous_hash != expected_prev:
                logger.error(f"Audit integrity breach: Previous hash mismatch in mission {entry.mission_id}")
                return False
            
            if entry.entry_hash != entry.compute_hash():
                logger.error(f"Audit integrity breach: Entry hash corrupted in mission {entry.mission_id}")
                return False
            
            expected_prev = entry.entry_hash
            
        return True

    def get_audit_log_html(self) -> str:
        """Generates a Trilium-compatible HTML report of the audit trail."""
        html = "<h1>K1 Intention Audit Trail</h1><table border='1'><tr><th>Stage</th><th>Consensus</th><th>Hash</th></tr>"
        for entry in self.chain:
            html += f"<tr><td>{entry.stage}</td><td>{entry.consensus_id}</td><td><code>{entry.entry_hash[:12]}...</code></td></tr>"
        html += "</table>"
        return html
