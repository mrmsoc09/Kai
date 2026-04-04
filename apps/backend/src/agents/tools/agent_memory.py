from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class ScanRecord:
    scan_id: str
    target: str
    timestamp: str
    command: list[str]
    result_count: int
    signal_count: int
    noise_count: int
    findings: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FindingCorrelation:
    finding_id: str
    tool: str
    target: str
    value: str
    first_seen: str
    last_seen: str
    seen_count: int
    confirmed: bool = False
    tags: list[str] = field(default_factory=list)


class AgentMemory:
    """Persistent JSONL-based memory for a tool agent."""

    def __init__(self, memory_dir: str | Path) -> None:
        self.memory_dir = Path(memory_dir)
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self._scan_history_path = self.memory_dir / "scan_history.jsonl"
        self._findings_path = self.memory_dir / "findings_correlation.jsonl"

    # ------------------------------------------------------------------
    # Scan history
    # ------------------------------------------------------------------

    def record_scan(self, record: ScanRecord) -> None:
        with self._scan_history_path.open("a") as fh:
            fh.write(json.dumps(record.__dict__) + "\n")

    def load_scan_history(self) -> list[ScanRecord]:
        if not self._scan_history_path.exists():
            return []
        records: list[ScanRecord] = []
        with self._scan_history_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    records.append(ScanRecord(**data))
        return records

    def get_prior_findings_for_target(self, target: str) -> list[ScanRecord]:
        return [r for r in self.load_scan_history() if r.target == target]

    # ------------------------------------------------------------------
    # Finding correlation
    # ------------------------------------------------------------------

    def record_finding(self, correlation: FindingCorrelation) -> None:
        with self._findings_path.open("a") as fh:
            fh.write(json.dumps(correlation.__dict__) + "\n")

    def load_findings(self) -> list[FindingCorrelation]:
        if not self._findings_path.exists():
            return []
        findings: list[FindingCorrelation] = []
        with self._findings_path.open() as fh:
            for line in fh:
                line = line.strip()
                if line:
                    data = json.loads(line)
                    findings.append(FindingCorrelation(**data))
        return findings

    def has_seen_value(self, value: str, target: str) -> bool:
        return any(
            f.value == value and f.target == target
            for f in self.load_findings()
        )

    def record_confirmed_finding(self, finding: dict[str, Any]) -> None:
        """Called by VisionValidationService when a finding is confirmed (confidence >= 0.85).

        Appends to findings_correlation.jsonl with confirmed=True so the agent
        accumulates a history of what actually produces valid findings over time.
        """
        record = {
            "confirmed": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "finding_type": finding.get("finding_type"),
            "value": str(finding.get("value", ""))[:500],
            "target": finding.get("target"),
            "confidence": finding.get("confidence"),
            "raw_evidence": finding.get("raw_evidence", ""),
            "target_type": finding.get("target_type", "unknown"),
        }
        with self._findings_path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")

    def summary(self) -> dict[str, Any]:
        scans = self.load_scan_history()
        findings = self.load_findings()
        return {
            "total_scans": len(scans),
            "total_findings": len(findings),
            "confirmed_findings": sum(1 for f in findings if f.confirmed),
            "targets_scanned": list({s.target for s in scans}),
        }
