from __future__ import annotations

from apps.backend.src.core.skill_router import SignedSkillContext, SkillRouter, sign_skill_context


def test_skill_router_invocation_with_signed_context(monkeypatch):
    monkeypatch.setenv("K1_SECRET_BACKEND", "env")
    monkeypatch.setenv("K1_SKILL_ROUTER_HMAC_KEY", "test-key")
    router = SkillRouter()
    router.register("echo", lambda payload: {"echo": payload.get("value")})

    sig = sign_skill_context("run-1", "prog-1", "cert-1", "user-1")
    context = SignedSkillContext(
        run_id="run-1",
        program_id="prog-1",
        certificate_id="cert-1",
        user_id="user-1",
        signature=sig,
    )
    out = router.invoke("echo", {"value": "ok"}, context)
    assert out["result"]["echo"] == "ok"


def test_skill_router_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("K1_SECRET_BACKEND", "env")
    monkeypatch.setenv("K1_SKILL_ROUTER_HMAC_KEY", "test-key")
    router = SkillRouter()
    router.register("echo", lambda payload: {"echo": payload.get("value")})
    context = SignedSkillContext(
        run_id="run-1",
        program_id="prog-1",
        certificate_id="cert-1",
        user_id="user-1",
        signature="bad",
    )
    try:
        router.invoke("echo", {"value": "ok"}, context)
    except PermissionError as exc:
        assert "invalid skill context signature" in str(exc)
        return
    raise AssertionError("expected PermissionError")
