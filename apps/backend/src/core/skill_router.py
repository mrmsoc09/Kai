from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any, Callable, Dict

from .secret_manager import get_secret_manager, SecretManagerError


SkillHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass(frozen=True)
class SignedSkillContext:
    run_id: str
    program_id: str
    certificate_id: str
    user_id: str
    signature: str

    def canonical_payload(self) -> str:
        payload = {
            "certificate_id": self.certificate_id,
            "program_id": self.program_id,
            "run_id": self.run_id,
            "user_id": self.user_id,
        }
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _resolve_hmac_key() -> str:
    try:
        key = get_secret_manager().get_required("K1_SKILL_ROUTER_HMAC_KEY")
    except SecretManagerError as exc:
        raise RuntimeError("skill router signing key unavailable") from exc
    return key


def sign_skill_context(run_id: str, program_id: str, certificate_id: str, user_id: str) -> str:
    context = SignedSkillContext(
        run_id=run_id,
        program_id=program_id,
        certificate_id=certificate_id,
        user_id=user_id,
        signature="",
    )
    key = _resolve_hmac_key().encode("utf-8")
    msg = context.canonical_payload().encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_skill_context(context: SignedSkillContext) -> bool:
    expected = sign_skill_context(
        run_id=context.run_id,
        program_id=context.program_id,
        certificate_id=context.certificate_id,
        user_id=context.user_id,
    )
    return hmac.compare_digest(expected, context.signature)


class SkillRouter:
    def __init__(self) -> None:
        self._skills: Dict[str, SkillHandler] = {}

    def register(self, skill_id: str, handler: SkillHandler) -> None:
        if not skill_id.strip():
            raise ValueError("skill_id required")
        self._skills[skill_id] = handler

    def invoke(self, skill_id: str, payload: Dict[str, Any], context: SignedSkillContext) -> Dict[str, Any]:
        if skill_id not in self._skills:
            raise KeyError(f"unknown skill: {skill_id}")
        if not verify_skill_context(context):
            raise PermissionError("invalid skill context signature")
        if not context.run_id or not context.program_id or not context.certificate_id or not context.user_id:
            raise PermissionError("incomplete skill context")
        result = self._skills[skill_id](payload)
        return {
            "skill_id": skill_id,
            "result": result,
            "context": {
                "run_id": context.run_id,
                "program_id": context.program_id,
                "certificate_id": context.certificate_id,
                "user_id": context.user_id,
            },
        }
