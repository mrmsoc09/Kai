from __future__ import annotations

from .base import SubmissionExportContext, SubmissionProviderAdapter


class BugcrowdSubmissionAdapter(SubmissionProviderAdapter):
    provider = "bugcrowd"
    required_fields = (
        "title",
        "summary",
        "target",
        "vulnerability_type",
        "steps_to_reproduce",
        "impact",
    )

    def build_payload(self, context: SubmissionExportContext) -> dict:
        core = self._core_context(context)
        return {
            "provider": self.provider,
            "title": core["title"],
            "summary": core["summary"],
            "priority": core["severity"],
            "target": core["target"],
            "vulnerability_type": core["vulnerability_type"] or core["cwe"],
            "steps_to_reproduce": core["reproduction_steps"],
            "impact": core["impact"],
            "evidence": core["evidence_refs"],
            "artifacts": core["artifact_refs"],
            "observations": core["observation_refs"],
            "taxonomy": {"cwe": core["cwe"], "cve": core["cve"]},
            "kai_context": {
                "campaign_context": core["campaign_context"],
                "provenance": core["provenance"],
            },
        }

    def provider_warnings(self, context: SubmissionExportContext, payload: dict) -> list[str]:
        warnings: list[str] = []
        if not payload.get("vulnerability_type"):
            warnings.append("bugcrowd.vulnerability_type_missing")
        if any(item.get("synthetic") for item in payload.get("evidence", [])):
            warnings.append("bugcrowd.synthetic_evidence_present")
        return warnings
