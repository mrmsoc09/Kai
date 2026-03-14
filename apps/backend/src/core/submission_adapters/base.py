from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SubmissionExportContext:
    provider: str
    finding: Any
    submission_draft: Any
    package_json: dict[str, Any]
    evidence_rows: list[Any]
    artifacts: list[Any]
    observations: list[Any]
    actor: str | None = None


@dataclass
class ProviderValidationResult:
    state: str
    ready: bool
    missing_fields: list[str]
    warnings: list[str]


@dataclass
class ProviderPayloadResult:
    provider: str
    payload: dict[str, Any]
    validation: ProviderValidationResult


class SubmissionProviderAdapter(ABC):
    provider: str
    required_fields: tuple[str, ...] = ()

    @abstractmethod
    def build_payload(self, context: SubmissionExportContext) -> dict[str, Any]:
        raise NotImplementedError

    def provider_warnings(
        self,
        context: SubmissionExportContext,
        payload: dict[str, Any],
    ) -> list[str]:
        return []

    def preview(
        self,
        context: SubmissionExportContext,
        *,
        core_missing_fields: list[str] | None = None,
        core_warnings: list[str] | None = None,
    ) -> ProviderPayloadResult:
        payload = self.build_payload(context)
        validation = self.validate_payload(
            payload,
            core_missing_fields=core_missing_fields,
            core_warnings=(core_warnings or []) + self.provider_warnings(context, payload),
        )
        return ProviderPayloadResult(
            provider=self.provider,
            payload=payload,
            validation=validation,
        )

    def validate_payload(
        self,
        payload: dict[str, Any],
        *,
        core_missing_fields: list[str] | None = None,
        core_warnings: list[str] | None = None,
    ) -> ProviderValidationResult:
        missing = list(core_missing_fields or [])
        warnings = list(core_warnings or [])
        for path in self.required_fields:
            value = self._value_at_path(payload, path)
            if value in (None, "", []):
                missing.append(path)
        missing = self._dedupe(missing)
        warnings = self._dedupe(warnings)
        ready = len(missing) == 0
        return ProviderValidationResult(
            state="ready" if ready else "not_ready",
            ready=ready,
            missing_fields=missing,
            warnings=warnings,
        )

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            ordered.append(item)
        return ordered

    @staticmethod
    def _value_at_path(payload: dict[str, Any], path: str) -> Any:
        current: Any = payload
        for segment in path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(segment)
        return current

    @staticmethod
    def _scope_json(context: SubmissionExportContext) -> dict[str, Any]:
        scope_json = getattr(context.finding, "scope_json", {})
        return scope_json if isinstance(scope_json, dict) else {}

    def _core_context(self, context: SubmissionExportContext) -> dict[str, Any]:
        finding_json = (
            context.package_json.get("finding") if isinstance(context.package_json, dict) else {}
        )
        finding_json = finding_json if isinstance(finding_json, dict) else {}
        campaign_json = (
            context.package_json.get("campaign_context")
            if isinstance(context.package_json, dict)
            else {}
        )
        campaign_json = campaign_json if isinstance(campaign_json, dict) else {}
        scope_json = self._scope_json(context)

        observations_json = [
            item
            for item in (
                context.package_json.get("observations", [])
                if isinstance(context.package_json, dict)
                else []
            )
            if isinstance(item, dict)
        ]

        reproduction_notes = context.package_json.get("reproduction_notes", [])
        if not isinstance(reproduction_notes, list):
            reproduction_notes = []
        reproduction_steps = [str(note).strip() for note in reproduction_notes if str(note).strip()]
        if not reproduction_steps:
            for observation in observations_json:
                category = str(observation.get("category") or "").upper()
                summary = str(observation.get("summary") or "").strip()
                if summary and category == "VALIDATION":
                    reproduction_steps.append(summary)

        summary = (
            str(finding_json.get("description") or "").strip()
            or str(getattr(context.finding, "description", "") or "").strip()
            or (reproduction_steps[0] if reproduction_steps else "")
        )
        impact = (
            str(scope_json.get("impact") or "").strip()
            or str(finding_json.get("impact") or "").strip()
            or summary
        )
        target = (
            str(finding_json.get("asset") or "").strip()
            or str(getattr(context.finding, "asset", "") or "").strip()
        )
        title = (
            str(finding_json.get("title") or "").strip()
            or str(getattr(context.finding, "title", "") or "").strip()
        )
        severity = str(finding_json.get("severity") or "").strip() or (
            getattr(getattr(context.finding, "severity", None), "value", None)
            or str(getattr(context.finding, "severity", "") or "").strip()
        )
        taxonomy = scope_json.get("taxonomy")
        taxonomy_type = ""
        if isinstance(taxonomy, str):
            taxonomy_type = taxonomy.strip()
        elif isinstance(taxonomy, dict):
            taxonomy_type = str(
                taxonomy.get("type") or taxonomy.get("name") or taxonomy.get("category") or ""
            ).strip()
        vulnerability_type = (
            str(scope_json.get("vulnerability_type") or "").strip() or taxonomy_type
        )
        cwe = str(scope_json.get("cwe") or "").strip()
        cve = str(scope_json.get("cve") or "").strip()

        evidence_refs = [
            {
                "id": str(getattr(item, "id", "")),
                "kind": getattr(item, "kind", None),
                "uri": getattr(item, "uri", None),
                "synthetic": bool(
                    (getattr(item, "meta", {}) or {}).get("synthetic")
                    if isinstance(getattr(item, "meta", None), dict)
                    else False
                ),
            }
            for item in context.evidence_rows
        ]
        artifact_refs = [
            {
                "id": str(getattr(item, "id", "")),
                "uri": getattr(item, "uri", None),
                "mime_type": getattr(item, "mime_type", None),
                "content_hash": getattr(item, "content_hash", None),
                "synthetic": bool(
                    str(getattr(item, "uri", "")).startswith("inline://")
                    or (
                        isinstance(getattr(item, "details_json", None), dict)
                        and (
                            getattr(item, "details_json", {}).get("synthetic")
                            or getattr(item, "details_json", {}).get("placeholder")
                            or getattr(item, "details_json", {}).get("inline")
                        )
                    )
                ),
            }
            for item in context.artifacts
        ]
        observation_refs = [
            {
                "id": str(getattr(item, "id", "")),
                "category": getattr(item, "category", None),
                "title": getattr(item, "title", None),
                "summary": getattr(item, "summary", None),
            }
            for item in context.observations
        ]

        draft_campaign_id = getattr(context.submission_draft, "campaign_id", None)
        draft_branch_id = getattr(context.submission_draft, "branch_id", None)
        return {
            "title": title,
            "severity": severity,
            "target": target,
            "summary": summary,
            "impact": impact,
            "reproduction_steps": reproduction_steps,
            "vulnerability_type": vulnerability_type,
            "cwe": cwe,
            "cve": cve,
            "campaign_context": campaign_json,
            "evidence_refs": evidence_refs,
            "artifact_refs": artifact_refs,
            "observation_refs": observation_refs,
            "provenance": {
                "finding_id": str(getattr(context.finding, "id", "")),
                "submission_draft_id": str(getattr(context.submission_draft, "id", "")),
                "campaign_id": str(draft_campaign_id) if draft_campaign_id else None,
                "branch_id": str(draft_branch_id) if draft_branch_id else None,
                "source": "kai.canonical_submission_package",
            },
        }
