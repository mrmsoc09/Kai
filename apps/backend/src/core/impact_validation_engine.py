from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .audit_logger import write_audit_record
from .scope_guardrails import ScopePolicy, evaluate_target_scope, load_scope_policy

MIN_EVIDENCE_QUALITY_SCORE = 0.75
MIN_IMPACT_SCORE = 0.35
REQUIRED_IMPACT_STATEMENT_FIELDS = (
    "impact_summary",
    "technical_impact",
    "business_impact",
    "severity_estimate",
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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


def _artifact_root() -> Path:
    configured = os.getenv("K1_IMPACT_VALIDATION_ARTIFACT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    artifacts_root = os.getenv("K1_ARTIFACTS_ROOT")
    if artifacts_root:
        return (Path(artifacts_root).expanduser().resolve() / "impact_validation")
    return Path("artifacts/impact_validation").resolve()


def _mission_log_path(mission_id: str) -> Path:
    safe_mission = _normalize_text(mission_id) or "unknown-mission"
    return _artifact_root() / safe_mission / "mission_log.jsonl"


def _events_log_path() -> Path:
    return _artifact_root() / "events.jsonl"


def _normalize_vulnerability_type(finding: Mapping[str, Any]) -> str:
    raw = _normalize_text(
        finding.get("vulnerability_type")
        or finding.get("vuln_type")
        or finding.get("type")
    ).lower()
    if not raw:
        return "unknown"
    normalized = raw.replace("-", "_").replace(" ", "_")
    if "idor" in normalized:
        return "idor"
    if "ssrf" in normalized:
        return "ssrf"
    if "rce" in normalized or "command_injection" in normalized:
        return "rce"
    if "sqli" in normalized or "injection" in normalized:
        return "injection"
    return normalized


def _response_status_code(value: Any) -> int | None:
    if isinstance(value, Mapping):
        for key in ("status_code", "status", "code"):
            if key in value:
                try:
                    return int(value[key])
                except (TypeError, ValueError):
                    return None
    return None


def _response_body(value: Any) -> str:
    if isinstance(value, Mapping):
        for key in ("body", "response", "payload", "content"):
            text = _normalize_text(value.get(key))
            if text:
                return text[:4000]
    return _normalize_text(value)[:4000]


def _extract_response_text(finding: Mapping[str, Any], key: str) -> str:
    direct = finding.get(key)
    if direct is not None:
        return _response_body(direct)
    if key == "baseline_response":
        alt = finding.get("baseline")
    else:
        alt = finding.get("exploit_result")
    return _response_body(alt)


@dataclass(slots=True)
class ImpactValidationResult:
    validation_id: str
    mission_id: str
    stage_id: str
    finding_key: str
    vulnerability_type: str
    target: str
    behavior_difference_score: float
    data_exposure_score: float
    privilege_potential_score: float
    impact_score: float
    severity_estimate: str
    impact_statement: dict[str, str]
    capability_validation_results: dict[str, Any]
    impact_limited_due_to_scope: bool
    scope_compliance_status: str
    scope_reason: str
    commands_executed: list[str]
    allowed_actions_taken: list[str]
    blocked_actions: list[str]
    submission_candidate: bool
    created_at: str
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["behavior_difference_score"] = round(_clamp(self.behavior_difference_score), 4)
        payload["data_exposure_score"] = round(_clamp(self.data_exposure_score), 4)
        payload["privilege_potential_score"] = round(_clamp(self.privilege_potential_score), 4)
        payload["impact_score"] = round(_clamp(self.impact_score), 4)
        return payload


class ImpactValidationEngine:
    _lock = threading.Lock()
    _safe_ssrf_path_re = re.compile(r"^/(health|status|version|ready|robots\.txt|favicon\.ico)(/|$)", re.IGNORECASE)
    _safe_rce_commands = {"whoami", "id", "pwd", "echo test"}

    def __init__(self, *, scope_policy: ScopePolicy | None = None) -> None:
        self._scope_policy = scope_policy or load_scope_policy()

    def validate(
        self,
        finding: Mapping[str, Any],
        *,
        qualification: Mapping[str, Any] | None = None,
        baseline_response: Any | None = None,
        exploit_response: Any | None = None,
        scope_metadata: Mapping[str, Any] | None = None,
        mission_id: str | None = None,
        stage_id: str | None = None,
        report_id: str | None = None,
        persist: bool = True,
    ) -> ImpactValidationResult:
        mission = _normalize_text(mission_id)
        stage = _normalize_text(stage_id)
        target = _normalize_target(
            finding.get("target")
            or finding.get("host")
            or finding.get("domain")
            or finding.get("url")
            or (scope_metadata or {}).get("target")
        )
        vuln_type = _normalize_vulnerability_type(finding)
        finding_key = "|".join(
            [
                _normalize_text(report_id),
                _normalize_text(finding.get("finding_id") or finding.get("id")),
                vuln_type,
                target,
                _normalize_text(finding.get("endpoint") or finding.get("path")),
            ]
        ).strip("|")
        if not finding_key:
            finding_key = f"finding:{sha256(json.dumps(dict(finding), sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"

        scope_valid, scope_reason = self._scope_validity(target, scope_metadata)
        capability = self._capability_validation(
            vuln_type=vuln_type,
            finding=finding,
            baseline_response=baseline_response,
            exploit_response=exploit_response,
            scope_valid=scope_valid,
        )
        behavior = self._behavior_difference_score(
            baseline=baseline_response if baseline_response is not None else finding.get("baseline_response"),
            exploit=exploit_response if exploit_response is not None else finding.get("exploit_response"),
        )
        exposure = self._data_exposure_score(
            finding=finding,
            exploit=exploit_response if exploit_response is not None else finding.get("exploit_response"),
        )
        privilege = self._privilege_potential_score(
            vuln_type=vuln_type,
            behavior_difference_score=behavior,
            data_exposure_score=exposure,
            capability_status=_normalize_text(capability.get("status")),
        )
        impact_score = _clamp((behavior * 0.4) + (exposure * 0.35) + (privilege * 0.25))

        if not scope_valid:
            impact_score = min(impact_score, 0.2)
        if _normalize_text(capability.get("status")) == "limited":
            impact_score = min(impact_score, 0.55)

        severity = self._severity_estimate(impact_score)
        statement = self._impact_statement(
            finding=finding,
            vulnerability_type=vuln_type,
            target=target,
            severity=severity,
            capability=capability,
            impact_score=impact_score,
            scope_valid=scope_valid,
        )

        qualification_candidate = True
        if isinstance(qualification, Mapping):
            qualification_candidate = bool(qualification.get("submission_candidate", True))
        statement_complete = all(_normalize_text(statement.get(field)) for field in REQUIRED_IMPACT_STATEMENT_FIELDS)
        submission_candidate = (
            scope_valid
            and qualification_candidate
            and impact_score >= MIN_IMPACT_SCORE
            and statement_complete
        )

        result = ImpactValidationResult(
            validation_id=f"iv-{sha256(f'{finding_key}:{_utcnow_iso()}'.encode('utf-8')).hexdigest()[:16]}",
            mission_id=mission,
            stage_id=stage,
            finding_key=finding_key,
            vulnerability_type=vuln_type,
            target=target,
            behavior_difference_score=behavior,
            data_exposure_score=exposure,
            privilege_potential_score=privilege,
            impact_score=impact_score,
            severity_estimate=severity,
            impact_statement=statement,
            capability_validation_results=capability,
            impact_limited_due_to_scope=not scope_valid or _normalize_text(capability.get("status")) == "limited",
            scope_compliance_status="in_scope" if scope_valid else "out_of_scope",
            scope_reason=scope_reason,
            commands_executed=list(capability.get("commands_executed") or []),
            allowed_actions_taken=list(capability.get("allowed_actions_taken") or []),
            blocked_actions=list(capability.get("blocked_actions") or []),
            submission_candidate=submission_candidate,
            created_at=_utcnow_iso(),
            artifact_path=None,
        )

        self._emit_event("impact_validation_started", result)
        if persist:
            result.artifact_path = self._persist_result(result, finding=finding)
        self._emit_event("impact_validation_completed", result)
        return result

    def _scope_validity(
        self,
        target: str,
        scope_metadata: Mapping[str, Any] | None,
    ) -> tuple[bool, str]:
        meta = dict(scope_metadata or {})
        if "scope_validity" in meta:
            valid = bool(meta.get("scope_validity"))
            return valid, "scope_metadata.scope_validity"
        if "in_scope" in meta:
            valid = bool(meta.get("in_scope"))
            return valid, "scope_metadata.in_scope"
        if "allowed" in meta:
            valid = bool(meta.get("allowed"))
            return valid, "scope_metadata.allowed"
        decision = evaluate_target_scope(target, self._scope_policy)
        return bool(decision.allowed), _normalize_text(decision.reason) or "scope_guardrails"

    def _capability_validation(
        self,
        *,
        vuln_type: str,
        finding: Mapping[str, Any],
        baseline_response: Any | None,
        exploit_response: Any | None,
        scope_valid: bool,
    ) -> dict[str, Any]:
        if not scope_valid:
            return {
                "status": "limited",
                "reason": "impact_limited_due_to_scope",
                "allowed_actions_taken": [],
                "blocked_actions": ["all_actions_blocked_out_of_scope"],
                "commands_executed": [],
            }

        if vuln_type == "idor":
            return self._validate_idor(finding=finding, baseline_response=baseline_response, exploit_response=exploit_response)
        if vuln_type == "ssrf":
            return self._validate_ssrf(finding=finding)
        if vuln_type == "rce":
            return self._validate_rce(finding=finding)
        if vuln_type == "injection":
            return self._validate_injection(finding=finding, baseline_response=baseline_response, exploit_response=exploit_response)
        return {
            "status": "limited",
            "reason": "unsupported_vulnerability_type_for_impact_validation",
            "allowed_actions_taken": [],
            "blocked_actions": ["unsupported_vulnerability_type"],
            "commands_executed": [],
        }

    def _validate_idor(
        self,
        *,
        finding: Mapping[str, Any],
        baseline_response: Any | None,
        exploit_response: Any | None,
    ) -> dict[str, Any]:
        baseline = _response_body(baseline_response if baseline_response is not None else finding.get("baseline_response"))
        exploit = _response_body(exploit_response if exploit_response is not None else finding.get("exploit_response"))
        indicators = [
            bool(finding.get("cross_resource_access")),
            "other_user" in exploit.lower(),
            "unauthorized resource" in exploit.lower(),
            "account_id" in exploit.lower() and "account_id" in baseline.lower() and exploit != baseline,
        ]
        validated = any(indicators)
        return {
            "status": "validated" if validated else "limited",
            "reason": "read_only_cross_resource_access_confirmed" if validated else "idor_boundary_not_confirmed",
            "allowed_actions_taken": ["read_only_cross_resource_access_check"],
            "blocked_actions": ["sensitive_record_enumeration_blocked"],
            "commands_executed": [],
        }

    def _validate_ssrf(self, *, finding: Mapping[str, Any]) -> dict[str, Any]:
        endpoints = finding.get("ssrf_endpoints_tested")
        if not isinstance(endpoints, list):
            endpoints = []
        allowed: list[str] = []
        blocked: list[str] = []
        for raw in endpoints:
            candidate = _normalize_text(raw)
            parsed = urlparse(candidate if "://" in candidate else f"http://placeholder{candidate}")
            path = parsed.path or candidate
            if self._safe_ssrf_path_re.match(path):
                allowed.append(candidate)
            else:
                blocked.append(candidate)
        status = "validated" if allowed else "limited"
        if blocked and not allowed:
            reason = "ssrf_only_unsafe_endpoints_requested"
        elif blocked:
            reason = "ssrf_safe_subset_validated"
        elif allowed:
            reason = "ssrf_safe_endpoint_reachability_validated"
        else:
            reason = "ssrf_no_safe_endpoint_probes_present"
        return {
            "status": status,
            "reason": reason,
            "allowed_actions_taken": ["safe_internal_endpoint_probe"] if allowed else [],
            "blocked_actions": [f"blocked_ssrf_endpoint:{item}" for item in blocked],
            "safe_endpoints_validated": allowed,
            "commands_executed": [],
        }

    def _validate_rce(self, *, finding: Mapping[str, Any]) -> dict[str, Any]:
        commands = finding.get("impact_probe_commands")
        if not isinstance(commands, list):
            commands = finding.get("commands_executed")
        if not isinstance(commands, list):
            commands = []
        allowed: list[str] = []
        blocked: list[str] = []
        for item in commands:
            command = _normalize_text(item).lower()
            if not command:
                continue
            if command in self._safe_rce_commands:
                allowed.append(command)
            else:
                blocked.append(command)
        status = "validated" if allowed else "limited"
        return {
            "status": status,
            "reason": "safe_command_execution_validated" if allowed else "no_safe_rce_commands_provided",
            "allowed_actions_taken": ["safe_command_probe"] if allowed else [],
            "blocked_actions": [f"blocked_command:{cmd}" for cmd in blocked],
            "commands_executed": allowed,
        }

    def _validate_injection(
        self,
        *,
        finding: Mapping[str, Any],
        baseline_response: Any | None,
        exploit_response: Any | None,
    ) -> dict[str, Any]:
        baseline = _response_body(baseline_response if baseline_response is not None else finding.get("baseline_response")).lower()
        exploit = _response_body(exploit_response if exploit_response is not None else finding.get("exploit_response")).lower()
        controlled_extract = bool(finding.get("controlled_extraction_confirmed"))
        error_shift = (
            any(marker in exploit for marker in ["sql syntax", "syntax error", "ora-", "psql", "sqlite"])
            and not any(marker in baseline for marker in ["sql syntax", "syntax error", "ora-", "psql", "sqlite"])
        )
        validated = controlled_extract or error_shift
        return {
            "status": "validated" if validated else "limited",
            "reason": "controlled_extraction_or_error_shift_confirmed" if validated else "injection_delta_not_confirmed",
            "allowed_actions_taken": ["read_only_extraction_probe" if controlled_extract else "error_behavior_probe"],
            "blocked_actions": ["state_modification_probe_blocked"],
            "commands_executed": [],
        }

    def _behavior_difference_score(self, *, baseline: Any | None, exploit: Any | None) -> float:
        baseline_body = _response_body(baseline).lower()
        exploit_body = _response_body(exploit).lower()
        baseline_status = _response_status_code(baseline)
        exploit_status = _response_status_code(exploit)

        score = 0.0
        if baseline_status is not None and exploit_status is not None and baseline_status != exploit_status:
            score += 0.25
        if baseline_body and exploit_body and baseline_body != exploit_body:
            delta = abs(len(exploit_body) - len(baseline_body)) / max(1, max(len(exploit_body), len(baseline_body)))
            if delta >= 0.1:
                score += 0.2
            score += 0.1
        leak_markers = ["password", "token", "secret", "ssn", "email", "account_id", "api_key"]
        leak_delta = any(marker in exploit_body and marker not in baseline_body for marker in leak_markers)
        if leak_delta:
            score += 0.3
        boundary_markers = ["forbidden", "unauthorized", "not allowed"]
        boundary_shift = any(marker in baseline_body for marker in boundary_markers) and not any(
            marker in exploit_body for marker in boundary_markers
        )
        if boundary_shift:
            score += 0.15
        return _clamp(score)

    def _data_exposure_score(self, *, finding: Mapping[str, Any], exploit: Any | None) -> float:
        text = " ".join(
            [
                _normalize_text(finding.get("summary")),
                _normalize_text(finding.get("description")),
                _response_body(exploit),
            ]
        ).lower()
        if any(marker in text for marker in ["credit card", "payment", "iban", "wire", "bank_account"]):
            sensitivity = 1.0
        elif any(marker in text for marker in ["password", "token", "api_key", "private_key", "secret", "ssn"]):
            sensitivity = 0.9
        elif any(marker in text for marker in ["email", "phone", "address", "user_profile"]):
            sensitivity = 0.7
        elif any(marker in text for marker in ["internal", "employee", "admin_panel"]):
            sensitivity = 0.6
        else:
            sensitivity = 0.3

        breadth = 0.2
        tenant_count = _safe_float(finding.get("affected_tenant_count"), 0.0)
        record_count = _safe_float(finding.get("affected_record_count"), 0.0)
        if tenant_count >= 2 or "multi-tenant" in text or "all users" in text:
            breadth = 0.95
        elif record_count >= 50:
            breadth = 0.8
        elif record_count >= 5:
            breadth = 0.6
        elif record_count >= 1:
            breadth = 0.45

        return _clamp((sensitivity * 0.7) + (breadth * 0.3))

    @staticmethod
    def _privilege_potential_score(
        *,
        vuln_type: str,
        behavior_difference_score: float,
        data_exposure_score: float,
        capability_status: str,
    ) -> float:
        base = {
            "idor": 0.65,
            "ssrf": 0.5,
            "rce": 0.95,
            "injection": 0.8,
        }.get(vuln_type, 0.4)
        score = base + (behavior_difference_score * 0.15) + (data_exposure_score * 0.15)
        if capability_status == "limited":
            score -= 0.2
        return _clamp(score)

    @staticmethod
    def _severity_estimate(impact_score: float) -> str:
        if impact_score >= 0.9:
            return "critical"
        if impact_score >= 0.7:
            return "high"
        if impact_score >= 0.45:
            return "medium"
        return "low"

    def _impact_statement(
        self,
        *,
        finding: Mapping[str, Any],
        vulnerability_type: str,
        target: str,
        severity: str,
        capability: Mapping[str, Any],
        impact_score: float,
        scope_valid: bool,
    ) -> dict[str, str]:
        capability_reason = _normalize_text(capability.get("reason")) or "capability_assessment_complete"
        if not scope_valid:
            impact_summary = f"Impact validation was limited because `{target}` is out of scope for active probing."
            technical = "No additional impact actions were executed due to scope enforcement."
            business = "Treat as non-actionable until scope authorization is confirmed."
        else:
            impact_summary = (
                f"{vulnerability_type.upper()} on `{target}` demonstrated bounded impact signals "
                f"with score {impact_score:.2f}."
            )
            technical = (
                f"Capability validation status: {capability_reason}. "
                "Only bug-bounty-safe, read-only, non-destructive checks were allowed."
            )
            business = (
                f"Estimated severity is {severity}. The issue can affect confidentiality/integrity boundaries "
                "without requiring invasive post-exploitation actions."
            )
        return {
            "impact_summary": impact_summary,
            "technical_impact": technical,
            "business_impact": business,
            "severity_estimate": severity,
        }

    def _persist_result(self, result: ImpactValidationResult, *, finding: Mapping[str, Any]) -> str:
        root = _artifact_root()
        mission_dir = root / (_normalize_text(result.mission_id) or "unknown-mission")
        mission_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = mission_dir / f"{result.validation_id}.json"

        payload = result.to_dict()
        payload["finding"] = dict(finding)
        artifact_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        mission_log = _mission_log_path(result.mission_id)
        mission_log.parent.mkdir(parents=True, exist_ok=True)
        with mission_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

        events_log = _events_log_path()
        events_log.parent.mkdir(parents=True, exist_ok=True)
        with events_log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_type": "impact_validation_artifact_written",
                        "validation_id": result.validation_id,
                        "mission_id": result.mission_id,
                        "stage_id": result.stage_id,
                        "artifact_path": str(artifact_path),
                        "timestamp": _utcnow_iso(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return str(artifact_path)

    @staticmethod
    def _emit_event(event_type: str, result: ImpactValidationResult) -> None:
        write_audit_record(
            event_type,
            mission_id=result.mission_id,
            decision="allowed" if result.submission_candidate else "limited",
            reason=result.scope_reason or "impact_validation_complete",
            detail={
                "validation_id": result.validation_id,
                "finding_key": result.finding_key,
                "vulnerability_type": result.vulnerability_type,
                "impact_score": round(result.impact_score, 4),
                "severity_estimate": result.severity_estimate,
                "scope_compliance_status": result.scope_compliance_status,
                "allowed_actions_taken": result.allowed_actions_taken,
                "commands_executed": result.commands_executed,
                "blocked_actions": result.blocked_actions,
            },
        )


_ENGINE: ImpactValidationEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_impact_validation_engine() -> ImpactValidationEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = ImpactValidationEngine()
        return _ENGINE


def validate_impact(
    finding: Mapping[str, Any],
    *,
    qualification: Mapping[str, Any] | None = None,
    baseline_response: Any | None = None,
    exploit_response: Any | None = None,
    scope_metadata: Mapping[str, Any] | None = None,
    mission_id: str | None = None,
    stage_id: str | None = None,
    report_id: str | None = None,
    persist: bool = True,
) -> ImpactValidationResult:
    return get_impact_validation_engine().validate(
        finding,
        qualification=qualification,
        baseline_response=baseline_response,
        exploit_response=exploit_response,
        scope_metadata=scope_metadata,
        mission_id=mission_id,
        stage_id=stage_id,
        report_id=report_id,
        persist=persist,
    )


def resolve_submission_candidate_decision(
    *,
    evidence_qualification: Mapping[str, Any] | None,
    impact_validation: Mapping[str, Any] | None,
) -> dict[str, Any]:
    qualification = dict(evidence_qualification or {})
    impact = dict(impact_validation or {})

    if not qualification:
        return {
            "submission_candidate": False,
            "rejection_reason": "evidence_qualification_missing",
            "warnings": [],
            "additional_data_needed": ["evidence_qualification"],
            "decision_basis": {"evidence_qualification_present": False, "impact_validation_present": bool(impact)},
        }
    evidence_quality_score = _safe_float(qualification.get("evidence_quality_score"), 0.0)
    if not bool(qualification.get("submission_candidate")):
        return {
            "submission_candidate": False,
            "rejection_reason": _normalize_text(qualification.get("rejection_reason")) or "evidence_qualification_rejected",
            "warnings": [],
            "additional_data_needed": ["evidence_requalification"],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": bool(impact),
                "evidence_quality_score": evidence_quality_score,
            },
        }
    if evidence_quality_score < MIN_EVIDENCE_QUALITY_SCORE:
        return {
            "submission_candidate": False,
            "rejection_reason": "evidence_quality_below_threshold",
            "warnings": [],
            "additional_data_needed": ["higher_reproducibility_and_evidence_quality"],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": bool(impact),
                "evidence_quality_score": evidence_quality_score,
                "required_evidence_quality_score": MIN_EVIDENCE_QUALITY_SCORE,
            },
        }
    if not impact:
        return {
            "submission_candidate": False,
            "rejection_reason": "impact_validation_missing",
            "warnings": [],
            "additional_data_needed": ["impact_validation"],
            "decision_basis": {"evidence_qualification_present": True, "impact_validation_present": False},
        }
    impact_score = _safe_float(impact.get("impact_score"), 0.0)
    if not bool(impact.get("submission_candidate")):
        rejection_reason = (
            _normalize_text(impact.get("scope_reason"))
            or _normalize_text((impact.get("capability_validation_results") or {}).get("reason"))
            or "impact_validation_rejected"
        )
        return {
            "submission_candidate": False,
            "rejection_reason": rejection_reason,
            "warnings": [],
            "additional_data_needed": ["safe_impact_validation_signal"],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": True,
                "impact_score": impact_score,
                "scope_compliance_status": _normalize_text(impact.get("scope_compliance_status")),
            },
        }
    if impact_score < MIN_IMPACT_SCORE:
        return {
            "submission_candidate": False,
            "rejection_reason": "impact_score_below_threshold",
            "warnings": [],
            "additional_data_needed": ["stronger_behavioral_impact_validation"],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": True,
                "impact_score": impact_score,
                "required_impact_score": MIN_IMPACT_SCORE,
                "scope_compliance_status": _normalize_text(impact.get("scope_compliance_status")),
            },
        }
    impact_statement = impact.get("impact_statement")
    if not isinstance(impact_statement, dict) or not impact_statement:
        return {
            "submission_candidate": False,
            "rejection_reason": "impact_statement_missing",
            "warnings": [],
            "additional_data_needed": ["structured_impact_statement"],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": True,
                "impact_score": impact_score,
            },
        }
    missing_statement_fields = [
        field for field in REQUIRED_IMPACT_STATEMENT_FIELDS if not _normalize_text(impact_statement.get(field))
    ]
    if missing_statement_fields:
        return {
            "submission_candidate": False,
            "rejection_reason": "impact_statement_incomplete",
            "warnings": [],
            "additional_data_needed": [f"impact_statement.{field}" for field in missing_statement_fields],
            "decision_basis": {
                "evidence_qualification_present": True,
                "impact_validation_present": True,
                "impact_score": impact_score,
                "missing_statement_fields": missing_statement_fields,
            },
        }

    warnings: list[str] = []
    if bool(impact.get("impact_limited_due_to_scope")):
        warnings.append("impact_validation_limited")

    return {
        "submission_candidate": True,
        "rejection_reason": None,
        "warnings": warnings,
        "additional_data_needed": [],
        "decision_basis": {
            "evidence_qualification_present": True,
            "impact_validation_present": True,
            "evidence_quality_score": evidence_quality_score,
            "required_evidence_quality_score": MIN_EVIDENCE_QUALITY_SCORE,
            "impact_score": impact_score,
            "required_impact_score": MIN_IMPACT_SCORE,
            "scope_compliance_status": _normalize_text(impact.get("scope_compliance_status")),
        },
    }
