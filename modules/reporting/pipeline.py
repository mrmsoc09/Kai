"""
Content-to-Finding Pipeline
Bridges content/reporting/ Content Generation Engine with submission pipeline
"""
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

sys.path.insert(0, '/a0/usr/projects/kaisonone/content/reporting')
sys.path.insert(0, '/a0/usr/projects/kaisonone/tools/submission')

@dataclass
class GeneratedReport:
    """Report generated from finding by Content Engine."""
    finding_id: str
    title: str
    description: str
    impact: str
    remediation: str
    poc_steps: List[str]
    severity: str
    cvss_score: float
    bounty_estimate: str
    template_used: str
    raw_content: str

class ContentToFindingPipeline:
    """
    Pipeline bridging Content Generation Engine with submission system.
    Takes raw findings, generates BBP-optimized reports, routes to submission.
    """

    def __init__(self):
        self.content_engine_path = Path('/a0/usr/projects/kaisonone/content/reporting')
        self.submission_path = Path('/a0/usr/projects/kaisonone/tools/submission')
        self.llm_budget_router = None  # Initialized on demand

    def load_content_engine(self):
        """Lazy load Content Generation Engine."""
        try:
            from content_engine.generators.intelligence import IntelligenceReportGenerator
            return IntelligenceReportGenerator()
        except ImportError as e:
            print(f"Content Engine not installed: {e}")
            return None

    def generate_report(self, finding: Dict[str, Any], 
                       bbp_mode: str = "public_bbp") -> GeneratedReport:
        """
        Generate BBP-optimized report from finding.

        Args:
            finding: Raw vuln finding from tools
            bbp_mode: public_bbp, private_contract, or enterprise_audit

        Returns:
            GeneratedReport ready for submission
        """
        # Load BBP config for template selection
        bbp_config = self._load_bbp_config(bbp_mode)

        # Extract finding details
        vuln_type = finding.get('type', 'unknown')
        severity = finding.get('severity', 'medium')
        target = finding.get('target', 'unknown')
        evidence = finding.get('evidence', {})

        # Generate content using Content Engine or fallback
        engine = self.load_content_engine()
        if engine:
            content = engine.generate(
                finding=finding,
                template=bbp_config.get('reporting_template', 'hackerone_public'),
                mode=bbp_mode
            )
        else:
            # Fallback generation
            content = self._fallback_generate(finding, bbp_mode)

        # Estimate bounty
        bounty = self._estimate_bounty(vuln_type, severity, bbp_mode)

        return GeneratedReport(
            finding_id=finding.get('id', 'unknown'),
            title=f"{vuln_type.upper()} in {target}",
            description=content.get('description', ''),
            impact=content.get('impact', ''),
            remediation=content.get('remediation', ''),
            poc_steps=content.get('poc_steps', []),
            severity=severity,
            cvss_score=finding.get('cvss', 5.0),
            bounty_estimate=bounty,
            template_used=bbp_config.get('reporting_template'),
            raw_content=json.dumps(content)
        )

    def _load_bbp_config(self, mode: str) -> Dict:
        """Load BBP mode configuration."""
        import yaml
        try:
            with open('/a0/usr/projects/kaisonone/config/bbp_modes.yaml') as f:
                data = yaml.safe_load(f)
            return data.get('modes', {}).get(mode, {})
        except Exception as e:
            print(f"BBP config error: {e}")
            return {}

    def _fallback_generate(self, finding: Dict, mode: str) -> Dict:
        """Fallback report generation when Content Engine unavailable."""
        vuln_type = finding.get('type', 'vulnerability')
        target = finding.get('target', 'target')

        return {
            'description': f"A {vuln_type} vulnerability was identified in {target}.",
            'impact': f"This vulnerability could allow attackers to compromise {target}.",
            'remediation': f"Implement proper input validation and sanitization for {vuln_type}.",
            'poc_steps': [
                f"1. Navigate to {target}",
                f"2. Identify {vuln_type} vector",
                f"3. Exploit vulnerability",
                f"4. Observe impact"
            ]
        }

    def _estimate_bounty(self, vuln_type: str, severity: str, mode: str) -> str:
        """Estimate bounty range based on vuln characteristics."""
        ranges = {
            'critical': {'public': '$5,000 - $50,000', 'private': '$10,000 - $100,000'},
            'high': {'public': '$1,000 - $10,000', 'private': '$5,000 - $50,000'},
            'medium': {'public': '$200 - $2,000', 'private': '$1,000 - $10,000'},
            'low': {'public': '$100 - $500', 'private': '$500 - $2,000'}
        }

        prog_type = 'private' if mode != 'public_bbp' else 'public'
        return ranges.get(severity, {}).get(prog_type, 'Unknown')

    def route_to_submission(self, report: GeneratedReport, 
                           platform: str = "hackerone") -> Dict:
        """
        Route generated report to submission system.

        Args:
            report: GeneratedReport from generate_report()
            platform: hackerone, bugcrowd, or self_hosted

        Returns:
            Submission result with tracking ID
        """
        # Format for platform
        formatted = self._format_for_platform(report, platform)

        # Submit via submission tools
        # This integrates with tools/submission/ submission pipeline

        return {
            'status': 'ready_for_hil_review',
            'platform': platform,
            'finding_id': report.finding_id,
            'title': report.title,
            'bounty_estimate': report.bounty_estimate,
            'formatted_report': formatted,
            'next_step': 'awaiting_human_approval'
        }

    def _format_for_platform(self, report: GeneratedReport, 
                            platform: str) -> Dict:
        """Format report for specific BBP platform."""
        formatters = {
            'hackerone': self._format_hackerone,
            'bugcrowd': self._format_bugcrowd,
            'self_hosted': self._format_self_hosted
        }

        formatter = formatters.get(platform, self._format_hackerone)
        return formatter(report)

    def _format_hackerone(self, report: GeneratedReport) -> Dict:
        """Format for HackerOne submission."""
        return {
            'title': report.title,
            'vulnerability_types': [report.severity],
            'description': report.description,
            'impact': report.impact,
            'reproduction_steps': '\n'.join(report.poc_steps),
            'remediation': report.remediation,
            'severity': report.severity,
            'cvss_score': report.cvss_score
        }

    def _format_bugcrowd(self, report: GeneratedReport) -> Dict:
        """Format for Bugcrowd submission."""
        return {
            'title': report.title,
            'description': f"{report.description}\n\nImpact: {report.impact}",
            'proof_of_concept': '\n'.join(report.poc_steps),
            'remediation': report.remediation,
            'severity': report.severity.upper()
        }

    def _format_self_hosted(self, report: GeneratedReport) -> Dict:
        """Format for self-hosted BBP submission."""
        return {
            'report': {
                'title': report.title,
                'finding_type': report.severity,
                'description': report.description,
                'impact': report.impact,
                'poc': report.poc_steps,
                'remediation': report.remediation,
                'cvss': report.cvss_score,
                'bounty_estimate': report.bounty_estimate
            }
        }

if __name__ == '__main__':
    # Example usage
    pipeline = ContentToFindingPipeline()

    test_finding = {
        'id': 'test-001',
        'type': 'xss',
        'severity': 'high',
        'target': 'https://example.com/search',
        'evidence': {'payload': '<script>alert(1)</script>'},
        'cvss': 7.5
    }

    report = pipeline.generate_report(test_finding, 'public_bbp')
    submission = pipeline.route_to_submission(report, 'hackerone')

    print(json.dumps({
        'title': report.title,
        'bounty_estimate': report.bounty_estimate,
        'status': submission['status']
    }, indent=2))
