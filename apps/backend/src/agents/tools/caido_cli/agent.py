from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from apps.backend.src.core.protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    Severity,
)


@dataclass(slots=True)
class _CrawlExecution:
    target: str
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    failure_type: str


class CaidoCliAgent:
    """Headless Caido CLI wrapper for lightweight endpoint and parameter discovery."""

    TOOL_NAME = "caido_cli"

    _NOISE_EXTENSIONS = {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".svg",
        ".ico",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".mp4",
        ".mp3",
        ".pdf",
    }

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        depth = max(1, int(opts.get("depth", 2)))
        max_requests = max(1, int(opts.get("max_requests", 120)))
        timeout_ms = max(500, int(opts.get("request_timeout_ms", 8000)))

        command = [
            "caido-cli",
            "crawl",
            "--headless",
            "--url",
            target,
            "--format",
            "jsonl",
            "--depth",
            str(depth),
            "--max-requests",
            str(max_requests),
            "--request-timeout",
            str(timeout_ms),
        ]
        user_agent = opts.get("user_agent")
        if isinstance(user_agent, str) and user_agent.strip():
            command += ["--user-agent", user_agent.strip()]
        return command

    def run(
        self,
        target: str,
        raw_output: str,
        options: dict[str, Any] | None = None,
        mission_id: str = "mission-001",
    ) -> KaisonResult:
        started_at = datetime.now(UTC)
        opts = options or {}

        max_targets = max(1, int(opts.get("max_targets", 40)))
        max_findings = max(1, int(opts.get("max_findings", 2000)))

        phase3_targets = self._extract_phase3_targets(raw_output, target, max_targets)
        if not phase3_targets:
            fallback = self._normalize_seed_target(target)
            if fallback:
                phase3_targets = [fallback]

        findings: list[KaisonFinding] = []
        crawl_errors: list[dict[str, Any]] = []
        discovered_signal_count = 0

        endpoint_seen: set[str] = set()
        parameter_seen: set[tuple[str, str]] = set()

        for crawl_target in phase3_targets:
            execution = self._run_crawl(crawl_target, opts)
            if execution.exit_code != 0:
                crawl_errors.append(
                    {
                        "target": crawl_target,
                        "exit_code": execution.exit_code,
                        "failure_type": execution.failure_type,
                        "stderr": execution.stderr[:400],
                        "command": execution.command,
                    }
                )
                continue

            for record in self._iter_crawl_jsonl(execution.stdout, crawl_target):
                endpoint = record["endpoint_url"]
                method = record.get("method", "GET")

                if endpoint not in endpoint_seen and len(findings) < max_findings:
                    endpoint_seen.add(endpoint)
                    findings.append(
                        KaisonFinding(
                            finding_type=FindingType.CONFIG,
                            value=f"endpoint:{endpoint}",
                            source_agent=self.TOOL_NAME,
                            confidence=record.get("confidence", 0.84),
                            severity=Severity.INFO,
                            raw_evidence={
                                "kind": "endpoint",
                                "endpoint": endpoint,
                                "method": method,
                                "status_code": record.get("status_code"),
                                "crawl_target": crawl_target,
                            },
                        )
                    )
                    discovered_signal_count += 1

                for param in record.get("parameters", []):
                    key = (endpoint, param)
                    if key in parameter_seen or len(findings) >= max_findings:
                        continue
                    parameter_seen.add(key)
                    findings.append(
                        KaisonFinding(
                            finding_type=FindingType.CONFIG,
                            value=f"parameter:{param}@{endpoint}",
                            source_agent=self.TOOL_NAME,
                            confidence=0.8,
                            severity=Severity.INFO,
                            raw_evidence={
                                "kind": "parameter",
                                "parameter_name": param,
                                "endpoint": endpoint,
                                "method": method,
                                "crawl_target": crawl_target,
                            },
                        )
                    )
                    discovered_signal_count += 1

                if len(findings) >= max_findings:
                    break

            if len(findings) >= max_findings:
                break

        if crawl_errors:
            error_summary: dict[str, int] = {}
            for err in crawl_errors:
                key = str(err.get("failure_type") or "execution_error")
                error_summary[key] = error_summary.get(key, 0) + 1

            findings.append(
                KaisonFinding(
                    finding_type=FindingType.CONFIG,
                    value="caido_cli:telemetry:crawl_failures",
                    source_agent=self.TOOL_NAME,
                    confidence=1.0,
                    severity=Severity.INFO,
                    raw_evidence={
                        "kind": "telemetry",
                        "error_count": len(crawl_errors),
                        "error_summary": error_summary,
                        "errors": crawl_errors[:25],
                    },
                )
            )

        status = "success"
        if discovered_signal_count > 0 and crawl_errors:
            status = "partial"
        elif discovered_signal_count == 0 and crawl_errors:
            status = "failure"
        elif discovered_signal_count == 0:
            status = "partial"

        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        return KaisonResult(
            mission_id=mission_id,
            source_agent=self.TOOL_NAME,
            status=status,
            target_context={
                "target": target,
                "phase3_targets": phase3_targets,
                "discovered_signal_count": discovered_signal_count,
                "crawl_error_count": len(crawl_errors),
                "max_findings": max_findings,
            },
            metadata=KaisonResultMetadata(
                started_at=started_at,
                ended_at=ended_at,
                runtime_ms=runtime_ms,
            ),
            findings=findings,
        )

    def _run_crawl(self, target: str, options: dict[str, Any]) -> _CrawlExecution:
        timeout_seconds = max(5, int(options.get("timeout_seconds", 120)))
        max_stdout_chars = max(2_000, int(options.get("max_stdout_chars", 1_000_000)))
        max_stderr_chars = max(2_000, int(options.get("max_stderr_chars", 16_000)))

        command: list[str] = []
        try:
            command = self._resolve_runtime_command(target, options)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                shell=False,
            )
            failure_type = (
                self._classify_failure(completed.stderr, completed.returncode)
                if completed.returncode != 0
                else "none"
            )
            return _CrawlExecution(
                target=target,
                command=command,
                exit_code=completed.returncode,
                stdout=(completed.stdout or "")[:max_stdout_chars],
                stderr=(completed.stderr or "")[:max_stderr_chars],
                failure_type=failure_type,
            )
        except subprocess.TimeoutExpired as exc:
            err = f"timeout after {timeout_seconds}s: {exc}"
            return _CrawlExecution(
                target=target,
                command=command,
                exit_code=124,
                stdout="",
                stderr=err[:max_stderr_chars],
                failure_type="timeout",
            )
        except FileNotFoundError as exc:
            message = str(exc)
            lowered = message.lower()
            failure_type = "docker_unavailable" if "docker_unavailable" in lowered else "missing_binary"
            return _CrawlExecution(
                target=target,
                command=command,
                exit_code=127,
                stdout="",
                stderr=message[:max_stderr_chars],
                failure_type=failure_type,
            )
        except OSError as exc:
            message = str(exc)
            return _CrawlExecution(
                target=target,
                command=command,
                exit_code=127,
                stdout="",
                stderr=message[:max_stderr_chars],
                failure_type=self._classify_failure(message, 127),
            )

    def _resolve_runtime_command(self, target: str, options: dict[str, Any]) -> list[str]:
        native = self.build_command(target, options)
        if shutil.which("caido-cli"):
            return native

        docker_enabled = bool(options.get("docker_fallback", True))
        if docker_enabled and shutil.which("docker"):
            image = str(options.get("docker_image", "ghcr.io/caido/caido-cli:latest"))
            return ["docker", "run", "--rm", "--network", "host", image] + native[1:]

        if docker_enabled and not shutil.which("docker"):
            raise FileNotFoundError("caido-cli missing and docker_unavailable for fallback")
        raise FileNotFoundError("caido-cli binary missing and docker fallback disabled")

    @staticmethod
    def _classify_failure(stderr: str, exit_code: int) -> str:
        text = (stderr or "").lower()
        if "connection refused" in text:
            return "connection_refused"
        if "timed out" in text or "timeout" in text or exit_code == 124:
            return "timeout"
        if "no such file" in text or "not found" in text or exit_code == 127:
            return "missing_binary"
        if "permission denied" in text:
            return "permission_denied"
        if "dns" in text or "name or service not known" in text:
            return "dns_resolution_error"
        return "execution_error"

    def _iter_crawl_jsonl(self, output: str, crawl_target: str) -> Iterable[dict[str, Any]]:
        seen: set[tuple[str, str]] = set()

        for line in output.splitlines():
            item = self._parse_line(line)
            if not item:
                continue

            endpoint = item["endpoint_url"]
            method = item.get("method", "GET")
            key = (endpoint, method)
            if key in seen:
                continue
            seen.add(key)

            ext = self._path_extension(endpoint)
            if ext in self._NOISE_EXTENSIONS:
                continue

            item["crawl_target"] = crawl_target
            yield item

    def _parse_line(self, line: str) -> dict[str, Any] | None:
        text = line.strip()
        if not text:
            return None

        payload: dict[str, Any]
        if text.startswith("{"):
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return None
        elif text.startswith(("http://", "https://")):
            payload = {"url": text}
        else:
            return None

        raw_url = self._coalesce(
            payload.get("url"),
            payload.get("endpoint"),
            payload.get("request_url"),
            payload.get("matched-at"),
            self._safe_get(payload, "request", "url"),
        )
        if not raw_url:
            return None

        endpoint_url = self._normalize_endpoint(str(raw_url))
        if not endpoint_url:
            return None

        method = str(
            self._coalesce(
                payload.get("method"),
                self._safe_get(payload, "request", "method"),
                "GET",
            )
        ).upper()

        status_raw = self._coalesce(
            payload.get("status"),
            payload.get("status_code"),
            self._safe_get(payload, "response", "status"),
            self._safe_get(payload, "response", "status_code"),
        )

        status_code: int | None = None
        if status_raw is not None:
            try:
                status_code = int(status_raw)
            except (TypeError, ValueError):
                status_code = None

        return {
            "endpoint_url": endpoint_url,
            "method": method,
            "status_code": status_code,
            "parameters": self._extract_parameter_names(payload, str(raw_url)),
            "confidence": 0.84,
        }

    def _extract_parameter_names(self, payload: dict[str, Any], raw_url: str) -> list[str]:
        names: set[str] = set()

        query = urlsplit(raw_url).query
        for name, _value in parse_qsl(query, keep_blank_values=True):
            clean = self._clean_param_name(name)
            if clean:
                names.add(clean)

        candidates: list[Any] = [
            payload.get("params"),
            payload.get("parameters"),
            payload.get("query_params"),
            self._safe_get(payload, "request", "params"),
            self._safe_get(payload, "request", "parameters"),
            self._safe_get(payload, "request", "query_params"),
        ]

        for candidate in candidates:
            if isinstance(candidate, dict):
                for key in candidate.keys():
                    clean = self._clean_param_name(str(key))
                    if clean:
                        names.add(clean)
            elif isinstance(candidate, list):
                for item in candidate:
                    if isinstance(item, dict):
                        value = self._coalesce(item.get("name"), item.get("key"), item.get("param"))
                        if value:
                            clean = self._clean_param_name(str(value))
                            if clean:
                                names.add(clean)
                    else:
                        clean = self._clean_param_name(str(item))
                        if clean:
                            names.add(clean)

        return sorted(names)[:80]

    def _extract_phase3_targets(self, raw_output: str, fallback_target: str, limit: int) -> list[str]:
        seen: set[str] = set()
        targets: list[str] = []

        def add(candidate: str) -> None:
            normalized = self._normalize_seed_target(candidate)
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            targets.append(normalized)

        stripped = raw_output.strip()
        if stripped:
            decoded = self._maybe_decode_json(stripped)
            if decoded is not None:
                for candidate in self._iter_url_candidates(decoded):
                    add(candidate)
            else:
                for line in stripped.splitlines():
                    token = line.strip()
                    if not token:
                        continue
                    nested = self._maybe_decode_json(token)
                    if nested is None:
                        add(token)
                    else:
                        for candidate in self._iter_url_candidates(nested):
                            add(candidate)

        if not targets:
            add(fallback_target)

        return targets[:limit]

    def _iter_url_candidates(self, value: Any) -> list[str]:
        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            merged: list[str] = []
            for item in value:
                merged.extend(self._iter_url_candidates(item))
            return merged

        if isinstance(value, dict):
            merged: list[str] = []
            for key in (
                "url",
                "urls",
                "target",
                "targets",
                "items",
                "input_urls",
                "live_urls",
                "endpoint",
                "endpoints",
            ):
                if key in value:
                    merged.extend(self._iter_url_candidates(value[key]))
            return merged

        return []

    @staticmethod
    def _normalize_seed_target(candidate: str) -> str | None:
        token = str(candidate).strip().strip('"').strip("'")
        if not token:
            return None
        if token.startswith(("{", "[")):
            return None

        parsed = urlsplit(token if "://" in token else f"https://{token}")
        if parsed.scheme not in {"http", "https"}:
            return None
        if not parsed.netloc:
            return None

        path = parsed.path or "/"
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))

    @staticmethod
    def _normalize_endpoint(raw_url: str) -> str | None:
        parsed = urlsplit(raw_url if "://" in raw_url else f"https://{raw_url}")
        if parsed.scheme not in {"http", "https"}:
            return None
        if not parsed.netloc:
            return None
        path = parsed.path or "/"
        return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))

    @staticmethod
    def _path_extension(url: str) -> str:
        path = urlsplit(url).path.lower().strip()
        if not path:
            return ""
        filename = path.rsplit("/", 1)[-1]
        if "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1]

    @staticmethod
    def _safe_get(data: dict[str, Any], key: str, nested_key: str) -> Any:
        nested = data.get(key)
        if isinstance(nested, dict):
            return nested.get(nested_key)
        return None

    @staticmethod
    def _coalesce(*values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            return value
        return None

    @staticmethod
    def _maybe_decode_json(text: str) -> Any | None:
        if not text or text[0] not in {"{", "["}:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _clean_param_name(name: str) -> str | None:
        token = name.strip()
        if not token:
            return None
        allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.$[]"
        cleaned = "".join(ch for ch in token if ch in allowed)
        return cleaned[:120] if cleaned else None
