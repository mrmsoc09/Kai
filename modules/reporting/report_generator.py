"""
Per-Scan Report Generation with Quality Scoring
Intelligent report generation with automatic quality assessment
"""
import json
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

class QualityTier(Enum):
    EXCELLENT = "excellent"  # 90-100 score
    GOOD = "good"           # 70-89 score  
    ACCEPTABLE = "acceptable" # 50-69 score
    NEEDS_WORK = "needs_work" # 0-49 score

@dataclass
class QualityScore:
    """Quality metrics for generated report."""
    overall_score: float  # 0-100
    tier: QualityTier
    completeness: float   # 0-100
    clarity: float        # 0-100
    impact_description: float  # 0-100
    poc_quality: float    # 0-100
    remediation: float    # 0-100
    improvement_suggestions: List[str]

@dataclass
class ScanReport:
    """Complete per-scan report with findings and metadata."""
    report_id: str
    scan_id: str
    target: str
    scan_start: datetime
    scan_end: datetime
    bbp_mode: str
    findings: List[Dict]
    summary: Dict
    quality_score: QualityScore
    formatted_submissions: Dict[str, Any]
    export_paths: Dict[str, str]
    recommendations: List[str]

class PerScanReportGenerator:
    """
    Generates comprehensive per-scan reports with automatic quality scoring.
    Integrates with intelligence engine and submission formatters.
    """

    def __init__(self):
        self.report_counter = 0

    def generate(self, scan_results: Dict, bbp_mode: str = "public_bbp") -> ScanReport:
        """
        Generate complete scan report with quality assessment.

        Args:
            scan_results: Raw scan output from tools
            bbp_mode: BBP mode for formatting

        Returns:
            ScanReport with quality scoring and formatted submissions
        """
        self.report_counter += 1
        report_id = f"RPT-{datetime.now().strftime('%Y%m%d')}-{self.report_counter:04d}"

        # Process findings through pipeline
        findings = self._process_findings(scan_results.get('findings', []), bbp_mode)

        # Generate summary statistics
        summary = self._generate_summary(findings)

        # Generate formatted submissions for each platform
        formatted = self._format_for_platforms(findings, bbp_mode)

        # Calculate quality score
        quality = self._calculate_quality(findings, scan_results)

        # Generate recommendations
        recommendations = self._generate_recommendations(quality, findings)

        # Export to file paths
        export_paths = self._export_report(report_id, scan_report={
            'findings': findings,
            'summary': summary,
            'quality': quality,
            'formatted': formatted
        })

        return ScanReport(
            report_id=report_id,
            scan_id=scan_results.get('scan_id', 'unknown'),
            target=scan_results.get('target', 'unknown'),
            scan_start=scan_results.get('start_time', datetime.now()),
            scan_end=datetime.now(),
            bbp_mode=bbp_mode,
            findings=findings,
            summary=summary,
            quality_score=quality,
            formatted_submissions=formatted,
            export_paths=export_paths,
            recommendations=recommendations
        )

    def _process_findings(self, findings: List[Dict], bbp_mode: str) -> List[Dict]:
        """Process and enrich raw findings."""
        processed = []

        for finding in findings:
            # Enrich with BBP-specific data
            enriched = {
                **finding,
                'bounty_potential': self._estimate_bounty(finding, bbp_mode),
                'submission_ready': self._check_submission_ready(finding),
                'platform_optimizations': self._get_platform_tips(finding)
            }
            processed.append(enriched)

        # Sort by severity and bounty potential
        processed.sort(key=lambda x: (
            {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(x.get('severity', 'low'), 4),
            -self._parse_bounty_estimate(x.get('bounty_potential', '0'))
        ))

        return processed

    def _generate_summary(self, findings: List[Dict]) -> Dict:
        """Generate executive summary of scan."""
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        total_bounty_estimate = 0

        for f in findings:
            sev = f.get('severity', 'low')
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            total_bounty_estimate += self._parse_bounty_estimate(
                f.get('bounty_potential', '0')
            )

        return {
            'total_findings': len(findings),
            'severity_breakdown': severity_counts,
            'estimated_total_bounty': f"${total_bounty_estimate:,}",
            'submission_ready_count': sum(1 for f in findings if f.get('submission_ready')),
            'critical_findings': severity_counts.get('critical', 0),
            'recommendation': self._summary_recommendation(severity_counts)
        }

    def _format_for_platforms(self, findings: List[Dict], bbp_mode: str) -> Dict:
        """Generate platform-specific formatted submissions."""
        return {
            'hackerone': [self._format_hackerone(f) for f in findings],
            'bugcrowd': [self._format_bugcrowd(f) for f in findings],
            'self_hosted': [self._format_self_hosted(f) for f in findings]
        }

    def _calculate_quality(self, findings: List[Dict], scan_results: Dict) -> QualityScore:
        """Calculate comprehensive quality score."""

        # Completeness: Do findings have all required fields?
        completeness_scores = []
        for f in findings:
            required = ['type', 'severity', 'target', 'description', 'impact']
            present = sum(1 for field in required if f.get(field))
            completeness_scores.append((present / len(required)) * 100)

        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0

        # Clarity: Are descriptions detailed enough?
        clarity_scores = []
        for f in findings:
            desc_len = len(f.get('description', ''))
            if desc_len > 500:
                clarity_scores.append(100)
            elif desc_len > 200:
                clarity_scores.append(70)
            elif desc_len > 100:
                clarity_scores.append(40)
            else:
                clarity_scores.append(20)

        avg_clarity = sum(clarity_scores) / len(clarity_scores) if clarity_scores else 0

        # Impact quality
        impact_scores = []
        for f in findings:
            impact = f.get('impact', '')
            if 'compromise' in impact.lower() or 'extract' in impact.lower():
                impact_scores.append(100)
            elif 'access' in impact.lower():
                impact_scores.append(70)
            else:
                impact_scores.append(40)

        avg_impact = sum(impact_scores) / len(impact_scores) if impact_scores else 0

        # PoC quality
        poc_scores = []
        for f in findings:
            poc = f.get('poc_steps', [])
            if len(poc) >= 5:
                poc_scores.append(100)
            elif len(poc) >= 3:
                poc_scores.append(70)
            else:
                poc_scores.append(40)

        avg_poc = sum(poc_scores) / len(poc_scores) if poc_scores else 0

        # Remediation quality
        remediation_scores = []
        for f in findings:
            rem = f.get('remediation', '')
            if len(rem) > 200:
                remediation_scores.append(100)
            elif len(rem) > 100:
                remediation_scores.append(70)
            else:
                remediation_scores.append(40)

        avg_remediation = sum(remediation_scores) / len(remediation_scores) if remediation_scores else 0

        # Overall score (weighted)
        overall = (
            avg_completeness * 0.25 +
            avg_clarity * 0.20 +
            avg_impact * 0.25 +
            avg_poc * 0.15 +
            avg_remediation * 0.15
        )

        # Determine tier
        if overall >= 90:
            tier = QualityTier.EXCELLENT
        elif overall >= 70:
            tier = QualityTier.GOOD
        elif overall >= 50:
            tier = QualityTier.ACCEPTABLE
        else:
            tier = QualityTier.NEEDS_WORK

        # Generate improvement suggestions
        suggestions = []
        if avg_completeness < 80:
            suggestions.append("Add missing fields: type, severity, target, description, impact")
        if avg_clarity < 70:
            suggestions.append("Expand descriptions to 200+ characters with technical details")
        if avg_impact < 60:
            suggestions.append("Strengthen impact statements: describe data at risk, user compromise")
        if avg_poc < 70:
            suggestions.append("Add more detailed reproduction steps (5+ steps)")
        if avg_remediation < 70:
            suggestions.append("Provide specific remediation guidance with code examples")

        return QualityScore(
            overall_score=round(overall, 1),
            tier=tier,
            completeness=round(avg_completeness, 1),
            clarity=round(avg_clarity, 1),
            impact_description=round(avg_impact, 1),
            poc_quality=round(avg_poc, 1),
            remediation=round(avg_remediation, 1),
            improvement_suggestions=suggestions if suggestions else ["Report quality is good - minor polish only"]
        )

    def _generate_recommendations(self, quality: QualityScore, findings: List[Dict]) -> List[str]:
        """Generate action recommendations based on scan results."""
        recommendations = []

        critical_count = sum(1 for f in findings if f.get('severity') == 'critical')
        if critical_count > 0:
            recommendations.append(f"🚨 PRIORITY: Submit {critical_count} critical findings immediately")

        high_count = sum(1 for f in findings if f.get('severity') == 'high')
        if high_count > 3:
            recommendations.append(f"Consider batching {high_count} high-severity findings by target")

        if quality.tier == QualityTier.NEEDS_WORK:
            recommendations.append("Quality Score below 50 - regenerate reports with template guidance")

        duplicate_risk = sum(1 for f in findings if f.get('duplicate_probability', 0) > 0.7)
        if duplicate_risk > 0:
            recommendations.append(f"⚠️ {duplicate_risk} findings have high duplicate risk - verify uniqueness")

        return recommendations if recommendations else ["✅ Scan quality good - proceed to HiL review"]

    def _export_report(self, report_id: str, scan_report: Dict) -> Dict[str, str]:
        """Export report to multiple formats."""
        import os
        from pathlib import Path

        base = Path('/a0/usr/projects/kaisonone/output/reports')
        base.mkdir(parents=True, exist_ok=True)

        paths = {}

        # JSON export
        json_path = base / f"{report_id}.json"
        with open(json_path, 'w') as f:
            json.dump(scan_report, f, indent=2, default=str)
        paths['json'] = str(json_path)

        # Markdown summary
        md_path = base / f"{report_id}.md"
        md_content = self._generate_markdown(report_id, scan_report)
        with open(md_path, 'w') as f:
            f.write(md_content)
        paths['markdown'] = str(md_path)

        return paths

    def _generate_markdown(self, report_id: str, scan_report: Dict) -> str:
        """Generate human-readable markdown report."""
        quality = scan_report.get('quality', {})
        summary = scan_report.get('summary', {})

        md = f"""# Scan Report: {report_id}

## Executive Summary

- **Total Findings:** {summary.get('total_findings', 0)}
- **Critical:** {summary.get('severity_breakdown', {}).get('critical', 0)}
- **High:** {summary.get('severity_breakdown', {}).get('high', 0)}
- **Medium:** {summary.get('severity_breakdown', {}).get('medium', 0)}
- **Estimated Bounty:** {summary.get('estimated_total_bounty', 'Unknown')}

## Quality Score: {quality.get('overall_score', 0)}/100 ({quality.get('tier', 'unknown').value})

### Breakdown
- Completeness: {quality.get('completeness', 0)}%
- Clarity: {quality.get('clarity', 0)}%
- Impact Description: {quality.get('impact_description', 0)}%
- PoC Quality: {quality.get('poc_quality', 0)}%
- Remediation: {quality.get('remediation', 0)}%

### Improvements Needed
"""
        for suggestion in quality.get('improvement_suggestions', []):
            md += f"- {suggestion}\n"

        return md

    def _format_hackerone(self, finding: Dict) -> Dict:
        """Format single finding for HackerOne."""
        return {
            'title': finding.get('title', 'Vulnerability Report'),
            'vulnerability_types': [finding.get('type', 'general')],
            'severity': finding.get('severity', 'medium'),
            'description': finding.get('description', ''),
            'impact': finding.get('impact', ''),
            'reproduction': '\n'.join(finding.get('poc_steps', [])),
            'remediation': finding.get('remediation', '')
        }

    def _format_bugcrowd(self, finding: Dict) -> Dict:
        """Format single finding for Bugcrowd."""
        return {
            'title': finding.get('title', 'Vulnerability Report'),
            'description': f"{finding.get('description', '')}\n\nImpact: {finding.get('impact', '')}",
            'proof_of_concept': '\n'.join(finding.get('poc_steps', [])),
            'remediation': finding.get('remediation', ''),
            'severity': finding.get('severity', 'medium').upper()
        }

    def _format_self_hosted(self, finding: Dict) -> Dict:
        """Format for self-hosted BBP."""
        return finding

    def _estimate_bounty(self, finding: Dict, bbp_mode: str) -> str:
        """Quick bounty estimate."""
        sev = finding.get('severity', 'medium')
        ranges = {
            'critical': '$5K-$50K+',
            'high': '$1K-$10K',
            'medium': '$200-$2K',
            'low': '$50-$500'
        }
        return ranges.get(sev, 'Unknown')

    def _check_submission_ready(self, finding: Dict) -> bool:
        """Check if finding has minimum required fields."""
        required = ['type', 'severity', 'target', 'description']
        return all(finding.get(f) for f in required)

    def _get_platform_tips(self, finding: Dict) -> Dict:
        """Get platform-specific tips for this finding."""
        return {
            'hackerone_tip': 'Include video PoC for faster triage',
            'bugcrowd_tip': 'Focus on business impact in description',
            'self_hosted_tip': 'Include CVSS vector string'
        }

    def _parse_bounty_estimate(self, estimate: str) -> int:
        """Parse bounty string to numeric value."""
        import re
        numbers = re.findall(r'[\d,]+', estimate)
        if numbers:
            return int(numbers[0].replace(',', ''))
        return 0

    def _summary_recommendation(self, severity_counts: Dict) -> str:
        """Generate recommendation based on severity distribution."""
        if severity_counts.get('critical', 0) > 0:
            return "Immediate submission recommended - critical findings present"
        elif severity_counts.get('high', 0) >= 3:
            return "Strong bounty potential - batch and submit"
        elif sum(severity_counts.values()) == 0:
            return "No findings detected - consider expanding scope"
        else:
            return "Findings ready for HiL review"

if __name__ == "__main__":
    generator = PerScanReportGenerator()

    test_scan = {
        "scan_id": "test-scan-001",
        "target": "https://example.com",
        "findings": [
            {
                "type": "xss",
                "severity": "high",
                "target": "https://example.com/search",
                "description": "Reflected XSS in search parameter allows script injection",
                "impact": "Session hijacking and credential theft possible",
                "poc_steps": ["1. Go to search", "2. Enter <script>alert(1)</script>", "3. Observe alert"],
                "remediation": "Implement input validation and output encoding"
            }
        ]
    }

    report = generator.generate(test_scan, "public_bbp")
    print(f"Report ID: {report.report_id}")
    print(f"Quality Score: {report.quality_score.overall_score}/100")
    print(f"Tier: {report.quality_score.tier.value}")
