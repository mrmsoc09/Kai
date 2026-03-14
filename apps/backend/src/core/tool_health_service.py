"""
Tool health dashboard service.

Checks installation status, credential readiness, wrapper smoke-test status,
execution mode, and recent failure reasons for every tool in the catalog.
Synchronous by design so it works both from the CLI and from API handlers
(which run it in a thread-pool via asyncio.to_thread).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .helpers import artifacts_root, utcnow, workflow_output_root
from .tool_registry_catalog import ToolCatalogEntry, list_catalog_entries
from ..models.campaign import ToolExecution

# How many recent telemetry lines to consider per tool.
_DEFAULT_TELEMETRY_WINDOW = 20
# Subprocess timeout (seconds) for install_verification_cmd.
_DEFAULT_INSTALL_TIMEOUT = 8

_ALIAS_SUFFIXES = ("_scan", "_enum", "_probe", "_quick", "_host")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return utcnow()


def _telemetry_path() -> Path:
    return artifacts_root() / "telemetry" / "tool_runs.jsonl"


def _install_report_path() -> Path:
    return workflow_output_root() / "reports" / "tool_install_verification.json"


def _normalize_tool_name(name: str) -> str:
    from .tool_adapters_bugbounty import REGISTRY_TOOL_ID_ALIASES

    value = (name or "").strip().lower()
    if not value:
        return value
    reverse_aliases = {v.lower(): k.lower() for k, v in REGISTRY_TOOL_ID_ALIASES.items()}
    if value in reverse_aliases:
        return reverse_aliases[value]
    for suffix in _ALIAS_SUFFIXES:
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def _load_install_report_cache() -> dict[str, dict[str, Any]]:
    path = _install_report_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        tool_name = _normalize_tool_name(str(item.get("tool") or ""))
        if not tool_name:
            continue
        out[tool_name] = item
    return out


def _load_recent_telemetry(tool_name: str, *, window: int) -> list[dict[str, Any]]:
    """Return up to *window* recent telemetry entries for *tool_name*.

    The JSONL file may be large; we read from the end using a simple tail
    strategy (read last 256 KB, parse lines, filter by tool).
    """
    path = _telemetry_path()
    if not path.exists():
        return []

    try:
        size = path.stat().st_size
        read_bytes = min(size, 256 * 1024)
        with path.open("rb") as fh:
            if read_bytes < size:
                fh.seek(-read_bytes, 2)
                fh.readline()  # skip partial first line
            raw = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return []

    entries: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict):
            continue
        # Match on tool_id, tool_name, or name field.
        record_tool = str(
            record.get("tool_id") or record.get("tool_name") or record.get("name") or ""
        ).lower()
        if record_tool in (tool_name.lower(), f"{tool_name.lower()}_scan",
                           f"{tool_name.lower()}_enum", f"{tool_name.lower()}_probe"):
            entries.append(record)

    # Keep the last *window* entries (JSONL is written in chronological order).
    return entries[-window:]


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def check_runtime_presence(entry: ToolCatalogEntry) -> dict[str, Any]:
    binary_name = entry.binary_path or entry.name
    binary_resolved = shutil.which(binary_name) if binary_name else None
    docker_binary = shutil.which("docker")
    docker_available = docker_binary is not None
    image_configured = bool(entry.container_image)

    mode = entry.execution_mode
    if mode in {"api", "hook"}:
        return {
            "status": "not_required",
            "binary_present": False,
            "binary_path": None,
            "container_image_configured": image_configured,
            "docker_available": docker_available,
            "detail": f"{mode} execution mode does not require local binary/image presence",
        }
    if binary_resolved:
        return {
            "status": "present",
            "binary_present": True,
            "binary_path": binary_resolved,
            "container_image_configured": image_configured,
            "docker_available": docker_available,
            "detail": f"binary resolved: {binary_resolved}",
        }
    if mode in {"docker", "optional"} and image_configured and docker_available:
        return {
            "status": "present",
            "binary_present": False,
            "binary_path": None,
            "container_image_configured": True,
            "docker_available": True,
            "detail": f"docker runtime present; image configured: {entry.container_image}",
        }
    return {
        "status": "missing",
        "binary_present": False,
        "binary_path": None,
        "container_image_configured": image_configured,
        "docker_available": docker_available,
        "detail": "missing required runtime binary/image",
    }


def check_install(
    entry: ToolCatalogEntry,
    *,
    timeout: int = _DEFAULT_INSTALL_TIMEOUT,
    cached_report: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run install_verification_cmd and return a raw check dict."""
    now = _now()
    if cached_report:
        cached = cached_report.get(_normalize_tool_name(entry.name))
        if cached is not None:
            ok = bool(cached.get("ok"))
            return {
                "status": "ok" if ok else "missing",
                "detail": str(cached.get("output") or "").strip()[:300],
                "checked_at": now,
                "source": "cached_report",
            }

    if not entry.install_verification_cmd:
        return {
            "status": "skipped",
            "detail": "no install_verification_cmd configured",
            "checked_at": now,
            "source": "live_check",
        }

    cmd = entry.install_verification_cmd
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        ok = completed.returncode == 0
        output = (completed.stdout or completed.stderr or "").strip()[:300]
        if ok:
            return {
                "status": "ok",
                "detail": output,
                "checked_at": now,
                "source": "live_check",
            }
        return {
            "status": "missing",
            "detail": f"returncode={completed.returncode} {output}",
            "checked_at": now,
            "source": "live_check",
        }
    except FileNotFoundError:
        binary = cmd[0] if cmd else "(none)"
        return {
            "status": "missing",
            "detail": f"binary not found: {binary}",
            "checked_at": now,
            "source": "live_check",
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "detail": f"install_verification_cmd timed out after {timeout}s",
            "checked_at": now,
            "source": "live_check",
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "status": "error",
            "detail": str(exc),
            "checked_at": now,
            "source": "live_check",
        }


def check_credentials(entry: ToolCatalogEntry) -> dict[str, Any]:
    """Check whether required environment variables are present."""
    required = list(entry.api_keys_required)
    if not required:
        return {
            "status": "not_required",
            "required_keys": [],
            "present_keys": [],
            "missing_keys": [],
            "detail": "",
        }

    present: list[str] = []
    missing: list[str] = []
    for key in required:
        val = os.getenv(key, "").strip()
        if val:
            present.append(key)
        else:
            missing.append(key)

    if missing:
        return {
            "status": "missing",
            "required_keys": required,
            "present_keys": present,
            "missing_keys": missing,
            "detail": f"{len(missing)} of {len(required)} required key(s) absent from environment",
        }
    return {
        "status": "ready",
        "required_keys": required,
        "present_keys": present,
        "missing_keys": [],
        "detail": f"all {len(required)} required key(s) present",
    }


def check_wrapper(entry: ToolCatalogEntry) -> dict[str, Any]:
    """Verify the tool adapter is registered in the global tool registry.

    Intentionally avoids importing `initialize_default_tools` to keep this
    check idempotent and safe; instead it queries the already-loaded state.
    """
    from .tools import get_registry
    from .tool_adapters_bugbounty import REGISTRY_TOOL_ID_ALIASES

    registry = get_registry()
    # The catalog name may map to a different registry ID.
    registry_id = REGISTRY_TOOL_ID_ALIASES.get(entry.name, entry.name)

    tool = registry.get(registry_id)
    if tool is None:
        # Try a few common suffixes used in the bugbounty adapters.
        for suffix in ("_scan", "_enum", "_probe", "_quick", "_host"):
            candidate = registry.get(f"{entry.name}{suffix}")
            if candidate is not None:
                tool = candidate
                registry_id = f"{entry.name}{suffix}"
                break

    if tool is None:
        return {
            "status": "not_registered",
            "registry_tool_id": None,
            "detail": f"no adapter registered under id '{registry_id}' (catalog tool not yet loaded?)",
            "tool": None,
        }

    try:
        schema = tool.get_schema()
        if not isinstance(schema, dict) or "name" not in schema:
            return {
                "status": "failed",
                "registry_tool_id": registry_id,
                "detail": "get_schema() returned invalid structure",
                "tool": tool,
            }
    except Exception as exc:
        return {
            "status": "failed",
            "registry_tool_id": registry_id,
            "detail": f"get_schema() raised: {exc}",
            "tool": tool,
        }

    return {
        "status": "ok",
        "registry_tool_id": registry_id,
        "detail": f"registered as '{registry_id}' (tier={tool.autonomy_tier.name})",
        "tool": tool,
    }


def check_safe_mode_compatibility(entry: ToolCatalogEntry) -> dict[str, Any]:
    safety = entry.safety_classification.lower()
    compatible = safety not in {"intrusive", "manual_only"}
    return {
        "compatible": compatible,
        "requires_override": not compatible,
        "detail": (
            "safe-mode compatible"
            if compatible
            else f"safe_mode blocks {entry.name} ({entry.safety_classification})"
        ),
    }


def check_wrapper_smoke(
    entry: ToolCatalogEntry,
    *,
    wrapper_result: dict[str, Any],
    run_smoke_tests: bool,
) -> dict[str, Any]:
    from .tool_adapters.base_adapter import execute_registered_tool
    from .workflow_normalizer import normalize_tool_output

    if not run_smoke_tests:
        return {"status": "skipped", "detail": "smoke tests disabled by caller"}

    if wrapper_result.get("status") != "ok":
        return {
            "status": "not_registered",
            "detail": "wrapper not available for smoke test",
        }

    tool = wrapper_result.get("tool")
    if tool is None:
        return {"status": "not_registered", "detail": "registered tool object unavailable"}

    # Lightweight parser check through canonical normalizer.
    try:
        normalized = normalize_tool_output(
            run_id="tool-health-smoke",
            tool_name=entry.name,
            target="example.com",
            output={},
        )
        parser_ok = isinstance(normalized, dict)
    except Exception as exc:
        return {"status": "failed", "detail": f"output parser smoke failed: {exc}"}

    if not parser_ok:
        return {"status": "failed", "detail": "output parser smoke returned invalid structure"}

    registry_id = str(wrapper_result.get("registry_tool_id") or "")
    if registry_id not in {"k1_correlation", "k1_priority_ranking"}:
        return {
            "status": "skipped",
            "detail": "invocation smoke skipped for external wrapper",
        }

    params: dict[str, Any] = {"target": "example.com", "run_id": "tool-health-smoke"}
    if registry_id in {"k1_correlation", "k1_priority_ranking"}:
        params["signals"] = []

    try:
        result = execute_registered_tool(tool, params)
        if not hasattr(result, "to_dict"):
            return {"status": "failed", "detail": "wrapper returned non-standard result object"}
        payload = result.to_dict()
        if not isinstance(payload, dict) or "status" not in payload:
            return {"status": "failed", "detail": "wrapper result serialization invalid"}
    except Exception as exc:
        return {"status": "failed", "detail": f"wrapper invocation smoke failed: {exc}"}

    return {"status": "ok", "detail": "wrapper invocation + parser smoke passed"}


def check_policy(entry: ToolCatalogEntry) -> bool:
    """Return True if the tool is enabled according to toolpack policy."""
    from .toolpacks import get_toolpack_manager
    from .tool_adapters_bugbounty import REGISTRY_TOOL_ID_ALIASES

    registry_id = REGISTRY_TOOL_ID_ALIASES.get(entry.name, entry.name)
    try:
        manager = get_toolpack_manager()
        return manager.is_adapter_enabled(registry_id)
    except Exception:
        # Toolpack policy unavailable — treat as enabled (fail-open for health checks).
        return True


def summarize_telemetry(entries: list[dict[str, Any]], *, window: int) -> dict[str, Any]:
    """Aggregate a list of raw telemetry records into a summary dict."""
    if not entries:
        return {
            "window_size": window,
            "total": 0,
            "completed": 0,
            "failed": 0,
            "failure_rate": 0.0,
            "last_status": None,
            "last_executed_at": None,
            "failure_reasons": [],
        }

    total = len(entries)
    completed = sum(
        1 for e in entries
        if str(e.get("status", "")).upper() in {"COMPLETED", "SUCCESS", "OK"}
    )
    failed = sum(
        1 for e in entries
        if str(e.get("status", "")).upper() in {"FAILED", "FAILURE", "ERROR"}
    )
    failure_rate = round(failed / total, 3) if total else 0.0

    last = entries[-1]
    last_status = str(last.get("status") or last.get("tool_status") or "").upper() or None
    last_executed_at = str(last.get("timestamp") or last.get("ended_at") or "") or None

    # Collect deduplicated failure reasons (newest first).
    seen: set[str] = set()
    failure_reasons: list[str] = []
    for entry in reversed(entries):
        status = str(entry.get("status") or entry.get("tool_status") or "").upper()
        if status not in {"FAILED", "FAILURE", "ERROR"}:
            continue
        reason = str(
            entry.get("error") or entry.get("error_message") or entry.get("stderr_summary") or ""
        ).strip()
        if reason and reason not in seen:
            seen.add(reason)
            failure_reasons.append(reason)
        if len(failure_reasons) >= 5:
            break

    return {
        "window_size": window,
        "total": total,
        "completed": completed,
        "failed": failed,
        "failure_rate": failure_rate,
        "last_status": last_status,
        "last_executed_at": last_executed_at,
        "failure_reasons": failure_reasons,
    }


# ---------------------------------------------------------------------------
# Overall health classification
# ---------------------------------------------------------------------------


_HEALTHY_INSTALL = {"ok"}
_HEALTHY_CREDS = {"ready", "not_required"}
_HEALTHY_WRAPPER = {"ok", "skipped", "not_registered"}  # not_registered ≠ broken


def classify_health(
    install_status: str,
    runtime_status: str,
    cred_status: str,
    wrapper_status: str,
    smoke_status: str,
    policy_enabled: bool,
    recent: dict[str, Any],
) -> str:
    """Return one of: healthy, degraded, unavailable, unchecked."""
    if not policy_enabled:
        return "unavailable"
    if install_status == "missing":
        return "unavailable"
    if runtime_status == "missing":
        return "unavailable"
    if install_status == "skipped" and wrapper_status == "not_registered" and recent["total"] == 0:
        return "unchecked"
    if install_status in {"error"}:
        return "degraded"
    if cred_status == "missing":
        return "degraded"
    if wrapper_status == "failed":
        return "degraded"
    if smoke_status == "failed":
        return "degraded"
    if recent["failure_rate"] >= 0.5 and recent["total"] >= 3:
        return "degraded"
    return "healthy"


# ---------------------------------------------------------------------------
# Per-tool and full dashboard check
# ---------------------------------------------------------------------------


def check_tool(
    entry: ToolCatalogEntry,
    *,
    install_timeout: int = _DEFAULT_INSTALL_TIMEOUT,
    telemetry_window: int = _DEFAULT_TELEMETRY_WINDOW,
    run_smoke_tests: bool = False,
    cached_install_report: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run all health checks for a single catalog entry and return a raw dict."""
    now = _now()

    runtime_presence = check_runtime_presence(entry)
    install = check_install(
        entry,
        timeout=install_timeout,
        cached_report=cached_install_report,
    )
    credentials = check_credentials(entry)
    wrapper = check_wrapper(entry)
    smoke = check_wrapper_smoke(
        entry,
        wrapper_result=wrapper,
        run_smoke_tests=run_smoke_tests,
    )
    policy_enabled = check_policy(entry)
    safe_mode = check_safe_mode_compatibility(entry)

    raw_telemetry = _load_recent_telemetry(entry.name, window=telemetry_window)
    recent = summarize_telemetry(raw_telemetry, window=telemetry_window)

    overall = classify_health(
        install_status=install["status"],
        runtime_status=runtime_presence["status"],
        cred_status=credentials["status"],
        wrapper_status=wrapper["status"],
        smoke_status=smoke["status"],
        policy_enabled=policy_enabled,
        recent=recent,
    )
    required_present = (
        len(credentials["missing_keys"]) == 0 if credentials["required_keys"] else True
    )
    last_failure_reason = (
        recent["failure_reasons"][0] if recent.get("failure_reasons") else None
    )
    enabled_status = (
        "enabled"
        if policy_enabled and entry.enabled_by_default
        else "disabled_by_policy"
        if not policy_enabled
        else "disabled_by_default"
    )

    return {
        "tool_name": entry.name,
        "name": entry.name,  # compatibility
        "category": entry.category,
        "enabled_status": enabled_status,
        "enabled": policy_enabled and entry.enabled_by_default,
        "execution_mode": entry.execution_mode,
        "safety_classification": entry.safety_classification,
        "enabled_by_default": entry.enabled_by_default,
        "policy_enabled": policy_enabled,
        "tags": entry.tags,
        "api_keys_required": entry.api_keys_required,
        "timeout_seconds": entry.timeout_seconds,
        "binary_or_image_presence": runtime_presence,
        "install_verification_status": install["status"],
        "required_environment_variables_present": required_present,
        "credential_status": credentials["status"],
        "wrapper_smoke_test_status": smoke["status"],
        "safe_mode_compatibility": safe_mode,
        "last_execution_status": recent.get("last_status"),
        "last_failure_reason": last_failure_reason,
        "last_execution_at": recent.get("last_executed_at"),
        "install": install,
        "credentials": credentials,
        "wrapper": {k: v for k, v in wrapper.items() if k != "tool"},
        "smoke_test": smoke,
        "recent_executions": recent,
        "overall_health": overall,
        "checked_at": now,
    }


def _build_summary(reports: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = defaultdict(int)
    for r in reports:
        counts[r["overall_health"]] += 1
    missing_binary = sum(
        1 for r in reports if r["binary_or_image_presence"]["status"] == "missing"
    )
    missing_credentials = sum(1 for r in reports if r["credential_status"] == "missing")
    failed_verification = sum(
        1
        for r in reports
        if r["install_verification_status"] in {"missing", "error"}
    )
    return {
        "total": len(reports),
        "healthy": counts["healthy"],
        "degraded": counts["degraded"],
        "unavailable": counts["unavailable"],
        "unchecked": counts["unchecked"],
        "total_tools": len(reports),
        "healthy_tools": counts["healthy"],
        "tools_missing_binary": missing_binary,
        "tools_missing_credentials": missing_credentials,
        "tools_with_failed_verification": failed_verification,
    }


def build_dashboard(
    *,
    tool_names: list[str] | None = None,
    categories: list[str] | None = None,
    enabled_only: bool = False,
    install_timeout: int = _DEFAULT_INSTALL_TIMEOUT,
    telemetry_window: int = _DEFAULT_TELEMETRY_WINDOW,
    run_smoke_tests: bool = False,
    use_cached_install_report: bool = True,
) -> dict[str, Any]:
    """Run health checks for all (or filtered) catalog entries.

    Parameters
    ----------
    tool_names:
        If provided, only check these catalog tool names.
    categories:
        If provided, only check tools in these categories.
    enabled_only:
        If True, skip tools with ``enabled_by_default=False``.
    install_timeout:
        Seconds each install_verification_cmd subprocess may run.
    telemetry_window:
        Number of recent telemetry lines to inspect per tool.
    """
    entries = list_catalog_entries(enabled_only=enabled_only)
    if tool_names:
        names_lower = {n.lower() for n in tool_names}
        entries = [e for e in entries if e.name in names_lower]
    if categories:
        cats_lower = {c.lower() for c in categories}
        entries = [e for e in entries if e.category in cats_lower]

    cached_report = _load_install_report_cache() if use_cached_install_report else None
    reports: list[dict[str, Any]] = []
    for entry in entries:
        reports.append(
            check_tool(
                entry,
                install_timeout=install_timeout,
                telemetry_window=telemetry_window,
                run_smoke_tests=run_smoke_tests,
                cached_install_report=cached_report,
            )
        )

    # Per-category summaries.
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in reports:
        by_cat[r["category"]].append(r)
    by_category = {cat: _build_summary(reps) for cat, reps in sorted(by_cat.items())}

    return {
        "generated_at": _now(),
        "install_timeout_seconds": install_timeout,
        "telemetry_window": telemetry_window,
        "smoke_tests_enabled": run_smoke_tests,
        "summary": _build_summary(reports),
        "by_category": by_category,
        "tools": reports,
    }


def write_dashboard_report(
    dashboard: dict[str, Any],
    *,
    report_path: str | Path | None = None,
) -> str:
    if report_path is None:
        path = workflow_output_root() / "reports" / "tool_health_report.json"
    else:
        path = Path(report_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dashboard, indent=2, default=str), encoding="utf-8")
    return str(path)


async def load_last_execution_records(db: AsyncSession, *, limit: int = 2000) -> dict[str, dict[str, Any]]:
    result = await db.execute(
        select(ToolExecution).order_by(
            ToolExecution.ended_at.desc().nullslast(),
            ToolExecution.created_at.desc(),
        ).limit(limit)
    )
    rows = list(result.scalars().all())
    output: dict[str, dict[str, Any]] = {}
    for row in rows:
        normalized = _normalize_tool_name(str(row.tool_name or ""))
        if not normalized or normalized in output:
            continue
        status = row.status.value if hasattr(row.status, "value") else str(row.status)
        output[normalized] = {
            "status": status,
            "failure_reason": row.error_message or row.stderr_summary,
            "executed_at": (
                (row.ended_at or row.updated_at or row.created_at).isoformat()
                if (row.ended_at or row.updated_at or row.created_at)
                else None
            ),
            "source": "db",
        }
    return output


def apply_execution_history(
    dashboard: dict[str, Any],
    execution_records: dict[str, dict[str, Any]],
) -> None:
    for item in dashboard.get("tools", []):
        name = _normalize_tool_name(str(item.get("tool_name") or item.get("name") or ""))
        if not name:
            continue
        record = execution_records.get(name)
        if not record:
            continue
        item["last_execution_status"] = record.get("status") or item.get("last_execution_status")
        if record.get("failure_reason"):
            item["last_failure_reason"] = record.get("failure_reason")
        if record.get("executed_at"):
            item["last_execution_at"] = record.get("executed_at")
