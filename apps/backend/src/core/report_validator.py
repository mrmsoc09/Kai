"""Comprehensive report validation with content quality checks."""

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re
import logging

logger = logging.getLogger(__name__)

REQUIRED_COMMON = ["Summary", "Impact", "Steps to Reproduce", "Evidence", "Mitigation"]

STAKEHOLDER_RULES = {
    "google_vrp": {
        "required_sections": REQUIRED_COMMON + ["Timeline"],
        "min_summary_words": 50,
        "min_impact_words": 75,
        "min_repro_steps": 3,
        "multipliers": ["format compliance", "deterministic repro", "scope explicitly cited", "minimal data exposure", "no service degradation"],
    },
    "hackerone": {
        "required_sections": REQUIRED_COMMON + ["References"],
        "min_summary_words": 50,
        "min_impact_words": 75,
        "min_repro_steps": 2,
        "multipliers": ["CWE included", "CVSS provided", "PoC code included"],
    },
    "bugcrowd": {
        "required_sections": REQUIRED_COMMON + ["Attack Scenario"],
        "min_summary_words": 40,
        "min_impact_words": 60,
        "min_repro_steps": 2,
        "multipliers": ["attack narrative clarity", "business impact clear"],
    },
    "intigriti": {
        "required_sections": REQUIRED_COMMON,
        "min_summary_words": 50,
        "min_impact_words": 75,
        "min_repro_steps": 3,
        "multipliers": ["CWE referenced", "reproducible"],
    },
    "msrc": {
        "required_sections": ["Summary", "Impact", "Components", "Repro Steps", "Mitigation"],
        "min_summary_words": 50,
        "min_impact_words": 75,
        "min_repro_steps": 3,
        "multipliers": ["version info clear", "platform specific"],
    },
}


class ReportValidator:
    """Comprehensive report validator with quality checks."""

    def __init__(self):
        """Initialize validator."""
        self.validation_cache = {}

    def validate_rendered(
        self,
        stakeholder: str,
        content: str,
        run_id: str = None,
        has_recording: bool = False,
        finding_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Validate rendered report against stakeholder requirements and quality standards.

        Args:
            stakeholder: Stakeholder identifier
            content: Rendered report content (markdown)
            run_id: Optional run ID
            has_recording: Whether screen recording is attached
            finding_data: Optional finding data for enhanced validation

        Returns:
            Validation result with detailed issues and recommendations
        """
        if finding_data is None:
            finding_data = {}

        rules = STAKEHOLDER_RULES.get(stakeholder, {"required_sections": REQUIRED_COMMON})

        # Check required sections
        missing_sections = self._check_required_sections(content, rules.get("required_sections", []))

        # Check content quality
        quality_issues = self._check_content_quality(content, rules)

        # Check metadata presence
        metadata_issues = self._check_metadata(finding_data)

        # Calculate validation score
        all_issues = missing_sections + quality_issues + metadata_issues
        compliance_score = self._calculate_compliance_score(len(all_issues), len(rules.get("required_sections", [])))

        # Warnings vs errors
        errors = [issue for issue in all_issues if issue['level'] == 'error']
        warnings = [issue for issue in all_issues if issue['level'] == 'warning']

        is_valid = not errors and has_recording
        issues = errors + warnings

        # Check for multipliers (reward optimization hints)
        detected_multipliers = self._detect_multipliers(content, finding_data, rules.get("multipliers", []))

        result = {
            "ok": is_valid,
            "stakeholder": stakeholder,
            "run_id": run_id,
            "compliance_score": compliance_score,
            "content_metrics": self._analyze_content(content),
            "issues": issues,
            "errors": errors,
            "warnings": warnings,
            "missing_sections": missing_sections,
            "has_recording": bool(has_recording),
            "detected_multipliers": detected_multipliers,
            "recommendations": self._generate_recommendations(issues, detected_multipliers),
        }

        return result

    def _check_required_sections(self, content: str, required_sections: List[str]) -> List[Dict[str, Any]]:
        """Check for required sections in content."""
        missing = []

        for section in required_sections:
            # Check for markdown headers (## or #)
            patterns = [
                f"^#+\\s*{re.escape(section)}\\b",
                f"\\n#+\\s*{re.escape(section)}\\b",
                f"^##\\s*{re.escape(section)}",
                f"\\n##\\s*{re.escape(section)}",
            ]

            found = False
            for pattern in patterns:
                if re.search(pattern, content, re.MULTILINE | re.IGNORECASE):
                    found = True
                    break

            if not found:
                missing.append({
                    'section': section,
                    'level': 'error',
                    'message': f"Missing required section: {section}"
                })

        return missing

    def _check_content_quality(self, content: str, rules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check content quality metrics."""
        issues = []

        # Extract section contents
        summary = self._extract_section(content, "Summary")
        impact = self._extract_section(content, "Impact")
        repro = self._extract_section(content, "Steps to Reproduce")

        # Check summary length
        min_summary = rules.get("min_summary_words", 50)
        if summary and len(summary.split()) < min_summary:
            issues.append({
                'section': 'Summary',
                'level': 'warning',
                'message': f"Summary is too brief ({len(summary.split())} words, minimum {min_summary} recommended)"
            })

        # Check impact length
        min_impact = rules.get("min_impact_words", 75)
        if impact and len(impact.split()) < min_impact:
            issues.append({
                'section': 'Impact',
                'level': 'warning',
                'message': f"Impact description is too brief ({len(impact.split())} words, minimum {min_impact} recommended)"
            })

        # Check repro step count
        min_steps = rules.get("min_repro_steps", 2)
        step_count = len(re.findall(r'^\s*\d+\.\s', repro, re.MULTILINE)) if repro else 0
        if step_count < min_steps:
            issues.append({
                'section': 'Steps to Reproduce',
                'level': 'warning',
                'message': f"Only {step_count} reproduction steps found, minimum {min_steps} recommended"
            })

        # Check for evidence quality
        if "code" in content.lower() or "screenshot" in content.lower():
            pass  # Good sign of evidence
        else:
            issues.append({
                'section': 'Evidence',
                'level': 'warning',
                'message': "No code examples or screenshots mentioned - consider adding visual evidence"
            })

        # Check for severity/CVSS formatting
        if not re.search(r'(CVSS|severity|severe|critical|high|medium|low)', content, re.IGNORECASE):
            issues.append({
                'section': 'Metadata',
                'level': 'warning',
                'message': "Severity level not explicitly stated"
            })

        # Check for CWE/CVE references
        if not re.search(r'(CWE-\d+|CVE-\d{4}-\d{4,})', content, re.IGNORECASE):
            issues.append({
                'section': 'Metadata',
                'level': 'info',
                'message': "No CWE or CVE reference found (optional but recommended)"
            })

        return issues

    def _check_metadata(self, finding_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for required metadata in finding data."""
        issues = []

        required_fields = ['severity', 'impact', 'scope']
        for field in required_fields:
            if not finding_data.get(field):
                issues.append({
                    'field': field,
                    'level': 'warning',
                    'message': f"Missing metadata: {field}"
                })

        return issues

    def _extract_section(self, content: str, section_name: str) -> str:
        """Extract content of a specific section."""
        pattern = f"^#+\\s*{re.escape(section_name)}\\b(.*?)(?=^#+|\\Z)"
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    def _analyze_content(self, content: str) -> Dict[str, Any]:
        """Analyze content metrics."""
        lines = content.split('\n')
        words = content.split()
        code_blocks = len(re.findall(r'```', content))
        images = len(re.findall(r'!\[.*?\]\(.*?\)', content))
        links = len(re.findall(r'\[.*?\]\(.*?\)', content))
        bold_text = len(re.findall(r'\*\*.*?\*\*', content))

        return {
            'total_lines': len(lines),
            'total_words': len(words),
            'average_line_length': sum(len(line) for line in lines) // len(lines) if lines else 0,
            'code_blocks': code_blocks // 2,  # Divide by 2 because opening and closing ```
            'images': images,
            'links': links,
            'bold_sections': bold_text,
        }

    def _calculate_compliance_score(self, issue_count: int, section_count: int) -> float:
        """Calculate compliance score 0-100."""
        base_score = 100
        error_penalty = 15
        warning_penalty = 5

        # This would need to separate errors and warnings
        # For now, simple calculation
        score = max(0, base_score - (issue_count * 5))
        return round(score, 1)

    def _detect_multipliers(
        self,
        content: str,
        finding_data: Dict[str, Any],
        potential_multipliers: List[str]
    ) -> List[str]:
        """Detect reward multipliers (hints for optimization)."""
        detected = []

        # Check for common multiplier indicators
        multiplier_patterns = {
            "deterministic repro": r"(always|consistently|deterministic|every time)",
            "scope explicitly cited": r"(only.*affected|limited to|restricted to)",
            "minimal data exposure": r"(does not|no.*exposure|limited.*data)",
            "no service degradation": r"(no.*impact|no.*outage|non.*breaking)",
            "CWE referenced": r"CWE-\d+",
            "CVSS provided": r"CVSS.*[0-9.]+",
            "PoC code included": r"```.*?```",
            "attack narrative clarity": r"(attack|exploit|chain.*of)",
            "business impact clear": r"(financial|revenue|customer|user)",
            "version info clear": r"(version|release|branch)",
            "platform specific": r"(Windows|Linux|macOS|iOS|Android)",
        }

        for multiplier, pattern in multiplier_patterns.items():
            if multiplier in potential_multipliers:
                if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                    detected.append(multiplier)

        return detected

    def _generate_recommendations(
        self,
        issues: List[Dict[str, Any]],
        multipliers: List[str]
    ) -> List[str]:
        """Generate recommendations based on issues and detected multipliers."""
        recommendations = []

        if issues:
            recommendations.append("Fix all errors before submission")

        for issue in issues:
            if issue['level'] == 'warning':
                recommendations.append(f"Consider: {issue['message']}")

        if not multipliers:
            recommendations.append("Consider adding multiplier indicators (e.g., CWE references, CVSS scores, PoC code)")

        if len(multipliers) < 3:
            recommendations.append(f"Currently detected {len(multipliers)} multipliers. Try to maximize to increase reward potential")

        return recommendations


def validate_rendered(
    stakeholder: str,
    content: str,
    run_id: str = None,
    has_recording: bool = False,
    finding_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Convenience function for report validation."""
    validator = ReportValidator()
    return validator.validate_rendered(stakeholder, content, run_id, has_recording, finding_data)
