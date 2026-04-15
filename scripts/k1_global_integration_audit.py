#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


@dataclass
class Finding:
    severity: str
    category: str
    file: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "message": self.message,
        }


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python_files(root: Path, pattern: str) -> list[Path]:
    return sorted(root.rglob(pattern))


def _class_bases(path: Path) -> dict[str, list[str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            names: list[str] = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    names.append(base.id)
                elif isinstance(base, ast.Attribute):
                    names.append(base.attr)
            out[node.name] = names
    return out


def _audit_base_tool_inheritance(agent_files: list[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in agent_files:
        rel = str(path.relative_to(root))
        try:
            classes = _class_bases(path)
        except Exception as exc:
            findings.append(Finding("high", "parsing", rel, f"AST parse failed: {exc}"))
            continue
        def inherits_base_tool(class_name: str, seen: set[str] | None = None) -> bool:
            seen = seen or set()
            if class_name in seen:
                return False
            seen.add(class_name)
            bases = classes.get(class_name, [])
            if "BaseToolAgent" in bases:
                return True
            for base in bases:
                if base in classes and inherits_base_tool(base, seen):
                    return True
            return False

        for class_name, bases in classes.items():
            if class_name.endswith("Agent") and class_name != "BaseToolAgent":
                if not inherits_base_tool(class_name):
                    findings.append(
                        Finding(
                            "high",
                            "inheritance",
                            rel,
                            f"{class_name} does not inherit BaseToolAgent (bases={bases})",
                        )
                    )
    return findings


def _audit_registry_alignment(agent_files: list[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    required_tokens = ("DiscoveryRegistry", "SecretLeakRegistry", "VulnerabilityRegistry")
    for path in agent_files:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        uses_required_registry = any(token in text for token in required_tokens)
        if not uses_required_registry:
            continue
        if ".model_validate(" not in text:
            findings.append(
                Finding(
                    "medium",
                    "registry_alignment",
                    rel,
                    "Registry model referenced without model_validate() usage",
                )
            )
    return findings


def _audit_secret_masking(agent_files: list[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    scanners = ("trufflehog", "gitleaks")
    for path in agent_files:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8").lower()
        if not any(scanner in rel for scanner in scanners):
            continue
        has_mask = "mask" in text and "masked" in text
        if not has_mask:
            findings.append(
                Finding(
                    "high",
                    "masked_evidence",
                    rel,
                    "Secret scanner appears to miss explicit masking semantics",
                )
            )
    return findings


def _audit_snl_routing(enhanced_files: list[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in enhanced_files:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8").lower()
        uses_subprocess = "subprocess." in text or "create_subprocess_exec" in text
        if not uses_subprocess:
            continue
        has_snl_guard = any(
            token in text
            for token in (
                "sovereign",
                "snl",
                "proxy",
                "vpn",
                "network_env",
                "k1_enforce_sovereign_network",
            )
        )
        if not has_snl_guard:
            findings.append(
                Finding(
                    "high",
                    "snl_routing",
                    rel,
                    "subprocess execution detected without explicit SNL/proxy guard markers",
                )
            )
    return findings


def _audit_vrad_telemetry(agent_files: list[Path], root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in agent_files:
        rel = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8")
        has_hook = "_telemetry_hook" in text or "telemetry_hook" in text
        has_emit = "_emit_telemetry" in text or "get_telemetry_events" in text
        if not (has_hook and has_emit):
            findings.append(
                Finding(
                    "medium",
                    "vrad_telemetry",
                    rel,
                    "No clear telemetry hook + emit pattern found",
                )
            )
    return findings


def _write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# K1 Global Integration Audit",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- Agent files audited: `{report['agent_files_audited']}`",
        f"- Findings: `{report['summary']['total_findings']}`",
        f"- High: `{report['summary']['high']}` | Medium: `{report['summary']['medium']}`",
        "",
        "## Findings",
        "",
    ]
    for finding in report["findings"]:
        lines.append(
            f"- **{finding['severity'].upper()}** [{finding['category']}] "
            f"`{finding['file']}`: {finding['message']}"
        )
    if not report["findings"]:
        lines.append("- No issues detected by static checks.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_audit() -> dict[str, Any]:
    root = _repo_root()
    agents_root = root / "apps" / "backend" / "src" / "agents" / "tools"
    agent_files = _python_files(agents_root, "agent.py")
    enhanced_files = _python_files(agents_root, "agent_enhanced.py")

    findings: list[Finding] = []
    findings.extend(_audit_base_tool_inheritance(agent_files, root))
    findings.extend(_audit_registry_alignment(agent_files, root))
    findings.extend(_audit_secret_masking(agent_files, root))
    findings.extend(_audit_snl_routing(enhanced_files, root))
    findings.extend(_audit_vrad_telemetry(agent_files, root))

    summary = {
        "total_findings": len(findings),
        "high": sum(1 for f in findings if f.severity == "high"),
        "medium": sum(1 for f in findings if f.severity == "medium"),
    }
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "agent_files_audited": len(agent_files),
        "agent_enhanced_files_audited": len(enhanced_files),
        "summary": summary,
        "findings": [f.as_dict() for f in findings],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="K1 global integration static audit")
    parser.add_argument(
        "--output-json",
        default="output/audits/global_k1_integration_audit.json",
        help="JSON output path",
    )
    parser.add_argument(
        "--output-md",
        default="output/audits/global_k1_integration_audit.md",
        help="Markdown output path",
    )
    args = parser.parse_args()

    report = run_audit()

    json_path = Path(args.output_json)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    md_path = Path(args.output_md)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    _write_markdown(md_path, report)

    print(
        json.dumps(
            {
                "json_report": str(json_path),
                "markdown_report": str(md_path),
                "total_findings": report["summary"]["total_findings"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
