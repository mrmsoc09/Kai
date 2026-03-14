from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .kai_security_guardrails import get_guardrail_engine
from .scope_guardrails import evaluate_target_scope, load_scope_policy
from .scope_resolver import is_in_scope_for_workflow, is_in_scope_for_workflow_async
from .toolpacks import get_toolpack_manager


class AuthorizationGateError(RuntimeError):
    """Raised when scope or authorization checks fail."""


@dataclass(frozen=True)
class AuthorizationGateContext:
    tool_id: str
    target: str
    program_id: str
    method: str
    user_id: str
    certificate_id: str


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_target(target: str) -> str:
    text = (target or "").strip()
    if not text:
        return ""
    if "://" in text:
        parsed = urlparse(text)
        return parsed.hostname or ""
    return text


def scope_validator(
    target: str,
    program_id: str,
    method: str,
    workflow_id: Optional[str] = None,
) -> bool:
    normalized_target = _normalize_target(target)
    if not normalized_target:
        return False
    if not (program_id or "").strip():
        return False
    if not (method or "").strip():
        return False
    if workflow_id:
        return is_in_scope_for_workflow(normalized_target, workflow_id=workflow_id)
    policy = load_scope_policy()
    decision = evaluate_target_scope(normalized_target, policy)
    return decision.allowed


def authorization_certificate_check(
    user_id: str,
    certificate_id: str,
    target: str,
    method: str,
) -> bool:
    if not (user_id or "").strip():
        return False
    if not (certificate_id or "").strip():
        return False

    guardrails = get_guardrail_engine()
    cert = guardrails.authorized_certificates.get(certificate_id)
    if not cert:
        return False
    if not cert.is_valid():
        return False

    normalized_target = _normalize_target(target)
    if not guardrails._matches_target(cert.target, normalized_target):
        return False
    if method not in cert.allowed_methods:
        return False

    cert_user = (cert.metadata or {}).get("user_id")
    if cert_user and cert_user != user_id:
        return False
    return True


def _extract_target(params: Dict[str, Any]) -> Optional[str]:
    for key in ("target", "url", "domain", "host", "ip", "rhost"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _resolve_method(tool_id: str, explicit_method: Optional[str]) -> str:
    if explicit_method and explicit_method.strip():
        return explicit_method.strip()
    manager = get_toolpack_manager()
    if manager.config is not None:
        resolved = manager.get_method_for_adapter(tool_id)
        if resolved:
            return resolved
    return "tool_execution"


def build_authorization_context(
    tool_id: str,
    params: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    program_id: Optional[str] = None,
    certificate_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    method: Optional[str] = None,
) -> AuthorizationGateContext:
    target = _extract_target(params) or ""
    guardrails = get_guardrail_engine()
    # Identity/scope context must be explicit at call boundary, not inferred from
    # caller-controlled params payload fields.
    resolved_certificate_id = (certificate_id or "").strip()
    cert = guardrails.authorized_certificates.get(resolved_certificate_id)
    cert_program_id = ""
    if cert is not None:
        cert_program_id = str((cert.metadata or {}).get("program_id") or "").strip()
    resolved_program_id = (program_id or cert_program_id or "").strip()
    if cert_program_id and resolved_program_id and resolved_program_id != cert_program_id:
        raise AuthorizationGateError("program_id does not match certificate metadata")
    return AuthorizationGateContext(
        tool_id=tool_id,
        target=target,
        program_id=resolved_program_id,
        method=_resolve_method(tool_id, method or params.get("method")),
        user_id=(user_id or "").strip(),
        certificate_id=resolved_certificate_id,
    )


def enforce_authorization_gates(
    tool_id: str,
    params: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    program_id: Optional[str] = None,
    certificate_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    method: Optional[str] = None,
) -> AuthorizationGateContext:
    # Tests can disable strict gate checks when exercising unrelated flows.
    # K1_RELAX_AUTH_GATES_FOR_TESTS must be explicitly set to "true" — it does not default on.
    if _env_bool("K1_TEST_MODE", False) and _env_bool("K1_RELAX_AUTH_GATES_FOR_TESTS", False):
        return build_authorization_context(
            tool_id,
            params,
            user_id=user_id,
            program_id=program_id or "test-program",
            certificate_id=certificate_id or "test-certificate",
            method=method or "tool_execution",
        )

    # Resolve workflow_id from params if not explicitly provided
    _workflow_id = workflow_id or params.get("workflow_id") or None

    ctx = build_authorization_context(
        tool_id,
        params,
        user_id=user_id,
        program_id=program_id,
        certificate_id=certificate_id,
        workflow_id=_workflow_id,
        method=method,
    )
    if not ctx.target:
        raise AuthorizationGateError("missing target for scope validation")
    # Pass workflow_id to scope_validator so it can match against workflow scope_domains
    if not scope_validator(ctx.target, ctx.program_id, ctx.method, workflow_id=_workflow_id):
        raise AuthorizationGateError("scope_validator failed")
    if not authorization_certificate_check(ctx.user_id, ctx.certificate_id, ctx.target, ctx.method):
        raise AuthorizationGateError("authorization_certificate_check failed")
    return ctx


async def scope_validator_async(
    target: str,
    program_id: str,
    method: str,
    workflow_id: Optional[str] = None,
) -> bool:
    normalized_target = _normalize_target(target)
    if not normalized_target:
        return False
    if not (program_id or "").strip():
        return False
    if not (method or "").strip():
        return False
    if workflow_id:
        return await is_in_scope_for_workflow_async(normalized_target, workflow_id=workflow_id)
    policy = load_scope_policy()
    decision = evaluate_target_scope(normalized_target, policy)
    return decision.allowed


async def enforce_authorization_gates_async(
    tool_id: str,
    params: Dict[str, Any],
    *,
    user_id: Optional[str] = None,
    program_id: Optional[str] = None,
    certificate_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    method: Optional[str] = None,
) -> AuthorizationGateContext:
    # Tests can disable strict gate checks when exercising unrelated flows.
    # K1_RELAX_AUTH_GATES_FOR_TESTS must be explicitly set to "true" — it does not default on.
    if _env_bool("K1_TEST_MODE", False) and _env_bool("K1_RELAX_AUTH_GATES_FOR_TESTS", False):
        return build_authorization_context(
            tool_id,
            params,
            user_id=user_id,
            program_id=program_id or "test-program",
            certificate_id=certificate_id or "test-certificate",
            method=method or "tool_execution",
        )

    _workflow_id = workflow_id or params.get("workflow_id") or None
    ctx = build_authorization_context(
        tool_id,
        params,
        user_id=user_id,
        program_id=program_id,
        certificate_id=certificate_id,
        workflow_id=_workflow_id,
        method=method,
    )
    if not ctx.target:
        raise AuthorizationGateError("missing target for scope validation")
    if not await scope_validator_async(ctx.target, ctx.program_id, ctx.method, workflow_id=_workflow_id):
        raise AuthorizationGateError("scope_validator failed")
    if not authorization_certificate_check(ctx.user_id, ctx.certificate_id, ctx.target, ctx.method):
        raise AuthorizationGateError("authorization_certificate_check failed")
    return ctx
