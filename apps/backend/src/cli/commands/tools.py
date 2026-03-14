"""
Tool command group for catalog health and readiness checks.
"""

from __future__ import annotations

import json

import click

from ...core.tool_health_service import build_dashboard, write_dashboard_report
from ..ui import (
    console,
    create_status_panel,
    create_table,
    print_error,
    print_header,
    print_info,
    print_success,
)


@click.group()
def tools() -> None:
    """Tool catalog and readiness operations."""
    pass


@tools.command("health")
@click.option("--enabled-only", is_flag=True, help="Check only enabled-by-default tools")
@click.option("--smoke-tests", is_flag=True, help="Run lightweight wrapper smoke tests")
@click.option("--category", "categories", multiple=True, help="Filter by tool category")
@click.option("--tool", "tool_names", multiple=True, help="Filter by tool name")
@click.option("--install-timeout", default=8, type=int, show_default=True, help="Install check timeout seconds")
@click.option("--telemetry-window", default=20, type=int, show_default=True, help="Recent execution window size")
@click.option("--json-output", is_flag=True, help="Print full health dashboard JSON")
@click.option("--write-report", is_flag=True, help="Write report to output/reports/tool_health_report.json")
@click.option("--report-file", type=click.Path(), help="Optional report path override")
def tools_health(
    enabled_only: bool,
    smoke_tests: bool,
    categories: tuple[str, ...],
    tool_names: tuple[str, ...],
    install_timeout: int,
    telemetry_window: int,
    json_output: bool,
    write_report: bool,
    report_file: str | None,
) -> None:
    """Run tool health checks and print summary or JSON output."""
    print_header("Tool Health", "Catalog-backed tool readiness report")
    try:
        dashboard = build_dashboard(
            enabled_only=enabled_only,
            run_smoke_tests=smoke_tests,
            categories=list(categories) or None,
            tool_names=list(tool_names) or None,
            install_timeout=max(1, install_timeout),
            telemetry_window=max(1, telemetry_window),
            use_cached_install_report=True,
        )
    except Exception as exc:
        print_error(f"Tool health check failed: {exc}")
        raise SystemExit(2) from exc

    summary = dashboard.get("summary", {})
    console.print(
        create_status_panel(
            "Summary",
            {
                "Total Tools": summary.get("total_tools", summary.get("total", 0)),
                "Healthy": summary.get("healthy_tools", summary.get("healthy", 0)),
                "Degraded": summary.get("degraded", 0),
                "Unavailable": summary.get("unavailable", 0),
                "Missing Binary/Image": summary.get("tools_missing_binary", 0),
                "Missing Credentials": summary.get("tools_missing_credentials", 0),
                "Failed Verification": summary.get("tools_with_failed_verification", 0),
            },
            style="green" if summary.get("degraded", 0) == 0 and summary.get("unavailable", 0) == 0 else "yellow",
        )
    )

    rows: list[list[str]] = []
    for item in dashboard.get("tools", []):
        rows.append(
            [
                str(item.get("tool_name") or item.get("name") or ""),
                str(item.get("category") or ""),
                str(item.get("execution_mode") or ""),
                str(item.get("enabled_status") or ""),
                str((item.get("binary_or_image_presence") or {}).get("status") or ""),
                str(item.get("install_verification_status") or ""),
                str(item.get("credential_status") or ""),
                str(item.get("wrapper_smoke_test_status") or ""),
                "yes" if bool((item.get("safe_mode_compatibility") or {}).get("compatible")) else "no",
                str(item.get("last_execution_status") or "-"),
                str(item.get("overall_health") or ""),
            ]
        )
    if rows:
        console.print(
            create_table(
                "Tool Health",
                [
                    "Tool",
                    "Category",
                    "Mode",
                    "Enabled",
                    "Runtime",
                    "Install",
                    "Creds",
                    "Smoke",
                    "Safe Mode",
                    "Last Exec",
                    "Overall",
                ],
                rows,
                styles=[
                    "cyan",
                    "green",
                    "dim",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "bold",
                ],
            )
        )
    else:
        print_info("No tools matched the selected filters.")

    if write_report or report_file:
        path = write_dashboard_report(dashboard, report_path=report_file)
        print_success(f"Wrote tool health report: {path}")

    if json_output:
        console.print(json.dumps(dashboard, indent=2, default=str))

