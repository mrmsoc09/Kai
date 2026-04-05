from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from typing import Any

from ..base_tool_agent import BaseToolAgent


_CATEGORIES = ["sqli", "xss", "ssrf", "redirect", "rce", "idor"]


class GfAgent(BaseToolAgent):
    TOOL_NAME = "gf"

    def _get_tool_name(self) -> str:
        return self.TOOL_NAME

    def build_command(self, target: str, options: dict[str, Any] | None = None) -> list[str]:
        opts = options or {}
        combined_urls = str(opts.get("combined_urls_file", target))
        return ["gf", "sqli", combined_urls]

    def execute(
        self,
        target: str,
        options: dict[str, Any] | None = None,
        *,
        mission_id: str = "mission-001",
    ):
        """
        Run gf across all supported categories and aggregate results for routing.
        """
        opts = options or {}
        combined_urls = str(opts.get("combined_urls_file", target))
        timeout_seconds = max(1, int(opts.get("timeout_seconds", self.DEFAULT_TIMEOUT_SECONDS)))

        started_at = datetime.now(UTC)
        aggregated_lines: list[str] = []
        stderr_chunks: list[str] = []
        command_log: list[list[str]] = []
        status = "success"
        had_any_output = False

        for category in _CATEGORIES:
            cmd = ["gf", category, combined_urls]
            command_log.append(cmd)
            try:
                completed = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    shell=False,
                    timeout=timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                status = "timeout"
                stderr_chunks.append(f"{category}: timeout_exceeded:{timeout_seconds}s")
                break
            except OSError as exc:
                status = "failure"
                stderr_chunks.append(f"{category}: {exc}")
                break

            output = (completed.stdout or "").strip()
            if output:
                had_any_output = True
                for line in output.splitlines():
                    value = line.strip()
                    if value:
                        aggregated_lines.append(f"{category}\t{value}")

            if completed.returncode not in (0, 1):
                status = "failure"
                stderr_chunks.append(
                    f"{category}: non_zero_exit={completed.returncode} stderr={(completed.stderr or '').strip()[:500]}"
                )

        if status == "success" and not had_any_output:
            status = "partial"

        ended_at = datetime.now(UTC)
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))
        stdout = "\n".join(aggregated_lines)
        stderr = "\n".join(chunk for chunk in stderr_chunks if chunk)
        exit_code = 0 if status in {"success", "partial"} else 1

        result = self.map_output(
            target=target,
            command=["gf", "multi", combined_urls],
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=runtime_ms,
            mission_id=mission_id,
            status=status,
            options={**opts, "gf_commands": command_log},
        )

        deduped_findings = self._filter_duplicates(target, result.findings)
        if len(deduped_findings) != len(result.findings):
            result = result.model_copy(update={"status": "partial", "findings": deduped_findings})

        self._persist_memory(target, deduped_findings)
        return result

    def parse_output(self, raw_output: str, target: str) -> list[dict[str, Any]]:
        findings: list[dict[str, Any]] = []
        for line in raw_output.strip().splitlines():
            value = line.strip()
            if not value:
                continue

            category = "uncategorized"
            url = value
            if "\t" in value:
                prefix, rest = value.split("\t", 1)
                if prefix.lower() in _CATEGORIES:
                    category = prefix.lower()
                    url = rest.strip()
            elif value.startswith("[") and "]" in value:
                prefix, rest = value.split("]", 1)
                token = prefix.lstrip("[").strip().lower()
                if token in _CATEGORIES:
                    category = token
                    url = rest.strip()

            severity = "high" if category in {"ssrf", "sqli", "rce"} else ("medium" if category in {"xss", "idor"} else "info")
            findings.append(
                {
                    "type": "url",
                    "value": url,
                    "target": target,
                    "severity": severity,
                    "confidence": 0.86,
                    "source_tool": self.TOOL_NAME,
                    "raw_evidence": value[:1000],
                    "context": {"category": category},
                    "recommended_next_tools": ["sqlmap", "dalfox", "ssrfmap"],
                    "recommended_next_actions": ["vulnerability_scan"],
                }
            )

        return findings

    def filter_noise(
        self, findings: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        signal: list[dict[str, Any]] = []
        noise: list[dict[str, Any]] = []
        known = self.load_memory()

        for finding in findings:
            value = finding["value"].lower()
            if f"{finding['target'].lower()}|url|{value}" in known:
                noise.append(finding)
                continue

            category = str(finding.get("context", {}).get("category", ""))
            if category == "rce":
                finding["severity"] = "high"
                finding["context"]["manual_review_required"] = True
                signal.append(finding)
                continue
            if category == "uncategorized":
                noise.append(finding)
                continue
            signal.append(finding)

        return signal, noise

    def _generate_next_agent_instructions(
        self,
        signal: list[dict[str, Any]],
        target: str,
    ) -> dict[str, Any]:
        grouped: dict[str, list[str]] = {k: [] for k in _CATEGORIES}
        for finding in signal:
            category = str(finding.get("context", {}).get("category", ""))
            if category in grouped:
                grouped[category].append(str(finding.get("value", "")))

        next_agents = []
        if grouped["sqli"]:
            next_agents.append("sqlmap")
        if grouped["xss"]:
            next_agents.append("dalfox")
        if grouped["ssrf"]:
            next_agents.append("ssrfmap")

        return {
            "next_agents": next_agents,
            "sqli_urls": grouped["sqli"],
            "xss_urls": grouped["xss"],
            "ssrf_urls": grouped["ssrf"],
            "idor_urls": grouped["idor"],
            "rce_urls": grouped["rce"],
            "configuration_hints": {
                "sqlmap": {"input_file": "gf_sqli.txt"},
                "dalfox": {"input_file": "gf_xss.txt"},
                "ssrfmap": {"input_file": "gf_ssrf.txt"},
            },
            "operator_summary": (
                f"GF categorized {len(signal)} URLs for {target}. SQLi={len(grouped['sqli'])}, "
                f"XSS={len(grouped['xss'])}, SSRF={len(grouped['ssrf'])}, IDOR={len(grouped['idor'])}, "
                f"RCE(manual)={len(grouped['rce'])}."
            ),
        }
