from __future__ import annotations

from apps.backend.src.core.opsec_policy import MethodPolicy, OPSECPolicyEngine, OPSECPolicyError


def _engine(tmp_path):
    return OPSECPolicyEngine(
        {
            "recon": MethodPolicy(
                method="recon",
                max_requests_per_minute=2,
                max_concurrent=1,
                max_executions_per_hour=3,
            )
        }
    )


def test_opsec_concurrency_enforced(tmp_path):
    engine = _engine(tmp_path)
    t1 = engine.acquire("recon", "dnsx")
    try:
        try:
            engine.acquire("recon", "httpx")
            assert False, "expected concurrency block"
        except OPSECPolicyError as exc:
            assert "concurrency limit exceeded" in str(exc)
    finally:
        engine.release(t1, "completed")


def test_opsec_rate_limit_enforced(tmp_path):
    engine = _engine(tmp_path)
    t1 = engine.acquire("recon", "dnsx")
    engine.release(t1, "completed")
    t2 = engine.acquire("recon", "httpx")
    engine.release(t2, "completed")

    try:
        engine.acquire("recon", "naabu")
        assert False, "expected rate-limit block"
    except OPSECPolicyError as exc:
        assert "rate limit exceeded" in str(exc)


def test_opsec_hourly_budget_enforced(tmp_path):
    engine = OPSECPolicyEngine(
        {
            "web_testing": MethodPolicy(
                method="web_testing",
                max_requests_per_minute=100,
                max_concurrent=2,
                max_executions_per_hour=2,
            )
        }
    )
    for tool in ("ffuf", "gau"):
        ticket = engine.acquire("web_testing", tool)
        engine.release(ticket, "completed")

    try:
        engine.acquire("web_testing", "httpx")
        assert False, "expected hourly-budget block"
    except OPSECPolicyError as exc:
        assert "execution budget exceeded" in str(exc)
