"""
CLI UI components.

Uses Rich when available, with a lightweight stdout fallback for minimal
environments (tests/bootstrap).
"""

from __future__ import annotations

import json
from contextlib import contextmanager

try:  # pragma: no cover - exercised indirectly depending on environment
    from .rich_ui import (
        console,
        print_header,
        print_success,
        print_error,
        print_warning,
        print_info,
        create_table,
        create_progress,
        create_status_panel,
        create_findings_table,
        create_agent_table,
        create_workflow_table,
        create_hunt_summary,
        print_json,
        confirm_action,
        prompt_input,
    )
except ModuleNotFoundError:  # pragma: no cover - fallback path for missing rich
    class _ConsoleFallback:
        def print(self, value):
            print(value)

    console = _ConsoleFallback()

    def print_header(text: str, subtitle: str | None = None):
        print(f"K1 {text}")
        if subtitle:
            print(subtitle)

    def print_success(message: str):
        print(f"[OK] {message}")

    def print_error(message: str):
        print(f"[ERROR] {message}")

    def print_warning(message: str):
        print(f"[WARN] {message}")

    def print_info(message: str):
        print(f"[INFO] {message}")

    def create_table(title: str, columns, rows, styles=None):
        lines = [title, " | ".join(columns)]
        for row in rows:
            lines.append(" | ".join(str(cell) for cell in row))
        return "\n".join(lines)

    @contextmanager
    def create_progress():
        class _Progress:
            def add_task(self, *_args, **_kwargs):
                return 1

            def update(self, *_args, **_kwargs):
                return None

        yield _Progress()

    def create_status_panel(title: str, status: dict, style: str = "green"):
        lines = [title]
        for key, value in status.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)

    def create_findings_table(findings):
        return create_table("Findings", ["id", "title"], [[f.get("id", ""), f.get("title", "")] for f in findings])

    def create_agent_table(agents):
        return create_table("Agents", ["id", "name"], [[a.get("agent_id", ""), a.get("name", "")] for a in agents])

    def create_workflow_table(workflows):
        return create_table(
            "Workflows",
            ["id", "name"],
            [[w.get("workflow_id", w.get("id", "")), w.get("name", "")] for w in workflows],
        )

    def create_hunt_summary(summary):
        return json.dumps(summary, default=str, indent=2)

    def print_json(data):
        print(json.dumps(data, default=str, indent=2))

    def confirm_action(_message: str, default: bool = False) -> bool:
        return default

    def prompt_input(_message: str, default: str | None = None, password: bool = False) -> str:
        return default or ""


__all__ = [
    "console",
    "print_header",
    "print_success",
    "print_error",
    "print_warning",
    "print_info",
    "create_table",
    "create_progress",
    "create_status_panel",
    "create_findings_table",
    "create_agent_table",
    "create_workflow_table",
    "create_hunt_summary",
    "print_json",
    "confirm_action",
    "prompt_input",
]
