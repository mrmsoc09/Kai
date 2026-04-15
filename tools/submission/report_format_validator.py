from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.IGNORECASE)


@dataclass(slots=True)
class FormatValidationResult:
    format: str
    passed: bool
    requirements_met: dict[str, bool]
    violations: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": self.format,
            "passed": self.passed,
            "requirements_met": self.requirements_met,
            "violations": self.violations,
        }


class ReportFormatValidator:
    """Platform-specific report format validation for bug bounty submissions."""

    @staticmethod
    def _text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def assess_clarity(text: str) -> bool:
        value = text.strip()
        if len(value) < 30:
            return False
        vague = ["stuff", "maybe", "kind of", "etc", "something"]
        return not any(v in value.lower() for v in vague)

    @staticmethod
    def contains_cve_reference(text: str) -> bool:
        return bool(CVE_RE.search(text))

    @staticmethod
    def contains_business_context(text: str) -> bool:
        keys = ["business", "customer", "account", "data", "financial", "impact", "risk"]
        blob = text.lower()
        return sum(1 for key in keys if key in blob) >= 2

    @staticmethod
    def contains_specific_steps(text: str) -> bool:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 3 and any(line[:2].isdigit() and line[1] in {".", ")"} for line in lines):
            return True
        action_words = ["send", "request", "observe", "verify", "compare", "open", "submit"]
        blob = text.lower()
        return sum(1 for word in action_words if word in blob) >= 2

    @staticmethod
    def contains_exaggeration(text: str) -> bool:
        markers = ["guaranteed compromise", "total pwn", "certainly critical", "instant takeover"]
        blob = text.lower()
        return any(m in blob for m in markers)

    @staticmethod
    def contains_vuln_type(text: str) -> bool:
        keys = ["xss", "sql", "idor", "ssrf", "csrf", "authentication", "misconfiguration", "injection"]
        blob = text.lower()
        return any(k in blob for k in keys)

    @staticmethod
    def _violation_list(requirements: dict[str, bool]) -> list[str]:
        return [name for name, ok in requirements.items() if not ok]

    def validate_h1_format(self, report: dict[str, Any]) -> dict[str, Any]:
        title = self._text(report.get("title"))
        description = self._text(report.get("description"))
        poc_steps = report.get("poc_steps") or report.get("reproduction_steps") or []
        if isinstance(poc_steps, str):
            poc_text = poc_steps
            poc_count = len([ln for ln in poc_steps.splitlines() if ln.strip()])
        else:
            poc_count = len(poc_steps)
            poc_text = "\n".join(str(x) for x in poc_steps)
        impact = self._text(report.get("impact"))
        remediation = self._text(report.get("remediation"))

        req = {
            "title.present": bool(title),
            "title.min_length": len(title) >= 10,
            "title.max_length": len(title) <= 200,
            "description.present": bool(description),
            "description.min_length": len(description) >= 100,
            "description.clarity": self.assess_clarity(description),
            "proof_of_concept.present": poc_count >= 3,
            "proof_of_concept.clarity": self.assess_clarity(poc_text),
            "impact.present": bool(impact),
            "impact.min_length": len(impact) >= 50,
            "impact.includes_business_impact": self.contains_business_context(impact),
            "remediation.present": bool(remediation),
            "remediation.min_length": len(remediation) >= 50,
            "remediation.includes_specific_steps": self.contains_specific_steps(remediation),
            "reference.cve_or_cwe": bool(self.contains_cve_reference(description) or self.contains_vuln_type(description)),
        }

        out = FormatValidationResult(
            format="HackerOne",
            passed=all(req.values()),
            requirements_met=req,
            violations=self._violation_list(req),
        )
        return out.as_dict()

    def validate_intigriti_format(self, report: dict[str, Any]) -> dict[str, Any]:
        title = self._text(report.get("title"))
        description = self._text(report.get("description"))
        poc_steps = report.get("poc_steps") or report.get("reproduction_steps") or []
        if isinstance(poc_steps, str):
            poc_text = poc_steps
            poc_count = len([ln for ln in poc_steps.splitlines() if ln.strip()])
        else:
            poc_count = len(poc_steps)
            poc_text = "\n".join(str(x) for x in poc_steps)
        impact = self._text(report.get("impact"))
        screen_recording = self._text(report.get("screen_recording"))

        req = {
            "title.present": bool(title),
            "title.min_length": len(title) >= 15,
            "title.no_exaggeration": not self.contains_exaggeration(title),
            "description.present": bool(description),
            "description.includes_vulnerability_type": self.contains_vuln_type(description),
            "steps_to_reproduce.present": poc_count >= 4,
            "steps_to_reproduce.clarity": self.assess_clarity(poc_text),
            "steps_to_reproduce.screen_recording_included": bool(screen_recording),
            "impact.present": bool(impact),
            "impact.realistic_assessment": not self.contains_exaggeration(impact),
            "impact.includes_business_context": self.contains_business_context(impact),
        }

        out = FormatValidationResult(
            format="Intigriti",
            passed=all(req.values()),
            requirements_met=req,
            violations=self._violation_list(req),
        )
        return out.as_dict()

    def validate_direct_program_format(self, report: dict[str, Any]) -> dict[str, Any]:
        title = self._text(report.get("title"))
        description = self._text(report.get("description"))
        impact = self._text(report.get("impact"))
        remediation = self._text(report.get("remediation"))
        poc_steps = report.get("poc_steps") or report.get("reproduction_steps") or []
        poc_text = "\n".join(str(x) for x in poc_steps) if isinstance(poc_steps, list) else str(poc_steps)

        req = {
            "title.present": bool(title),
            "description.present": bool(description),
            "description.min_length": len(description) >= 100,
            "proof_of_concept.present": len([ln for ln in poc_text.splitlines() if ln.strip()]) >= 3,
            "proof_of_concept.clear": self.assess_clarity(poc_text),
            "impact.present": bool(impact),
            "impact.includes_business_context": self.contains_business_context(impact),
            "remediation.present": bool(remediation),
            "remediation.actionable": self.contains_specific_steps(remediation),
            "scope_confirmation": bool(report.get("in_scope_confirmed", False)),
        }

        out = FormatValidationResult(
            format="DirectProgram",
            passed=all(req.values()),
            requirements_met=req,
            violations=self._violation_list(req),
        )
        return out.as_dict()

    def validate_report_for_platform(self, platform: str, report: dict[str, Any]) -> dict[str, Any]:
        target = self._text(platform).lower()
        if target in {"hackerone", "h1"}:
            return self.validate_h1_format(report)
        if target in {"intigriti", "inti"}:
            return self.validate_intigriti_format(report)
        return self.validate_direct_program_format(report)

    def validate_report_format(self, report: dict[str, Any]) -> dict[str, Any]:
        platform = self._text(report.get("platform") or report.get("program") or "direct")
        return self.validate_report_for_platform(platform, report)


__all__ = ["ReportFormatValidator", "FormatValidationResult"]
