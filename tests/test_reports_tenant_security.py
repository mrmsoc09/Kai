from __future__ import annotations

from uuid import uuid4

import pytest

from apps.backend.src.core.auth import ROLE_OPERATOR, create_access_token
from apps.backend.src.routers.reports import _safe_attachment_name


@pytest.fixture(autouse=True)
def isolated_report_engine(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "report_artifacts"))
    import apps.backend.src.core.report_engine as report_engine_mod

    report_engine_mod._ENGINE = None
    yield
    report_engine_mod._ENGINE = None


def _headers_for_tenant(tenant_id: str) -> dict[str, str]:
    token = create_access_token(
        subject=str(uuid4()),
        roles=[ROLE_OPERATOR],
        tenant_id=tenant_id,
    )
    return {"Authorization": f"Bearer {token}"}


def test_reports_endpoints_are_tenant_scoped(client):
    tenant_a = str(uuid4())
    tenant_b = str(uuid4())
    headers_a = _headers_for_tenant(tenant_a)
    headers_b = _headers_for_tenant(tenant_b)

    generate_response = client.post(
        "/reports/generate",
        json={
            "finding": {
                "title": "Reflected XSS in search",
                "vuln_type": "xss",
                "target": "app.example.com",
                "summary": "Script injection is reproducible in search parameter.",
                "confidence_score": 0.9,
            }
        },
        headers=headers_a,
    )
    assert generate_response.status_code == 200
    report_id = generate_response.json()["report"]["report_id"]

    list_a = client.get("/reports", headers=headers_a)
    assert list_a.status_code == 200
    assert list_a.json()["total"] == 1

    list_b = client.get("/reports", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    get_b = client.get(f"/reports/{report_id}", headers=headers_b)
    assert get_b.status_code == 404

    export_b = client.get(f"/reports/{report_id}/export?format=json", headers=headers_b)
    assert export_b.status_code == 404


def test_safe_attachment_name_sanitizes_header_value() -> None:
    filename = _safe_attachment_name('bad"\r\nname', ".json")
    assert filename.endswith(".json")
    assert '"' not in filename
    assert "\n" not in filename
    assert "\r" not in filename
