"""Nuclei vulnerability scanner integration."""

import json
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime


class NucleiScanner:
    """Integrate Nuclei for vulnerability scanning."""

    # Nuclei severity levels
    NUCLEI_SEVERITIES = {
        "info": "info",
        "low": "low",
        "medium": "medium",
        "high": "high",
        "critical": "critical",
    }

    # Common Nuclei template categories
    TEMPLATE_CATEGORIES = [
        "cves",
        "web",
        "network",
        "dns",
        "file",
        "headless",
        "http",
        "javascript",
        "miscellaneous",
        "takeovers",
        "technologies",
        "vulnerability",
        "workflows",
    ]

    def __init__(self, nuclei_path: str = "nuclei"):
        """
        Initialize Nuclei scanner.

        Args:
            nuclei_path: Path to nuclei binary (default: assumes in PATH)
        """
        self.nuclei_path = nuclei_path
        self.scan_history: List[Dict[str, Any]] = []

    def scan_target(
        self,
        target: str,
        templates: Optional[List[str]] = None,
        severity: Optional[str] = None,
        timeout: int = 300,
        use_workflows: bool = True,
    ) -> Dict[str, Any]:
        """
        Scan target with Nuclei.

        Args:
            target: URL or domain to scan
            templates: Specific templates to use
            severity: Minimum severity (info, low, medium, high, critical)
            timeout: Scan timeout in seconds
            use_workflows: Use Nuclei workflows

        Returns:
            {
                'status': 'success'|'error',
                'target': target,
                'findings': [...],
                'template_count': N,
                'scan_time': seconds,
                'timestamp': ISO string
            }
        """
        scan_record = {
            "target": target,
            "started_at": datetime.utcnow().isoformat(),
            "status": "running",
        }

        # Build nuclei command
        cmd = [self.nuclei_path, "-u", target, "-json"]

        # Add severity filter
        if severity:
            severity_map = {"info": "info", "low": "low", "medium": "medium", "high": "high,critical", "critical": "critical"}
            cmd.extend(["-severity", severity_map.get(severity, severity)])

        # Add templates
        if templates:
            cmd.extend(["-t"] + templates)
        elif use_workflows:
            cmd.append("-wf")  # Use all workflows
        else:
            cmd.append("-t")
            cmd.append("templates")  # Use default templates directory

        # Run scan
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            findings = self._parse_nuclei_output(result.stdout)
            scan_record["status"] = "completed"
            scan_record["findings"] = findings
            scan_record["finding_count"] = len(findings)
            scan_record["return_code"] = result.returncode

            if result.stderr:
                scan_record["stderr"] = result.stderr

        except subprocess.TimeoutExpired:
            scan_record["status"] = "timeout"
            scan_record["findings"] = []
            scan_record["error"] = f"Scan timed out after {timeout} seconds"

        except FileNotFoundError:
            scan_record["status"] = "error"
            scan_record["findings"] = []
            scan_record["error"] = f"Nuclei not found at {self.nuclei_path}"

        except Exception as e:
            scan_record["status"] = "error"
            scan_record["findings"] = []
            scan_record["error"] = str(e)

        scan_record["completed_at"] = datetime.utcnow().isoformat()
        self.scan_history.append(scan_record)

        return scan_record

    def scan_batch(
        self,
        targets: List[str],
        templates: Optional[List[str]] = None,
        severity: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Scan multiple targets.

        Returns aggregated results.
        """
        results = {
            "targets": targets,
            "total_targets": len(targets),
            "scans": [],
            "total_findings": 0,
            "findings_by_severity": {},
            "started_at": datetime.utcnow().isoformat(),
        }

        for target in targets:
            scan = self.scan_target(target, templates, severity)
            results["scans"].append(scan)
            results["total_findings"] += scan.get("finding_count", 0)

            # Aggregate findings by severity
            for finding in scan.get("findings", []):
                severity = finding.get("severity", "info")
                results["findings_by_severity"][severity] = (
                    results["findings_by_severity"].get(severity, 0) + 1
                )

        results["completed_at"] = datetime.utcnow().isoformat()
        return results

    def list_templates(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        List available Nuclei templates.

        Args:
            category: Filter by category (cves, web, etc.)

        Returns:
            List of available templates
        """
        cmd = [self.nuclei_path, "-list-templates"]

        if category:
            cmd.extend(["-template-type", category])

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            templates = result.stdout.strip().split("\n")

            return {
                "status": "success",
                "category": category,
                "template_count": len(templates),
                "templates": templates,
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def validate_nuclei_setup(self) -> Dict[str, Any]:
        """Validate Nuclei installation and configuration."""
        validation = {
            "nuclei_path": self.nuclei_path,
            "is_installed": False,
            "version": None,
            "templates_available": False,
        }

        # Check if nuclei exists
        try:
            result = subprocess.run(
                [self.nuclei_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            validation["is_installed"] = result.returncode == 0
            validation["version"] = result.stdout.strip()
        except Exception:
            validation["is_installed"] = False

        # Check if templates are available
        if validation["is_installed"]:
            try:
                result = subprocess.run(
                    [self.nuclei_path, "-template-list"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                validation["templates_available"] = result.returncode == 0
            except Exception:
                validation["templates_available"] = False

        return validation

    def _parse_nuclei_output(self, output: str) -> List[Dict[str, Any]]:
        """Parse Nuclei JSON output into standardized findings."""
        findings = []

        for line in output.strip().split("\n"):
            if not line:
                continue

            try:
                item = json.loads(line)

                # Convert Nuclei format to our finding format
                finding = {
                    "id": f"nuclei_{item.get('template_id', 'unknown')}",
                    "source": "nuclei",
                    "url": item.get("host", ""),
                    "vulnerability_type": item.get("info", {}).get("name", "Unknown"),
                    "severity": item.get("info", {}).get("severity", "info").lower(),
                    "description": item.get("info", {}).get("description", ""),
                    "template_id": item.get("template_id", ""),
                    "template_path": item.get("template_path", ""),
                    "tags": item.get("info", {}).get("tags", []),
                    "reference": item.get("info", {}).get("reference", []),
                    "matched_line": item.get("matched_line", ""),
                    "curl_command": item.get("curl_command", ""),
                    "found_at": datetime.utcnow().isoformat(),
                }

                findings.append(finding)

            except json.JSONDecodeError:
                # Skip malformed JSON lines
                continue

        return findings

    def get_scan_history(self) -> List[Dict[str, Any]]:
        """Get history of all scans."""
        return self.scan_history

    def get_scan_stats(self) -> Dict[str, Any]:
        """Get statistics about performed scans."""
        if not self.scan_history:
            return {
                "total_scans": 0,
                "successful_scans": 0,
                "failed_scans": 0,
                "total_findings": 0,
            }

        successful = sum(1 for s in self.scan_history if s.get("status") == "completed")
        failed = sum(1 for s in self.scan_history if s.get("status") == "error")
        total_findings = sum(s.get("finding_count", 0) for s in self.scan_history)

        findings_by_severity = {}
        for scan in self.scan_history:
            for finding in scan.get("findings", []):
                severity = finding.get("severity", "info")
                findings_by_severity[severity] = findings_by_severity.get(severity, 0) + 1

        return {
            "total_scans": len(self.scan_history),
            "successful_scans": successful,
            "failed_scans": failed,
            "total_findings": total_findings,
            "findings_by_severity": findings_by_severity,
        }
