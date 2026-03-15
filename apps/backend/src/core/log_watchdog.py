"""
Project Kai Log Watchdog
Monitors hunt logs and alerts if entries lack valid PGP signatures
"""

import os
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib


class AlertSeverity(str, Enum):
    """Alert severity levels"""
    CRITICAL = "critical"  # Unsigned log in critical operation
    HIGH = "high"  # Unsigned log in important operation
    MEDIUM = "medium"  # Unsigned log in standard operation
    INFO = "info"  # Informational alert


@dataclass
class LogEntry:
    """A hunting log entry"""
    timestamp: str
    log_id: str
    log_file: str
    operation: str  # reconnaissance, exploitation, reporting, etc.
    target: str
    status: str  # success, failure, partial
    content_hash: str


@dataclass
class SignatureRecord:
    """PGP signature for a log entry"""
    log_id: str
    signature_file: str
    signer: str  # identity that signed
    signature_valid: bool
    verified_at: str


@dataclass
class UnsignedAlert:
    """Alert for unsigned or invalid log entry"""
    alert_id: str
    log_id: str
    operation: str
    severity: AlertSeverity
    message: str
    detected_at: str
    action_required: str


class LogWatchdog:
    """
    Monitor hunting logs for missing or invalid signatures
    Ensures cryptographic chain of custody for all operations
    """

    def __init__(
        self,
        log_directory: str = "/var/lib/kai/logs",
        crypto_system=None,
        alert_webhook: Optional[str] = None
    ):
        self.log_dir = Path(log_directory)
        self.crypto_system = crypto_system
        self.alert_webhook = alert_webhook

        # Tracking
        self.monitored_logs: Dict[str, LogEntry] = {}
        self.signature_records: Dict[str, SignatureRecord] = {}
        self.alerts: List[UnsignedAlert] = []
        self.last_scan: Optional[datetime] = None

        # Configuration
        self.critical_operations = [
            "exploitation",
            "payload_execution",
            "remote_code_execution",
            "privilege_escalation"
        ]

        self.log_dir.mkdir(parents=True, exist_ok=True)

    async def scan_logs(self) -> Tuple[int, int, List[UnsignedAlert]]:
        """
        Scan log directory for unsigned entries
        Returns: (total_logs, signed_logs, new_alerts)
        """
        print(f"\n[*] Scanning logs in {self.log_dir}")

        new_alerts = []
        log_files = list(self.log_dir.glob("*.log"))
        signed_count = 0

        if not log_files:
            print(f"[!] No log files found in {self.log_dir}")
            return (0, 0, [])

        print(f"[•] Found {len(log_files)} log file(s)")

        for log_file in log_files:
            try:
                # Read log entry
                log_content = log_file.read_text()
                log_entry = self._parse_log(log_file, log_content)

                # Check for signature
                sig_file = Path(str(log_file) + ".sig")

                if sig_file.exists():
                    # Verify signature
                    is_valid = await self._verify_signature(log_file, sig_file)

                    if is_valid:
                        print(f"[✓] {log_file.name}: Signed and valid")
                        signed_count += 1
                        self.signature_records[log_entry.log_id] = SignatureRecord(
                            log_id=log_entry.log_id,
                            signature_file=str(sig_file),
                            signer="machine-kaisonai@pm.me",
                            signature_valid=True,
                            verified_at=datetime.now(timezone.utc).isoformat()
                        )
                    else:
                        # Invalid signature - CRITICAL
                        alert = UnsignedAlert(
                            alert_id=self._generate_alert_id(),
                            log_id=log_entry.log_id,
                            operation=log_entry.operation,
                            severity=AlertSeverity.CRITICAL,
                            message=f"SIGNATURE INVALID: {log_file.name}",
                            detected_at=datetime.now(timezone.utc).isoformat(),
                            action_required="IMMEDIATE INVESTIGATION REQUIRED"
                        )
                        new_alerts.append(alert)
                        print(f"[✗] {log_file.name}: SIGNATURE INVALID!")

                else:
                    # No signature - ALERT
                    severity = self._determine_severity(log_entry)
                    alert = UnsignedAlert(
                        alert_id=self._generate_alert_id(),
                        log_id=log_entry.log_id,
                        operation=log_entry.operation,
                        severity=severity,
                        message=f"UNSIGNED LOG: {log_file.name}",
                        detected_at=datetime.now(timezone.utc).isoformat(),
                        action_required=f"Generate signature for {log_file.name}"
                    )
                    new_alerts.append(alert)
                    print(f"[!] {log_file.name}: UNSIGNED - Severity: {severity.value}")

                self.monitored_logs[log_entry.log_id] = log_entry

            except Exception as e:
                print(f"[✗] Error processing {log_file.name}: {str(e)}")

        self.last_scan = datetime.now(timezone.utc)
        self.alerts.extend(new_alerts)

        return (len(log_files), signed_count, new_alerts)

    def _parse_log(self, log_file: Path, content: str) -> LogEntry:
        """Parse a log file into LogEntry"""
        try:
            log_data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback for non-JSON logs
            log_data = {"content": content}

        log_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        return LogEntry(
            timestamp=log_data.get("timestamp", datetime.now(timezone.utc).isoformat()),
            log_id=log_id,
            log_file=str(log_file),
            operation=log_data.get("operation", "unknown"),
            target=log_data.get("target", "unknown"),
            status=log_data.get("status", "unknown"),
            content_hash=content_hash
        )

    async def _verify_signature(self, log_file: Path, sig_file: Path) -> bool:
        """Verify signature for a log file"""
        if not self.crypto_system:
            return False

        try:
            success, msg, record = await self.crypto_system.verify_artifact(
                str(log_file),
                str(sig_file)
            )
            return success and not (record.tamper_detected if record else False)
        except Exception as e:
            print(f"[✗] Signature verification error: {str(e)}")
            return False

    def _determine_severity(self, log_entry: LogEntry) -> AlertSeverity:
        """Determine alert severity based on operation type"""
        if log_entry.operation in self.critical_operations:
            return AlertSeverity.CRITICAL
        elif log_entry.operation in ["analysis", "reporting"]:
            return AlertSeverity.HIGH
        elif log_entry.operation == "reconnaissance":
            return AlertSeverity.MEDIUM
        else:
            return AlertSeverity.INFO

    def _generate_alert_id(self) -> str:
        """Generate unique alert ID"""
        timestamp = datetime.now(timezone.utc).isoformat()
        data = f"{timestamp}{len(self.alerts)}".encode()
        return hashlib.sha256(data).hexdigest()[:12]

    async def remediate_unsigned_logs(self) -> Dict[str, int]:
        """
        Attempt to sign all unsigned logs
        Returns: {unsigned_logs, signed_successfully, signing_failed}
        """
        if not self.crypto_system:
            print("[✗] Crypto system not available for remediation")
            return {"unsigned": 0, "signed": 0, "failed": 0}

        print(f"\n[*] Attempting to sign unsigned logs...")

        results = {"unsigned": 0, "signed": 0, "failed": 0}

        for alert in self.alerts:
            if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
                log_entry = self.monitored_logs.get(alert.log_id)
                if log_entry:
                    try:
                        sig_path = Path(log_entry.log_file).with_suffix(".log.sig")

                        # Sign the log
                        success, msg, record = await self.crypto_system.sign_artifact(
                            log_entry.log_file,
                            passphrase=""
                        )

                        if success:
                            print(f"[✓] Signed: {Path(log_entry.log_file).name}")
                            results["signed"] += 1
                        else:
                            print(f"[✗] Failed to sign: {log_entry.log_file}")
                            results["failed"] += 1

                    except Exception as e:
                        print(f"[✗] Remediation error: {str(e)}")
                        results["failed"] += 1

        results["unsigned"] = len([a for a in self.alerts if not self.signature_records.get(a.log_id)])
        return results

    async def generate_report(self) -> Dict:
        """Generate comprehensive watchdog report"""
        total_logs = len(self.monitored_logs)
        signed_logs = len([e for e in self.monitored_logs.values() if e.log_id in self.signature_records])
        unsigned_logs = total_logs - signed_logs

        critical_alerts = len([a for a in self.alerts if a.severity == AlertSeverity.CRITICAL])
        high_alerts = len([a for a in self.alerts if a.severity == AlertSeverity.HIGH])
        medium_alerts = len([a for a in self.alerts if a.severity == AlertSeverity.MEDIUM])

        return {
            "scan_timestamp": self.last_scan.isoformat() if self.last_scan else None,
            "summary": {
                "total_logs": total_logs,
                "signed_logs": signed_logs,
                "unsigned_logs": unsigned_logs,
                "signature_coverage": (signed_logs / total_logs * 100) if total_logs > 0 else 0
            },
            "alerts": {
                "total": len(self.alerts),
                "critical": critical_alerts,
                "high": high_alerts,
                "medium": medium_alerts,
                "info": len([a for a in self.alerts if a.severity == AlertSeverity.INFO])
            },
            "alert_details": [
                {
                    "alert_id": a.alert_id,
                    "operation": a.operation,
                    "severity": a.severity.value,
                    "message": a.message,
                    "action": a.action_required
                }
                for a in self.alerts
            ],
            "status": "CRITICAL" if critical_alerts > 0 else "WARNING" if (high_alerts + critical_alerts) > 0 else "NORMAL"
        }

    def print_report(self):
        """Print formatted watchdog report"""
        report = asyncio.run(self.generate_report())

        print(f"\n{'='*70}")
        print("PROJECT KAI LOG WATCHDOG REPORT")
        print(f"{'='*70}")

        summary = report["summary"]
        print(f"\nLOG COVERAGE:")
        print(f"  Total logs: {summary['total_logs']}")
        print(f"  Signed logs: {summary['signed_logs']}")
        print(f"  Unsigned logs: {summary['unsigned_logs']}")
        print(f"  Coverage: {summary['signature_coverage']:.1f}%")

        alerts = report["alerts"]
        print(f"\nALERTS:")
        print(f"  Total: {alerts['total']}")
        print(f"  Critical: {alerts['critical']}")
        print(f"  High: {alerts['high']}")
        print(f"  Medium: {alerts['medium']}")
        print(f"  Info: {alerts['info']}")

        print(f"\nSTATUS: {report['status']}")

        if report["alert_details"]:
            print(f"\nALERT DETAILS:")
            for alert in report["alert_details"]:
                severity_symbol = {
                    "critical": "[✗]",
                    "high": "[!]",
                    "medium": "[•]",
                    "info": "[•]"
                }.get(alert["severity"], "[?]")

                print(f"\n{severity_symbol} {alert['operation'].upper()}")
                print(f"    Severity: {alert['severity']}")
                print(f"    Message: {alert['message']}")
                print(f"    Action: {alert['action']}")

        print(f"\n{'='*70}\n")

        return report


# Global watchdog instance
kai_log_watchdog = None


def initialize_log_watchdog(
    log_directory: str = "/var/lib/kai/logs",
    crypto_system=None
) -> LogWatchdog:
    """Initialize the log watchdog"""
    global kai_log_watchdog

    kai_log_watchdog = LogWatchdog(
        log_directory=log_directory,
        crypto_system=crypto_system
    )

    return kai_log_watchdog


def get_log_watchdog() -> LogWatchdog:
    """Get the global log watchdog"""
    global kai_log_watchdog

    if kai_log_watchdog is None:
        kai_log_watchdog = LogWatchdog()

    return kai_log_watchdog
