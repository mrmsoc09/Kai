from __future__ import annotations

from .base import SubmissionExportContext, SubmissionProviderAdapter


class IntigritiSubmissionAdapter(SubmissionProviderAdapter):
    provider = "intigriti"
    required_fields = (
        "title",
        "summary",
        "severity",
        "asset",
        "reproduction",
        "impact",
    )

    def build_payload(self, context: SubmissionExportContext) -> dict:
        core = self._core_context(context)
        return {
            "provider": self.provider,
            "title": core["title"],
            "summary": core["summary"],
            "severity": core["severity"],
            "asset": core["target"],
            "vulnerability_type": core["vulnerability_type"] or core["cwe"],
            "reproduction": core["reproduction_steps"],
            "impact": core["impact"],
            "supporting_materials": {
                "evidence": core["evidence_refs"],
                "artifacts": core["artifact_refs"],
            },
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
            warnings.append("intigriti.vulnerability_type_missing")
        if not payload.get("reproduction"):
            warnings.append("intigriti.reproduction_missing")
        return warnings
