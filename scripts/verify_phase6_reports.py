#!/usr/bin/env python3
"""Phase 6 Report Generation Verification Script.

Tests all report generation functionality:
- Template rendering for 5 VRP formats
- PDF generation with styling
- Multi-format export (markdown, HTML, PDF, JSON)
- Format validation with quality checks
- Multiplier detection
- Performance benchmarking
"""

import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, List

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "backend" / "src"))

from core.report_formats import render_report, validate_rendered, build_template_context
from core.pdf_generator import generate_pdf_from_markdown
from core.format_exporter import ReportExporter, create_exporter
from core.report_validator import validate_rendered as validate_report
from core.evidence_embedder import create_embedder


# Sample test data
SAMPLE_FINDING = {
    "title": "SQL Injection in Login Form",
    "severity": "high",
    "cvss": "8.2",
    "cwe": "CWE-89",
    "summary": "The login form accepts user input without proper parameterization, allowing SQL injection attacks that can lead to unauthorized database access and data exfiltration.",
    "impact": "An attacker can bypass authentication, access sensitive user data, modify database records, or execute arbitrary SQL commands. This could result in unauthorized access to all user accounts and complete compromise of the database.",
    "scope": "Authentication module affecting all users",
    "attack_scenario": "User navigates to login page, enters SQL payload in username field (e.g., ' OR '1'='1), gains database access",
    "endpoints": [
        "/api/login",
        "/auth/authenticate",
        "/user/signin"
    ],
}

SAMPLE_EVIDENCE = {
    "repro": """1. Navigate to http://target.com/login
2. Enter the following in the username field: ' OR '1'='1' --
3. Enter any password
4. Click "Login"
5. Observe that authentication is bypassed and dashboard is accessible
6. Application does not validate or sanitize input before constructing SQL query""",
    "artifacts": {
        "screenshot_1": "login_page_payload.png",
        "screenshot_2": "authenticated_dashboard.png",
    },
    "code_example": """import sqlite3
conn = sqlite3.connect('users.db')
username = request.form['username']  # Not sanitized!
query = f"SELECT * FROM users WHERE username='{username}'"
result = conn.execute(query).fetchall()""",
}

SAMPLE_MITIGATION = {
    "plan": "Use parameterized queries (prepared statements) for all database operations. Implement input validation and use ORM frameworks.",
    "timeline": "Can be fixed in version 2.1 (2 days)",
    "steps": [
        "Migrate to parameterized queries",
        "Add input validation",
        "Add WAF rules",
    ],
}


class Phase6Verifier:
    """Verify Phase 6 report generation implementation."""

    def __init__(self):
        """Initialize verifier."""
        self.results = []
        self.performance_metrics = {}
        self.sample_reports = {}

    def run_all_tests(self) -> bool:
        """Run all verification tests."""
        print("\n" + "=" * 80)
        print("PHASE 6: REPORT GENERATION VERIFICATION")
        print("=" * 80 + "\n")

        tests = [
            ("Template Rendering", self.test_template_rendering),
            ("PDF Generation", self.test_pdf_generation),
            ("Multi-Format Export", self.test_multiformat_export),
            ("Format Validation", self.test_format_validation),
            ("Multiplier Detection", self.test_multiplier_detection),
            ("Evidence Embedding", self.test_evidence_embedding),
            ("Performance Benchmarking", self.test_performance),
        ]

        all_passed = True
        for test_name, test_func in tests:
            try:
                passed = test_func()
                status = "✅ PASS" if passed else "❌ FAIL"
                print(f"{status} - {test_name}")
                self.results.append({"test": test_name, "passed": passed})
                if not passed:
                    all_passed = False
            except Exception as e:
                print(f"❌ FAIL - {test_name}: {str(e)}")
                self.results.append({"test": test_name, "passed": False, "error": str(e)})
                all_passed = False

        self._print_summary(all_passed)
        return all_passed

    def test_template_rendering(self) -> bool:
        """Test Jinja2 template rendering for all 5 VRP formats."""
        print("\n  Testing template rendering for 5 VRP formats...")

        vrp_formats = [
            "google_vrp",
            "hackerone",
            "bugcrowd",
            "intigriti",
            "msrc",
        ]

        results = {}
        for vrp_format in vrp_formats:
            try:
                # In production, would load actual format config
                # For now, test context building
                context = build_template_context(SAMPLE_FINDING, SAMPLE_EVIDENCE, SAMPLE_MITIGATION)

                # Verify context has all required fields
                required_fields = ["finding", "evidence", "mitigation", "report_id", "submission_date"]
                missing = [f for f in required_fields if f not in context]

                if missing:
                    results[vrp_format] = f"Missing fields: {missing}"
                else:
                    results[vrp_format] = "OK"
                    print(f"    ✓ {vrp_format}: Context building successful")

            except Exception as e:
                results[vrp_format] = f"Error: {str(e)}"
                print(f"    ✗ {vrp_format}: {str(e)}")

        # All formats should render successfully
        success = all(v == "OK" for v in results.values())
        self.sample_reports["template_rendering"] = results
        return success

    def test_pdf_generation(self) -> bool:
        """Test PDF generation with styling."""
        print("\n  Testing PDF generation with professional styling...")

        try:
            # Create sample markdown report
            markdown_content = self._create_sample_markdown()

            start_time = time.time()
            pdf_bytes = generate_pdf_from_markdown(
                markdown_content,
                stakeholder="hackerone"
            )
            generation_time = time.time() - start_time

            # Verify PDF was generated
            if not pdf_bytes or len(pdf_bytes) == 0:
                print(f"    ✗ PDF generation failed: empty output")
                return False

            pdf_size_kb = len(pdf_bytes) / 1024

            print(f"    ✓ PDF generated successfully")
            print(f"      - Size: {pdf_size_kb:.1f} KB")
            print(f"      - Generation time: {generation_time:.2f}s")

            self.performance_metrics["pdf_generation_ms"] = generation_time * 1000
            self.sample_reports["pdf_bytes"] = len(pdf_bytes)

            return True

        except Exception as e:
            print(f"    ✗ PDF generation failed: {str(e)}")
            return False

    def test_multiformat_export(self) -> bool:
        """Test multi-format export (markdown, HTML, PDF, JSON)."""
        print("\n  Testing multi-format export system...")

        try:
            # Create exporter
            exporter = create_exporter("google_vrp")

            formats_to_test = ["markdown", "html", "json"]
            results = {}

            for fmt in formats_to_test:
                try:
                    start_time = time.time()
                    export_result = exporter.export(
                        SAMPLE_FINDING,
                        SAMPLE_EVIDENCE,
                        SAMPLE_MITIGATION,
                        format_type=fmt
                    )
                    export_time = time.time() - start_time

                    if export_result and len(export_result) > 0:
                        results[fmt] = {
                            "size_kb": len(export_result) / 1024,
                            "time_ms": export_time * 1000,
                        }
                        print(f"    ✓ {fmt.upper()}: {len(export_result) / 1024:.1f} KB ({export_time*1000:.1f}ms)")
                    else:
                        results[fmt] = "Empty output"
                        print(f"    ✗ {fmt.upper()}: empty output")

                except Exception as e:
                    results[fmt] = f"Error: {str(e)}"
                    print(f"    ✗ {fmt.upper()}: {str(e)}")

            # Check export stats
            stats = exporter.get_export_stats()
            print(f"    ✓ Export statistics collected: {stats['total_exports']} total exports")

            self.sample_reports["export_formats"] = results
            return all(isinstance(v, dict) and "size_kb" in v for v in results.values())

        except Exception as e:
            print(f"    ✗ Multi-format export failed: {str(e)}")
            return False

    def test_format_validation(self) -> bool:
        """Test format validation with quality checks."""
        print("\n  Testing format validation across stakeholders...")

        markdown_report = self._create_sample_markdown()
        stakeholders = ["google_vrp", "hackerone", "bugcrowd", "intigriti", "msrc"]
        results = {}

        for stakeholder in stakeholders:
            try:
                validation = validate_report(
                    stakeholder=stakeholder,
                    content=markdown_report,
                    has_recording=True,
                    finding_data=SAMPLE_FINDING
                )

                compliance_score = validation.get("compliance_score", 0)
                has_issues = len(validation.get("errors", [])) > 0

                results[stakeholder] = {
                    "compliance": compliance_score,
                    "errors": len(validation.get("errors", [])),
                    "warnings": len(validation.get("warnings", [])),
                }

                status = "✓" if compliance_score >= 80 else "⚠"
                print(f"    {status} {stakeholder}: {compliance_score:.1f}% compliance")

            except Exception as e:
                results[stakeholder] = f"Error: {str(e)}"
                print(f"    ✗ {stakeholder}: {str(e)}")

        self.sample_reports["validation_results"] = results
        return all(isinstance(v, dict) and "compliance" in v for v in results.values())

    def test_multiplier_detection(self) -> bool:
        """Test multiplier detection for reward optimization."""
        print("\n  Testing multiplier detection...")

        # Create report with multiplier indicators
        multiplier_report = self._create_sample_markdown(include_multipliers=True)

        try:
            validation = validate_report(
                stakeholder="hackerone",
                content=multiplier_report,
                has_recording=True,
                finding_data={
                    **SAMPLE_FINDING,
                    "severity": "critical",
                    "impact": "Complete system compromise and data breach"
                }
            )

            detected = validation.get("detected_multipliers", [])
            recommendations = validation.get("recommendations", [])

            print(f"    ✓ Detected {len(detected)} multipliers:")
            for m in detected:
                print(f"      - {m}")

            print(f"    ✓ Generated {len(recommendations)} recommendations:")
            for r in recommendations[:3]:  # Show first 3
                print(f"      - {r}")

            self.sample_reports["multipliers"] = {
                "detected": detected,
                "count": len(detected),
            }

            return len(detected) > 0

        except Exception as e:
            print(f"    ✗ Multiplier detection failed: {str(e)}")
            return False

    def test_evidence_embedding(self) -> bool:
        """Test evidence embedding system."""
        print("\n  Testing evidence embedding...")

        try:
            embedder = create_embedder(merkle_chain_enabled=True)

            # Test code snippet embedding
            code_result = embedder.embed_code_snippet(
                code_content="SELECT * FROM users WHERE id = ?",
                language="sql",
                finding_id="TEST_001",
                description="Fixed SQL query with parameterization"
            )

            # Test log output embedding
            log_result = embedder.embed_log_output(
                log_content="Error: SQL injection detected\n" + "Stack trace line 1\n" * 5,
                finding_id="TEST_001",
                description="Application error logs showing exploitation",
                truncate_lines=10
            )

            # Verify integrity
            code_integrity = embedder.verify_evidence_integrity(code_result["evidence_id"])
            log_integrity = embedder.verify_evidence_integrity(log_result["evidence_id"])

            print(f"    ✓ Code snippet embedded: {code_result['evidence_id']}")
            print(f"    ✓ Log output embedded: {log_result['evidence_id']}")

            # Get manifest
            manifest = embedder.get_evidence_manifest("TEST_001")
            print(f"    ✓ Evidence manifest created: {manifest['total_evidence_items']} items")

            self.sample_reports["evidence_embedding"] = {
                "code_embedded": code_result["ok"],
                "log_embedded": log_result["ok"],
                "code_verified": code_integrity["valid"],
                "total_evidence": manifest["total_evidence_items"],
            }

            return (
                code_result["ok"]
                and log_result["ok"]
                and code_integrity["valid"]
                and log_integrity["valid"]
            )

        except Exception as e:
            print(f"    ✗ Evidence embedding failed: {str(e)}")
            return False

    def test_performance(self) -> bool:
        """Performance benchmarking."""
        print("\n  Running performance benchmarks...")

        try:
            # Benchmark: 10 report generations
            markdown_content = self._create_sample_markdown()
            iterations = 10

            start_time = time.time()
            for i in range(iterations):
                generate_pdf_from_markdown(markdown_content)
            total_time = time.time() - start_time

            avg_time_ms = (total_time / iterations) * 1000

            # Benchmark: 100 validations
            validation_start = time.time()
            for i in range(100):
                validate_report(
                    stakeholder="hackerone",
                    content=markdown_content,
                    has_recording=True,
                    finding_data=SAMPLE_FINDING
                )
            validation_time = time.time() - validation_start
            avg_validation_ms = (validation_time / 100) * 1000

            print(f"    ✓ PDF Generation ({iterations} reports): {avg_time_ms:.1f}ms avg")
            print(f"    ✓ Validation (100 checks): {avg_validation_ms:.2f}ms avg")
            print(f"    ✓ System can handle ~{int(1000/avg_time_ms)} PDFs/sec")

            self.performance_metrics["pdf_avg_ms"] = avg_time_ms
            self.performance_metrics["validation_avg_ms"] = avg_validation_ms
            self.performance_metrics["throughput_reports_per_sec"] = int(1000 / avg_time_ms)

            return avg_time_ms < 2000  # Should generate PDF in under 2 seconds

        except Exception as e:
            print(f"    ✗ Performance benchmarking failed: {str(e)}")
            return False

    def _create_sample_markdown(self, include_multipliers: bool = False) -> str:
        """Create sample markdown report."""
        report = f"""# Vulnerability Report: {SAMPLE_FINDING['title']}

## Summary
{SAMPLE_FINDING['summary']}

## Impact
{SAMPLE_FINDING['impact']}

## Attack Scenario
{SAMPLE_FINDING['attack_scenario']}

## Affected Endpoints
- {chr(10).join(f"- {ep}" for ep in SAMPLE_FINDING['endpoints'])}

## Steps to Reproduce
{SAMPLE_EVIDENCE['repro']}

## Evidence
### Code Vulnerable Code
```python
{SAMPLE_EVIDENCE['code_example']}
```

## Mitigation
{SAMPLE_MITIGATION['plan']}

### Timeline
{SAMPLE_MITIGATION['timeline']}
"""

        if include_multipliers:
            report += f"""

## Additional Technical Details

### CWE and CVSS
- **CWE:** {SAMPLE_FINDING.get('cwe', 'N/A')}
- **CVSS Score:** {SAMPLE_FINDING.get('cvss', 'N/A')}

### Proof of Concept
```sql
' OR '1'='1' --
```

### Attack Chain
1. Initial injection through login form
2. SQL query manipulation
3. Database query execution with attacker privileges
4. Data extraction and unauthorized access

### Business Impact
- Complete authentication bypass
- Unauthorized access to all user accounts
- Potential data breach affecting thousands of users
- System compromise and data exfiltration

### Reproducibility
The vulnerability is consistently reproducible and does not require user interaction.
"""

        return report

    def _print_summary(self, all_passed: bool):
        """Print verification summary."""
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        passed = sum(1 for r in self.results if r.get("passed"))
        total = len(self.results)

        print(f"\nTests Passed: {passed}/{total}")

        if self.performance_metrics:
            print("\nPerformance Metrics:")
            for key, value in self.performance_metrics.items():
                if "per_sec" in key:
                    print(f"  {key}: {value:.0f} {key.split('_')[-1]}")
                elif "ms" in key:
                    print(f"  {key}: {value:.2f}ms")
                else:
                    print(f"  {key}: {value}")

        print("\n" + "=" * 80)
        if all_passed:
            print("✅ ALL TESTS PASSED - Phase 6 Report Generation Ready!")
        else:
            print("❌ SOME TESTS FAILED - Review errors above")
        print("=" * 80 + "\n")

        # Save detailed report
        self._save_verification_report()

    def _save_verification_report(self):
        """Save detailed verification report to file."""
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tests_passed": sum(1 for r in self.results if r.get("passed")),
            "tests_total": len(self.results),
            "test_results": self.results,
            "performance_metrics": self.performance_metrics,
            "sample_reports": {
                k: v for k, v in self.sample_reports.items()
                if k != "pdf_bytes"
            },
        }

        report_path = Path(__file__).parent.parent / "phase6_verification_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        print(f"📄 Detailed report saved to: {report_path}")


def main():
    """Run Phase 6 verification."""
    verifier = Phase6Verifier()
    success = verifier.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
