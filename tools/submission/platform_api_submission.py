from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
from typing import Any
from urllib import error, request
from uuid import uuid4


class PlatformAPIError(RuntimeError):
    """Raised when a platform API call fails irrecoverably."""


@dataclass(slots=True)
class PlatformSubmissionResult:
    platform: str
    status: str
    submission_id: str | None
    response_code: int | None
    error: str | None
    submitted_at: str
    raw_response: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status,
            "submission_id": self.submission_id,
            "response_code": self.response_code,
            "error": self.error,
            "submitted_at": self.submitted_at,
            "raw_response": self.raw_response,
        }


class PlatformAPISubmissionClient:
    """
    Submission client for HackerOne and Intigriti APIs.

    Behavior:
    - returns FAILED_CONFIGURATION when required credentials are absent
    - returns FAILED_HTTP when platform call fails
    - never reports success without platform confirmation (or explicit dry-run mode)
    """

    def __init__(
        self,
        *,
        h1_base_url: str = "https://api.hackerone.com/v1",
        intigriti_base_url: str = "https://api.intigriti.com/core/public",
        timeout_seconds: int = 25,
        dry_run: bool = False,
    ) -> None:
        self.h1_base_url = h1_base_url.rstrip("/")
        self.intigriti_base_url = intigriti_base_url.rstrip("/")
        self.timeout_seconds = max(5, int(timeout_seconds))
        self.dry_run = dry_run

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _normalize(platform: str) -> str:
        return (platform or "").strip().lower()

    def _http_json(
        self,
        *,
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> tuple[int, dict[str, Any]]:
        body = None
        req_headers = {"Accept": "application/json", **headers}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            req_headers["Content-Type"] = "application/json"

        req = request.Request(url=url, data=body, method=method.upper(), headers=req_headers)

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                status = int(resp.getcode())
                raw = resp.read().decode("utf-8", errors="replace")
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            try:
                payload_out = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                payload_out = {"raw": raw}
            return int(exc.code), payload_out
        except error.URLError as exc:
            raise PlatformAPIError(f"Network/API error calling {url}: {exc.reason}") from exc

        try:
            payload_out = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload_out = {"raw": raw}
        return status, payload_out

    @staticmethod
    def _status_from_http(code: int) -> str:
        if 200 <= code < 300:
            return "SUBMITTED"
        return "FAILED_HTTP"

    @staticmethod
    def _extract_submission_id(platform: str, payload: dict[str, Any]) -> str | None:
        keys = ["id", "submission_id", "report_id", "uuid"]
        for key in keys:
            if key in payload and payload[key]:
                return str(payload[key])

        # Common nested patterns.
        for branch in [payload.get("data"), payload.get("report"), payload.get("submission")]:
            if not isinstance(branch, dict):
                continue
            for key in keys:
                if key in branch and branch[key]:
                    return str(branch[key])

        if platform == "hackerone":
            attrs = payload.get("data", {}).get("attributes", {}) if isinstance(payload.get("data"), dict) else {}
            if isinstance(attrs, dict) and attrs.get("id"):
                return str(attrs["id"])

        return None

    def _h1_headers(self) -> tuple[dict[str, str], str | None]:
        token = os.getenv("H1_API_TOKEN") or os.getenv("HACKERONE_API_TOKEN")
        if not token:
            return {}, "Missing H1/HackerOne API token (H1_API_TOKEN or HACKERONE_API_TOKEN)."
        return {"Authorization": f"Bearer {token}"}, None

    def _intigriti_headers(self) -> tuple[dict[str, str], str | None]:
        token = os.getenv("INTIGRITI_API_TOKEN")
        if not token:
            return {}, "Missing Intigriti API token (INTIGRITI_API_TOKEN)."
        return {"Authorization": f"Bearer {token}"}, None

    @staticmethod
    def _h1_payload(finding: dict[str, Any], screen_recording_path: str | None) -> dict[str, Any]:
        return {
            "title": finding.get("title"),
            "vulnerability_information": finding.get("description"),
            "impact": finding.get("impact"),
            "reproduction_steps": finding.get("poc_steps") or finding.get("reproduction_steps") or [],
            "severity_rating": (
                finding.get("severity", {}).get("severity_level")
                if isinstance(finding.get("severity"), dict)
                else finding.get("severity")
            ),
            "target": finding.get("target_endpoint") or finding.get("target") or finding.get("asset"),
            "screen_recording": screen_recording_path,
            "kai_metadata": {
                "finding_id": finding.get("finding_id") or finding.get("id"),
                "in_scope_confirmed": finding.get("in_scope_confirmed", False),
            },
        }

    @staticmethod
    def _intigriti_payload(finding: dict[str, Any], screen_recording_path: str | None) -> dict[str, Any]:
        return {
            "title": finding.get("title"),
            "summary": finding.get("description"),
            "severity": (
                finding.get("severity", {}).get("severity_level")
                if isinstance(finding.get("severity"), dict)
                else finding.get("severity")
            ),
            "impact": finding.get("impact"),
            "steps_to_reproduce": finding.get("poc_steps") or finding.get("reproduction_steps") or [],
            "target": finding.get("target_endpoint") or finding.get("target") or finding.get("asset"),
            "screen_recording": screen_recording_path,
            "kai_metadata": {
                "finding_id": finding.get("finding_id") or finding.get("id"),
                "in_scope_confirmed": finding.get("in_scope_confirmed", False),
            },
        }

    def submit(
        self,
        *,
        platform: str,
        finding: dict[str, Any],
        screen_recording_path: str | None = None,
    ) -> dict[str, Any]:
        target = self._normalize(platform)
        if target in {"h1", "hackerone"}:
            return self.submit_to_hackerone(finding=finding, screen_recording_path=screen_recording_path)
        if target in {"intigriti", "inti"}:
            return self.submit_to_intigriti(finding=finding, screen_recording_path=screen_recording_path)
        raise PlatformAPIError(f"Unsupported submission platform: {platform}")

    def submit_to_hackerone(self, *, finding: dict[str, Any], screen_recording_path: str | None = None) -> dict[str, Any]:
        platform = "hackerone"
        payload = self._h1_payload(finding, screen_recording_path)
        if self.dry_run:
            return PlatformSubmissionResult(
                platform=platform,
                status="QUEUED_DRY_RUN",
                submission_id=f"dryrun-h1-{uuid4().hex[:12]}",
                response_code=202,
                error=None,
                submitted_at=self._now(),
                raw_response={"payload_preview": payload},
            ).as_dict()

        headers, config_error = self._h1_headers()
        if config_error:
            return PlatformSubmissionResult(
                platform=platform,
                status="FAILED_CONFIGURATION",
                submission_id=None,
                response_code=None,
                error=config_error,
                submitted_at=self._now(),
                raw_response={},
            ).as_dict()

        endpoint = f"{self.h1_base_url}/reports"
        code, response_payload = self._http_json(method="POST", url=endpoint, payload=payload, headers=headers)
        status = self._status_from_http(code)
        submission_id = self._extract_submission_id(platform, response_payload)
        err = None if status == "SUBMITTED" else f"HackerOne API returned HTTP {code}"

        return PlatformSubmissionResult(
            platform=platform,
            status=status,
            submission_id=submission_id,
            response_code=code,
            error=err,
            submitted_at=self._now(),
            raw_response=response_payload,
        ).as_dict()

    def submit_to_intigriti(self, *, finding: dict[str, Any], screen_recording_path: str | None = None) -> dict[str, Any]:
        platform = "intigriti"
        payload = self._intigriti_payload(finding, screen_recording_path)
        if self.dry_run:
            return PlatformSubmissionResult(
                platform=platform,
                status="QUEUED_DRY_RUN",
                submission_id=f"dryrun-inti-{uuid4().hex[:12]}",
                response_code=202,
                error=None,
                submitted_at=self._now(),
                raw_response={"payload_preview": payload},
            ).as_dict()

        headers, config_error = self._intigriti_headers()
        if config_error:
            return PlatformSubmissionResult(
                platform=platform,
                status="FAILED_CONFIGURATION",
                submission_id=None,
                response_code=None,
                error=config_error,
                submitted_at=self._now(),
                raw_response={},
            ).as_dict()

        endpoint = f"{self.intigriti_base_url}/reports"
        code, response_payload = self._http_json(method="POST", url=endpoint, payload=payload, headers=headers)
        status = self._status_from_http(code)
        submission_id = self._extract_submission_id(platform, response_payload)
        err = None if status == "SUBMITTED" else f"Intigriti API returned HTTP {code}"

        return PlatformSubmissionResult(
            platform=platform,
            status=status,
            submission_id=submission_id,
            response_code=code,
            error=err,
            submitted_at=self._now(),
            raw_response=response_payload,
        ).as_dict()

    def poll_status(self, *, platform: str, submission_id: str) -> dict[str, Any]:
        target = self._normalize(platform)
        if target in {"h1", "hackerone"}:
            headers, config_error = self._h1_headers()
            if config_error:
                return {
                    "platform": "hackerone",
                    "submission_id": submission_id,
                    "status": "FAILED_CONFIGURATION",
                    "error": config_error,
                }
            endpoint = f"{self.h1_base_url}/reports/{submission_id}"
            code, payload = self._http_json(method="GET", url=endpoint, payload=None, headers=headers)
            status = "OK" if 200 <= code < 300 else "FAILED_HTTP"
            platform_status = payload.get("status") or payload.get("data", {}).get("attributes", {}).get("state")
            return {
                "platform": "hackerone",
                "submission_id": submission_id,
                "status": status,
                "platform_status": platform_status,
                "response_code": code,
                "payload": payload,
            }

        if target in {"intigriti", "inti"}:
            headers, config_error = self._intigriti_headers()
            if config_error:
                return {
                    "platform": "intigriti",
                    "submission_id": submission_id,
                    "status": "FAILED_CONFIGURATION",
                    "error": config_error,
                }
            endpoint = f"{self.intigriti_base_url}/reports/{submission_id}"
            code, payload = self._http_json(method="GET", url=endpoint, payload=None, headers=headers)
            status = "OK" if 200 <= code < 300 else "FAILED_HTTP"
            platform_status = payload.get("status") or payload.get("data", {}).get("status")
            return {
                "platform": "intigriti",
                "submission_id": submission_id,
                "status": status,
                "platform_status": platform_status,
                "response_code": code,
                "payload": payload,
            }

        raise PlatformAPIError(f"Unsupported status polling platform: {platform}")


__all__ = ["PlatformAPISubmissionClient", "PlatformAPIError", "PlatformSubmissionResult"]
