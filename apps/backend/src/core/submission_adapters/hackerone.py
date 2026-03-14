from __future__ import annotations

from .base import SubmissionExportContext, SubmissionProviderAdapter


class HackerOneSubmissionAdapter(SubmissionProviderAdapter):
    provider = "hackerone"
    required_fields = (
        "title",
        "severity_rating",
        "affected_assets",
        "vulnerability_information",
        "impact",
    )

    def build_payload(self, context: SubmissionExportContext) -> dict:
        core = self._core_context(context)
        weakness_name = core["cwe"] or core["vulnerability_type"]
        return {
            "provider": self.provider,
            "title": core["title"],
            "severity_rating": core["severity"],
            "weakness": {"name": weakness_name} if weakness_name else {},
            "affected_assets": [core["target"]] if core["target"] else [],
            "vulnerability_information": core["summary"],
            "impact": core["impact"],
            "reproduction_steps": core["reproduction_steps"],
            "references": [uri["uri"] for uri in core["evidence_refs"] if uri.get("uri")],
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
        if not payload.get("weakness", {}).get("name"):
            warnings.append("hackerone.weakness.name_missing")
        if not payload.get("reproduction_steps"):
            warnings.append("hackerone.reproduction_steps_missing")
        return warnings
