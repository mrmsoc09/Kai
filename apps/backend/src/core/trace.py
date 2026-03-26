from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .helpers import artifacts_root, repo_root

_CONF_DIR = repo_root() / "configs"
_CONF_POL = _CONF_DIR / "policies.yaml"
_CONF_KNOW = _CONF_DIR / "knowledge.yaml"

SAFE_DEFAULT_PATTERNS: list[str] = [
    r"AWS_SECRET_ACCESS_KEY",
    r"BEGIN RSA PRIVATE KEY",
    r"apikey=",
    r"password=",
]


def _log_base() -> Path:
    base = artifacts_root() / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _load_yaml(p: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore

        return yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _redactors() -> list[str]:
    k = _load_yaml(_CONF_KNOW)
    pats = ((k.get("governance") or {}).get("redact_patterns")) or []
    return list(set(pats + SAFE_DEFAULT_PATTERNS))


def _redact_text(text: str) -> str:
    result = text
    for patt in _redactors():
        try:
            result = re.sub(re.escape(patt), "[REDACTED]", result)
        except re.error:
            result = result.replace(patt, "[REDACTED]")
    return result


def _dated_log_dir() -> Path:
    now = datetime.now(timezone.utc)
    d = _log_base() / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_paths(run_id: str) -> dict[str, str]:
    base = _dated_log_dir() / "runs" / (run_id or "unknown")
    base.mkdir(parents=True, exist_ok=True)
    return {
        "base": str(base),
        "decision_trace": str(base / "decision_trace.jsonl"),
        "reasoning_summary": str(base / "reasoning_summary.md"),
        "taxonomy_tags": str(base / "taxonomy_tags.json"),
    }


def append_decision_trace(run_id: str, entry: dict[str, Any]) -> str:
    try:
        paths = log_paths(run_id)
        line: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            **{k: v for k, v in (entry or {}).items() if v is not None},
        }
        for k, v in list(line.items()):
            if isinstance(v, str):
                line[k] = _redact_text(v)
            elif isinstance(v, list):
                line[k] = [_redact_text(i) if isinstance(i, str) else i for i in v]
            elif isinstance(v, dict):
                for kk, vv in list(v.items()):
                    if isinstance(vv, str):
                        v[kk] = _redact_text(vv)
        with open(paths["decision_trace"], "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return paths["decision_trace"]
    except Exception:
        return ""


# Backward-compatible write_reasoning_summary supporting two call styles:
# A) write_reasoning_summary(run_id, what_changed, why, evidence, next_actions)
# B) write_reasoning_summary(summary_path, title, bullets)
def write_reasoning_summary(*args: Any, **kwargs: Any) -> str:
    try:
        if (
            len(args) >= 5
            and isinstance(args[0], str)
            and isinstance(args[3], list)
            and isinstance(args[4], list)
        ):
            run_id, what_changed, why, evidence, next_actions = args[:5]
            paths = log_paths(run_id)
            md: list[str] = [
                f"# Reasoning Summary — {run_id}",
                "",
                "## What changed",
                _redact_text(what_changed or "-"),
                "",
                "## Why",
                _redact_text(why or "-"),
                "",
                "## Evidence",
            ]
            md += [f"- {_redact_text(e)}" for e in (evidence or [])]
            md += ["", "## Next actions"]
            md += [f"- {_redact_text(n)}" for n in (next_actions or [])]
            md += [""]
            with open(paths["reasoning_summary"], "w", encoding="utf-8") as f:
                f.write("\n".join(md))
            if not os.path.exists(paths["taxonomy_tags"]):
                try:
                    with open(paths["taxonomy_tags"], "w", encoding="utf-8") as tf:
                        tf.write(json.dumps({"tags": []}, ensure_ascii=False))
                except Exception:
                    pass
            return paths["reasoning_summary"]

        if (
            len(args) >= 3
            and isinstance(args[0], str)
            and isinstance(args[2], list)
        ):
            summary_path, title, bullets = args[:3]
            os.makedirs(os.path.dirname(summary_path) or ".", exist_ok=True)
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(f"# {title}\n")
                for b in bullets or []:
                    f.write(f"- {str(b).replace(chr(13), '').rstrip(chr(10))}\n")
                f.write("\n")
            return summary_path
    except Exception:
        pass
    return ""


def policy_gate_info(
    mode: str | None = None,
    external: bool | None = None,
) -> dict[str, Any]:
    pol = _load_yaml(_CONF_POL) or {}
    auto = pol.get("autonomy") or {}
    m = mode or "plan"
    ext = bool(external) if external is not None else False
    if m != "execute":
        tier, name = 0, "AUTO"
    else:
        tier, name = (2, "APPROVE") if ext else (0, "AUTO")
    return {"tier": tier, "name": name, "rules": auto.get("gating_rules", [])}
