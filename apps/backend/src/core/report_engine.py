from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .evidence_qualification_engine import qualify_evidence
from .impact_validation_engine import resolve_submission_candidate_decision, validate_impact
from .novelty_dedupe_engine import evaluate_novelty_dedupe
from .vulnerability_intelligence_engine import enrich_finding_with_intelligence
from .pdf_generator import markdown_to_html, generate_pdf_from_markdown


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_vuln_type(value: Any) -> str:
    return _normalize_text(value).lower().replace(" ", "_") or "unknown"


def _normalize_target(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or parsed.path or raw
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip(".")


def _normalize_severity(value: Any, confidence: float = 0.0) -> str:
    raw = _normalize_text(value).lower()
    if raw in {"critical", "high", "medium", "low"}:
        return raw
    if raw:
        try:
            cvss = float(raw)
            if cvss >= 9.0:
                return "critical"
            if cvss >= 7.0:
                return "high"
            if cvss >= 4.0:
                return "medium"
            return "low"
        except ValueError:
            pass
    if confidence >= 0.9:
        return "critical"
    if confidence >= 0.75:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _normalize_references(finding: dict[str, Any]) -> list[str]:
    refs = finding.get("references") or finding.get("reference_links") or []
    if isinstance(refs, list):
        return [_normalize_text(value) for value in refs if _normalize_text(value)]
    if isinstance(refs, str):
        return [refs.strip()] if refs.strip() else []
    return []


def _report_state_path() -> Path:
    configured = os.getenv("K1_REPORT_ENGINE_STATE_PATH")
    if configured:
        return Path(configured).resolve()
    return Path("artifacts/reports/report_state.json").resolve()


def _report_artifacts_dir() -> Path:
    configured = os.getenv("K1_REPORT_ENGINE_ARTIFACT_DIR")
    if configured:
        return Path(configured).resolve()
    return Path("artifacts/reports/generated").resolve()


def _extract_validation_evidence(finding: dict[str, Any]) -> list[str]:
    rows = finding.get("validation_evidence") or finding.get("evidence") or []
    if isinstance(rows, list):
        out: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                detail = _normalize_text(row.get("detail") or row.get("message") or row.get("check"))
                if detail:
                    out.append(detail)
            else:
                text = _normalize_text(row)
                if text:
                    out.append(text)
        return out
    if isinstance(rows, str):
        text = rows.strip()
        return [text] if text else []
    return []


def _extract_reproduction_steps(finding: dict[str, Any], target: str) -> list[str]:
    rows = finding.get("reproduction_steps") or finding.get("steps_to_reproduce") or []
    if isinstance(rows, list):
        out: list[str] = []
        for row in rows:
            if isinstance(row, dict):
                text = _normalize_text(row.get("description") or row.get("step") or row.get("detail"))
            else:
                text = _normalize_text(row)
            if text:
                out.append(text)
        if out:
            return out

    endpoint = _normalize_text(finding.get("endpoint") or finding.get("path") or finding.get("url"))
    parameter = _normalize_text(finding.get("parameter") or finding.get("parameter_name") or finding.get("input_vector"))
    payload = _normalize_text(finding.get("payload") or finding.get("key_payload_signature") or finding.get("probe_payload"))
    steps = [
        f"Open target `{endpoint or target}`.",
        f"Send crafted input through `{parameter}`." if parameter else "Send crafted input to the vulnerable interface.",
        (
            f"Use payload signature `{payload}` and capture the server response."
            if payload
            else "Capture the server response and evidence of the vulnerability condition."
        ),
        "Repeat the request to confirm deterministic reproduction.",
    ]
    return steps


def _extract_http_samples(
    finding: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    requests = finding.get("http_requests") or finding.get("requests") or []
    responses = finding.get("http_responses") or finding.get("responses") or []

    normalized_requests: list[str] = []
    normalized_responses: list[str] = []

    if isinstance(requests, list):
        normalized_requests.extend([_normalize_text(row) for row in requests if _normalize_text(row)])
    elif isinstance(requests, str) and requests.strip():
        normalized_requests.append(requests.strip())

    if isinstance(responses, list):
        normalized_responses.extend([_normalize_text(row) for row in responses if _normalize_text(row)])
    elif isinstance(responses, str) and responses.strip():
        normalized_responses.append(responses.strip())

    for artifact in artifacts:
        if not isinstance(artifact, dict):
            continue
        req = _normalize_text(artifact.get("http_request") or artifact.get("request"))
        resp = _normalize_text(artifact.get("http_response") or artifact.get("response"))
        if req:
            normalized_requests.append(req)
        if resp:
            normalized_responses.append(resp)

    return normalized_requests[:10], normalized_responses[:10]


def _extract_payload_signature(finding: dict[str, Any], http_requests: list[str]) -> str:
    explicit = _normalize_text(
        finding.get("key_payload_signature")
        or finding.get("payload")
        or finding.get("probe_payload")
        or finding.get("input_signature")
    )
    if explicit:
        return explicit[:200]

    if http_requests:
        sample = http_requests[0]
        first_line = sample.splitlines()[0] if sample.splitlines() else sample
        return first_line[:200]

    parameter = _normalize_text(finding.get("parameter") or finding.get("parameter_name"))
    return parameter[:200]


def _default_remediation(vuln_type: str) -> str:
    mapping = {
        "xss": "Apply strict output encoding, sanitize untrusted input, and enforce a restrictive CSP.",
        "sqli": "Use parameterized queries consistently and remove dynamic SQL string interpolation.",
        "ssrf": "Harden outbound request controls with explicit allowlists and metadata endpoint blocks.",
        "idor": "Enforce object-level authorization checks on every resource access path.",
        "auth_bypass": "Require centralized authentication and authorization checks before sensitive actions.",
    }
    return mapping.get(vuln_type, "Apply least-privilege controls and deterministic input validation on the vulnerable path.")


def _default_impact(vuln_type: str, severity: str, target: str) -> str:
    return (
        f"The {vuln_type} condition on `{target}` is reproducible and supports a {severity} severity outcome. "
        "Successful exploitation can increase attacker control and business risk."
    )


@dataclass
class Report:
    report_id: str
    title: str
    vulnerability_type: str
    severity: str
    target: str
    summary: str
    reproduction_steps: list[str]
    http_requests: list[str]
    http_responses: list[str]
    exploit_chain: dict[str, Any] | None
    impact: str
    remediation: str
    references: list[str]
    validation_evidence: list[str]
    confidence_score: float
    quality_score: float
    duplicate_hash: str
    evidence_qualification: dict[str, Any] = field(default_factory=dict)
    impact_validation: dict[str, Any] = field(default_factory=dict)
    vulnerability_intelligence: dict[str, Any] = field(default_factory=dict)
    novelty_dedupe: dict[str, Any] = field(default_factory=dict)
    submission_decision: dict[str, Any] = field(default_factory=dict)
    submission_candidate: bool = False
    rejection_reason: str | None = None
    tenant_id: str | None = None
    mission_id: str | None = None
    opportunity_id: str | None = None
    finding_id: str | None = None
    artifact_uri: str | None = None
    generated_by: str | None = None
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    rendered_markdown: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["confidence_score"] = round(_clamp(self.confidence_score), 4)
        payload["quality_score"] = round(_clamp(self.quality_score), 4)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "Report":
        return cls(
            report_id=_normalize_text(payload.get("report_id")),
            title=_normalize_text(payload.get("title")),
            vulnerability_type=_normalize_text(payload.get("vulnerability_type")),
            severity=_normalize_text(payload.get("severity")),
            target=_normalize_text(payload.get("target")),
            summary=_normalize_text(payload.get("summary")),
            reproduction_steps=[_normalize_text(row) for row in payload.get("reproduction_steps", []) if _normalize_text(row)],
            http_requests=[_normalize_text(row) for row in payload.get("http_requests", []) if _normalize_text(row)],
            http_responses=[_normalize_text(row) for row in payload.get("http_responses", []) if _normalize_text(row)],
            exploit_chain=payload.get("exploit_chain") if isinstance(payload.get("exploit_chain"), dict) else None,
            impact=_normalize_text(payload.get("impact")),
            remediation=_normalize_text(payload.get("remediation")),
            references=[_normalize_text(row) for row in payload.get("references", []) if _normalize_text(row)],
            validation_evidence=[_normalize_text(row) for row in payload.get("validation_evidence", []) if _normalize_text(row)],
            confidence_score=_clamp(_safe_float(payload.get("confidence_score"), 0.0)),
            quality_score=_clamp(_safe_float(payload.get("quality_score"), 0.0)),
            duplicate_hash=_normalize_text(payload.get("duplicate_hash")),
            evidence_qualification=(
                payload.get("evidence_qualification")
                if isinstance(payload.get("evidence_qualification"), dict)
                else {}
            ),
            impact_validation=(
                payload.get("impact_validation")
                if isinstance(payload.get("impact_validation"), dict)
                else {}
            ),
            vulnerability_intelligence=(
                payload.get("vulnerability_intelligence")
                if isinstance(payload.get("vulnerability_intelligence"), dict)
                else {}
            ),
            novelty_dedupe=(
                payload.get("novelty_dedupe")
                if isinstance(payload.get("novelty_dedupe"), dict)
                else {}
            ),
            submission_decision=(
                payload.get("submission_decision")
                if isinstance(payload.get("submission_decision"), dict)
                else {}
            ),
            submission_candidate=bool(payload.get("submission_candidate", False)),
            rejection_reason=_normalize_text(payload.get("rejection_reason")) or None,
            tenant_id=payload.get("tenant_id"),
            mission_id=payload.get("mission_id"),
            opportunity_id=payload.get("opportunity_id"),
            finding_id=payload.get("finding_id"),
            artifact_uri=payload.get("artifact_uri"),
            generated_by=payload.get("generated_by"),
            created_at=_normalize_text(payload.get("created_at")) or _utcnow_iso(),
            updated_at=_normalize_text(payload.get("updated_at")) or _utcnow_iso(),
            rendered_markdown=_normalize_text(payload.get("rendered_markdown")),
        )


class ReportEngine:
    def __init__(self) -> None:
        self._state_path = _report_state_path()
        self._artifact_dir = _report_artifacts_dir()
        self._lock = threading.Lock()

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {"reports": {}, "duplicate_index": {}, "mission_index": {}, "updated_at": _utcnow_iso()}
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid_report_state")
            payload.setdefault("reports", {})
            payload.setdefault("duplicate_index", {})
            payload.setdefault("mission_index", {})
            payload.setdefault("updated_at", _utcnow_iso())
            return payload
        except Exception:
            return {"reports": {}, "duplicate_index": {}, "mission_index": {}, "updated_at": _utcnow_iso()}

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        state["updated_at"] = _utcnow_iso()
        self._state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def _report_id(self, duplicate_hash: str, finding_id: str, target: str) -> str:
        raw = f"{duplicate_hash}|{finding_id}|{target}|{time.time_ns()}"
        digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:16]
        return f"report_{digest}"

    def _duplicate_hash(self, finding: dict[str, Any], payload_signature: str) -> str:
        endpoint = _normalize_text(finding.get("endpoint") or finding.get("path") or finding.get("url") or finding.get("target"))
        target = _normalize_target(finding.get("target") or finding.get("domain") or finding.get("url"))
        vuln_type = _normalize_vuln_type(finding.get("vuln_type") or finding.get("type"))
        key = f"{endpoint.lower()}|{target}|{vuln_type}|{payload_signature.lower()}"
        return hashlib.sha256(key.encode("utf-8", errors="replace")).hexdigest()

    def _quality_score(
        self,
        *,
        report: Report,
        duplicate_likelihood: float,
    ) -> float:
        completeness_checks = [
            bool(report.title),
            bool(report.summary),
            bool(report.reproduction_steps),
            bool(report.http_requests),
            bool(report.http_responses),
            bool(report.impact),
            bool(report.remediation),
            bool(report.validation_evidence),
            bool(report.target),
            bool(report.vulnerability_type),
        ]
        completeness = sum(1 for row in completeness_checks if row) / len(completeness_checks)

        validation_strength = min(1.0, len(report.validation_evidence) / 4.0)
        chain_bonus = 1.0 if report.exploit_chain else 0.0
        repro_clarity = min(1.0, len(report.reproduction_steps) / 4.0)
        duplicate_component = 1.0 - _clamp(duplicate_likelihood)

        score = (
            0.45 * completeness
            + 0.20 * validation_strength
            + 0.15 * chain_bonus
            + 0.10 * repro_clarity
            + 0.10 * duplicate_component
        )
        evidence_quality = _safe_float(
            report.evidence_qualification.get("evidence_quality_score")
            if isinstance(report.evidence_qualification, dict)
            else 0.0,
            0.0,
        )
        impact_quality = _safe_float(
            report.impact_validation.get("impact_score")
            if isinstance(report.impact_validation, dict)
            else 0.0,
            0.0,
        )
        if evidence_quality > 0:
            score = (score * 0.8) + (_clamp(evidence_quality) * 0.2)
        if impact_quality > 0:
            score = (score * 0.85) + (_clamp(impact_quality) * 0.15)
        intel_dup = _safe_float(
            report.vulnerability_intelligence.get("duplicate_likelihood_score")
            if isinstance(report.vulnerability_intelligence, dict)
            else 0.0,
            0.0,
        )
        intel_novelty = _safe_float(
            report.vulnerability_intelligence.get("novelty_score")
            if isinstance(report.vulnerability_intelligence, dict)
            else 0.0,
            0.0,
        )
        dedupe_novelty = _safe_float(
            report.novelty_dedupe.get("novelty_score")
            if isinstance(report.novelty_dedupe, dict)
            else 0.0,
            0.0,
        )
        dedupe_duplicate = _safe_float(
            report.novelty_dedupe.get("duplicate_likelihood_score")
            if isinstance(report.novelty_dedupe, dict)
            else 0.0,
            0.0,
        )
        if intel_dup > 0 or intel_novelty > 0:
            # Intelligence/dedupe should inform queue ranking, not collapse intrinsic report quality.
            score = (score * 0.9) + (_clamp(intel_novelty) * 0.08) + ((1.0 - _clamp(intel_dup)) * 0.02)
        if dedupe_novelty > 0 or dedupe_duplicate > 0:
            score = (score * 0.92) + (_clamp(dedupe_novelty) * 0.06) + ((1.0 - _clamp(dedupe_duplicate)) * 0.02)
        suppression = _normalize_text(
            report.novelty_dedupe.get("suppression_recommendation")
            if isinstance(report.novelty_dedupe, dict)
            else ""
        )
        if suppression == "suppress_from_default_hil_view":
            score = min(score, 0.62)
        elif suppression == "deprioritize":
            score = min(score, 0.72)
        if not report.submission_candidate:
            # Keep report quality and submission eligibility aligned to avoid HiL queue leakage.
            score = min(score, 0.74)
        return round(_clamp(score), 4)

    def _render_markdown(self, report: Report) -> str:
        lines = [
            f"# {report.title}",
            "",
            f"**Report ID:** `{report.report_id}`",
            f"**Vulnerability Type:** `{report.vulnerability_type}`",
            f"**Severity:** `{report.severity}`",
            f"**Target:** `{report.target}`",
            f"**Confidence:** `{report.confidence_score:.2f}`",
            f"**Quality Score:** `{report.quality_score:.2f}`",
            f"**Submission Candidate:** `{report.submission_candidate}`",
            f"**Rejection Reason:** `{report.rejection_reason or 'n/a'}`",
            "",
            "## Summary",
            report.summary,
            "",
            "## Reproduction Steps",
        ]
        for index, step in enumerate(report.reproduction_steps, start=1):
            lines.append(f"{index}. {step}")

        lines.append("")
        lines.append("## HTTP Requests")
        if report.http_requests:
            for request in report.http_requests:
                lines.append("```http")
                lines.append(request)
                lines.append("```")
        else:
            lines.append("- No request trace captured.")

        lines.append("")
        lines.append("## HTTP Responses")
        if report.http_responses:
            for response in report.http_responses:
                lines.append("```http")
                lines.append(response)
                lines.append("```")
        else:
            lines.append("- No response trace captured.")

        if report.exploit_chain:
            lines.extend(
                [
                    "",
                    "## Exploit Chain",
                    f"- Chain ID: `{_normalize_text(report.exploit_chain.get('chain_id')) or 'n/a'}`",
                    f"- Score: `{_safe_float(report.exploit_chain.get('score'), 0.0):.2f}`",
                    f"- Confidence: `{_safe_float(report.exploit_chain.get('confidence_score'), 0.0):.2f}`",
                    f"- Reasoning: {_normalize_text(report.exploit_chain.get('reasoning_summary')) or 'n/a'}",
                ]
            )

        lines.extend(
            [
                "",
                "## Impact",
                report.impact,
                "",
                "## Impact Validation",
                json.dumps(
                    report.impact_validation if isinstance(report.impact_validation, dict) else {},
                    indent=2,
                    ensure_ascii=False,
                ),
                "",
                "## Vulnerability Intelligence",
                json.dumps(
                    report.vulnerability_intelligence if isinstance(report.vulnerability_intelligence, dict) else {},
                    indent=2,
                    ensure_ascii=False,
                ),
                "",
                "## Novelty + Duplicate Suppression",
                json.dumps(
                    report.novelty_dedupe if isinstance(report.novelty_dedupe, dict) else {},
                    indent=2,
                    ensure_ascii=False,
                ),
                "",
                "## Remediation",
                report.remediation,
                "",
                "## Validation Evidence",
            ]
        )

        if report.validation_evidence:
            lines.extend([f"- {row}" for row in report.validation_evidence])
        else:
            lines.append("- No validation evidence captured.")

        lines.extend(["", "## References"])
        if report.references:
            lines.extend([f"- {row}" for row in report.references])
        else:
            lines.append("- No external references.")
        return "\n".join(lines).strip() + "\n"

    def generate_report(
        self,
        finding: dict[str, Any],
        exploit_chain: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        *,
        tenant_id: str | None = None,
        mission_id: str | None = None,
        opportunity_id: str | None = None,
        generated_by: str | None = None,
    ) -> Report:
        artifacts = artifacts or []
        vuln_type = _normalize_vuln_type(finding.get("vuln_type") or finding.get("type"))
        confidence = _clamp(
            _safe_float(
                finding.get("confidence_score")
                or finding.get("confidence")
                or finding.get("validation_confidence")
                or 0.5
            )
        )
        severity = _normalize_severity(finding.get("severity") or finding.get("cvss"), confidence=confidence)
        target = _normalize_target(
            finding.get("target")
            or finding.get("domain")
            or finding.get("host")
            or finding.get("url")
            or finding.get("endpoint")
        ) or "unknown-target"
        finding_id = _normalize_text(finding.get("finding_id") or finding.get("id")) or None
        summary = _normalize_text(finding.get("summary")) or (
            f"Validated {vuln_type} condition identified on `{target}` with deterministic signal strength."
        )
        impact = _normalize_text(finding.get("impact")) or _default_impact(vuln_type, severity, target)
        remediation = _normalize_text(finding.get("remediation")) or _default_remediation(vuln_type)

        reproduction_steps = _extract_reproduction_steps(finding, target)
        http_requests, http_responses = _extract_http_samples(finding, artifacts)
        validation_evidence = _extract_validation_evidence(finding)
        references = _normalize_references(finding)
        payload_signature = _extract_payload_signature(finding, http_requests)
        duplicate_hash = self._duplicate_hash(finding, payload_signature)
        report_id = self._report_id(duplicate_hash, finding_id or "", target)
        title = _normalize_text(finding.get("title")) or f"{vuln_type.upper()} on {target}"
        qualification = qualify_evidence(
            finding,
            exploit_results=(
                finding.get("exploit_results")
                if isinstance(finding.get("exploit_results"), list)
                else None
            ),
            request_response_signatures=[
                f"{request}::{response}"
                for request, response in zip(http_requests[:3], http_responses[:3])
            ],
            scope_metadata=(
                finding.get("scope_metadata")
                if isinstance(finding.get("scope_metadata"), dict)
                else {"target": target}
            ),
            mission_id=mission_id,
            stage_id=_normalize_text(finding.get("stage_id") or finding.get("stage") or "report_generation"),
            report_id=report_id,
            persist=True,
            update_duplicate_history=True,
        )
        impact_validation = validate_impact(
            finding,
            qualification=qualification.to_dict(),
            baseline_response=finding.get("baseline_response"),
            exploit_response=finding.get("exploit_response"),
            scope_metadata=(
                finding.get("scope_metadata")
                if isinstance(finding.get("scope_metadata"), dict)
                else {"target": target}
            ),
            mission_id=mission_id,
            stage_id=_normalize_text(finding.get("stage_id") or finding.get("stage") or "impact_validation"),
            report_id=report_id,
            persist=True,
        )
        submission_decision = resolve_submission_candidate_decision(
            evidence_qualification=qualification.to_dict(),
            impact_validation=impact_validation.to_dict(),
        )
        vulnerability_intelligence = enrich_finding_with_intelligence(
            {
                **finding,
                "target": target,
                "vulnerability_type": vuln_type,
                "submission_decision": submission_decision,
                "evidence_qualification": qualification.to_dict(),
                "impact_validation": impact_validation.to_dict(),
                "scope_metadata": (
                    finding.get("scope_metadata")
                    if isinstance(finding.get("scope_metadata"), dict)
                    else {"target": target}
                ),
            },
            mission_id=mission_id,
            stage_id=_normalize_text(finding.get("stage_id") or finding.get("stage") or "vulnerability_intelligence"),
            report_id=report_id,
            persist=True,
            update_history=True,
        ).to_dict()
        novelty_dedupe = evaluate_novelty_dedupe(
            {
                **finding,
                "target": target,
                "vulnerability_type": vuln_type,
                "submission_decision": submission_decision,
            },
            vulnerability_intelligence=vulnerability_intelligence,
            evidence_qualification=qualification.to_dict(),
            impact_validation=impact_validation.to_dict(),
            submission_decision=submission_decision,
            mission_id=mission_id,
            stage_id=_normalize_text(finding.get("stage_id") or finding.get("stage") or "novelty_dedupe"),
            report_id=report_id,
            persist=True,
            update_history=True,
        ).to_dict()
        if not _normalize_text(finding.get("impact")) and isinstance(impact_validation.impact_statement, dict):
            impact = _normalize_text(impact_validation.impact_statement.get("technical_impact")) or impact

        report = Report(
            report_id=report_id,
            title=title,
            vulnerability_type=vuln_type,
            severity=severity,
            target=target,
            summary=summary,
            reproduction_steps=reproduction_steps,
            http_requests=http_requests,
            http_responses=http_responses,
            exploit_chain=exploit_chain if isinstance(exploit_chain, dict) else None,
            impact=impact,
            remediation=remediation,
            references=references,
            validation_evidence=validation_evidence,
            confidence_score=confidence,
            quality_score=0.0,
            duplicate_hash=duplicate_hash,
            evidence_qualification=qualification.to_dict(),
            impact_validation=impact_validation.to_dict(),
            vulnerability_intelligence=vulnerability_intelligence,
            novelty_dedupe=novelty_dedupe,
            submission_decision=submission_decision,
            submission_candidate=bool(submission_decision.get("submission_candidate")),
            rejection_reason=_normalize_text(submission_decision.get("rejection_reason")) or None,
            tenant_id=tenant_id,
            mission_id=mission_id,
            opportunity_id=opportunity_id,
            finding_id=finding_id,
            generated_by=generated_by,
        )
        report.quality_score = self._quality_score(
            report=report,
            duplicate_likelihood=_safe_float(finding.get("duplicate_risk"), 0.0),
        )
        report.rendered_markdown = self._render_markdown(report)
        return report

    def _persist_report_artifacts(self, report: Report) -> str:
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        
        markdown_content = report.rendered_markdown or self._render_markdown(report)
        
        json_path = self._artifact_dir / f"{report.report_id}.json"
        markdown_path = self._artifact_dir / f"{report.report_id}.md"
        html_path = self._artifact_dir / f"{report.report_id}.html"
        pdf_path = self._artifact_dir / f"{report.report_id}.pdf"
        
        json_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        markdown_path.write_text(markdown_content, encoding="utf-8")
        
        try:
            html_content = markdown_to_html(markdown_content)
            html_path.write_text(html_content, encoding="utf-8")
            
            pdf_bytes = generate_pdf_from_markdown(markdown_content)
            pdf_path.write_bytes(pdf_bytes)
        except Exception as e:
            # Non-fatal if HTML/PDF generation fails (e.g. if weasyprint dependencies are missing locally)
            pass
            
        return str(json_path)

    def generate_and_store_report(
        self,
        finding: dict[str, Any],
        exploit_chain: dict[str, Any] | None = None,
        artifacts: list[dict[str, Any]] | None = None,
        *,
        tenant_id: str | None = None,
        mission_id: str | None = None,
        opportunity_id: str | None = None,
        generated_by: str | None = None,
        deduplicate: bool = True,
    ) -> tuple[Report, bool]:
        candidate = self.generate_report(
            finding=finding,
            exploit_chain=exploit_chain,
            artifacts=artifacts,
            tenant_id=tenant_id,
            mission_id=mission_id,
            opportunity_id=opportunity_id,
            generated_by=generated_by,
        )

        with self._lock:
            state = self._load_state()
            duplicate_index = state.get("duplicate_index", {})
            reports = state.get("reports", {})
            existing_id = duplicate_index.get(candidate.duplicate_hash)
            if deduplicate and existing_id and existing_id in reports:
                existing = Report.from_dict(reports[existing_id])
                existing.updated_at = _utcnow_iso()
                reports[existing.report_id] = existing.to_dict()
                state["reports"] = reports
                self._save_state(state)
                return existing, True

            candidate.artifact_uri = self._persist_report_artifacts(candidate)
            candidate.updated_at = _utcnow_iso()
            reports[candidate.report_id] = candidate.to_dict()
            duplicate_index[candidate.duplicate_hash] = candidate.report_id

            mission_index = state.get("mission_index", {})
            if candidate.mission_id:
                mission_rows = mission_index.get(candidate.mission_id, [])
                if candidate.report_id not in mission_rows:
                    mission_rows.append(candidate.report_id)
                mission_index[candidate.mission_id] = mission_rows

            state["reports"] = reports
            state["duplicate_index"] = duplicate_index
            state["mission_index"] = mission_index
            self._save_state(state)
            return candidate, False

    def get_report(self, report_id: str) -> Report | None:
        with self._lock:
            state = self._load_state()
            payload = state.get("reports", {}).get(report_id)
            if not isinstance(payload, dict):
                return None
            return Report.from_dict(payload)

    def list_reports(
        self,
        *,
        tenant_id: str | None = None,
        severity: str | None = None,
        min_confidence: float | None = None,
        target: str | None = None,
        mission_id: str | None = None,
        opportunity_id: str | None = None,
    ) -> list[Report]:
        with self._lock:
            state = self._load_state()
            report_rows = [Report.from_dict(payload) for payload in state.get("reports", {}).values() if isinstance(payload, dict)]

        normalized_target = _normalize_target(target)
        normalized_severity = _normalize_text(severity).lower()
        min_confidence_value = _safe_float(min_confidence, 0.0) if min_confidence is not None else None

        filtered: list[Report] = []
        for report in report_rows:
            if tenant_id is not None and report.tenant_id != tenant_id:
                continue
            if mission_id and report.mission_id != mission_id:
                continue
            if opportunity_id and report.opportunity_id != opportunity_id:
                continue
            if normalized_severity and report.severity.lower() != normalized_severity:
                continue
            if normalized_target and _normalize_target(report.target) != normalized_target:
                continue
            if min_confidence_value is not None and report.confidence_score < min_confidence_value:
                continue
            filtered.append(report)

        filtered.sort(key=lambda row: row.updated_at, reverse=True)
        return filtered

    def reports_for_mission(self, mission_id: str) -> list[Report]:
        return self.list_reports(mission_id=mission_id)


_ENGINE: ReportEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_report_engine() -> ReportEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = ReportEngine()
        return _ENGINE
