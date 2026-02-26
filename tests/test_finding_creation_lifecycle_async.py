from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from apps.backend.src.main import app


@pytest.mark.asyncio
async def test_finding_creation_lifecycle_async():
    run_id = f"async-finding-{uuid.uuid4()}"

    transport = ASGITransport(app=app)
    headers = {"Authorization": "Bearer devtoken"}
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        ingest = await client.post(
            "/findings/ingest/tool-result",
            json={
                "run_id": run_id,
                "tool_id": "nuclei",
                "status": "completed",
                "output": {"matched": 1},
                "target": "example.com",
                "severity": "high",
                "metadata": {"repro_command": "nuclei -u https://example.com"},
            },
            headers=headers,
        )
        assert ingest.status_code == 200, ingest.text
        ingest_body = ingest.json()
        assert ingest_body.get("ok") is True

        findings = (ingest_body.get("run") or {}).get("findings") or []
        assert findings, "expected at least one finding after ingest"
        finding_id = findings[0]["id"]

        blocked = await client.post(
            "/findings/set_status",
            json={
                "run_id": run_id,
                "finding_id": finding_id,
                "status": "VALIDATED",
            },
            headers=headers,
        )
        assert blocked.status_code == 409, blocked.text
        assert "recording_required" in blocked.text

        approved = await client.post(
            "/findings/set_status",
            json={
                "run_id": run_id,
                "finding_id": finding_id,
                "status": "VALIDATED",
                "recording_path": f"artifacts/recordings/{run_id}/seg_0000.mp4",
            },
            headers=headers,
        )
        assert approved.status_code == 200, approved.text
        approved_body = approved.json()
        assert approved_body.get("ok") is True

        run = await client.get(f"/runs/{run_id}")
        assert run.status_code == 200, run.text
        run_body = run.json()
        run_findings = run_body.get("findings") or []
        assert run_findings and run_findings[0]["status"] == "VALIDATED"
