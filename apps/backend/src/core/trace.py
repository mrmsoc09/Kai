from __future__ import annotations
import os, json, re, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Resolve project root: .../k1/apps/backend/src/core/trace.py → ROOT=/a0/usr/projects/main-startup-build/k1
ROOT = Path(__file__).resolve().parents[4]
ART_DIR = ROOT / 'artifacts'
LOG_BASE = ART_DIR / 'logs'
CONF_DIR = ROOT / 'configs'
CONF_POL = CONF_DIR / 'policies.yaml'
CONF_KNOW = CONF_DIR / 'knowledge.yaml'
LOG_BASE.mkdir(parents=True, exist_ok=True)

SAFE_DEFAULT_PATTERNS = [
    r"AWS_SECRET_ACCESS_KEY", r"BEGIN RSA PRIVATE KEY", r"apikey=", r"password=",
]

def _load_yaml(p: Path) -> dict:
    try:
        import yaml  # type: ignore
        return yaml.safe_load(p.read_text(encoding='utf-8')) or {}
    except Exception:
        return {}

def _redactors() -> List[str]:
    k = _load_yaml(CONF_KNOW)
    pats = ((k.get('governance') or {}).get('redact_patterns')) or []
    return list(set(pats + SAFE_DEFAULT_PATTERNS))

def _redact_text(text: str) -> str:
    red = text
    for patt in _redactors():
        try:
            red = re.sub(re.escape(patt), '[REDACTED]', red)
        except re.error:
            red = red.replace(patt, '[REDACTED]')
    return red

def _date_dirs() -> Path:
    now = datetime.datetime.now(datetime.timezone.utc)
    d = LOG_BASE / f"{now.year:04d}" / f"{now.month:02d}" / f"{now.day:02d}"
    d.mkdir(parents=True, exist_ok=True)
    return d

def log_paths(run_id: str) -> Dict[str, str]:
    base = _date_dirs() / 'runs' / (run_id or 'unknown')
    base.mkdir(parents=True, exist_ok=True)
    return {
        'base': str(base),
        'decision_trace': str(base / 'decision_trace.jsonl'),
        'reasoning_summary': str(base / 'reasoning_summary.md'),
        'taxonomy_tags': str(base / 'taxonomy_tags.json'),
    }

def append_decision_trace(run_id: str, entry: Dict[str, Any]) -> str:
    try:
        paths = log_paths(run_id)
        line = {
            'ts': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            **{k: v for k, v in (entry or {}).items() if v is not None},
        }
        # shallow redact
        for k, v in list(line.items()):
            if isinstance(v, str):
                line[k] = _redact_text(v)
            elif isinstance(v, list):
                line[k] = [ _redact_text(i) if isinstance(i, str) else i for i in v ]
            elif isinstance(v, dict):
                for kk, vv in list(v.items()):
                    if isinstance(vv, str):
                        v[kk] = _redact_text(vv)
        with open(paths['decision_trace'], 'a', encoding='utf-8') as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
        return paths['decision_trace']
    except Exception:
        return ''

# Backward-compatible write_reasoning_summary supporting two call styles:
# A) write_reasoning_summary(run_id, what_changed, why, evidence, next_actions) → writes to run dir
# B) write_reasoning_summary(summary_path, title, bullets) → writes to explicit path

def write_reasoning_summary(*args, **kwargs) -> str:
    try:
        if len(args) >= 5 and isinstance(args[0], str) and isinstance(args[3], list) and isinstance(args[4], list):
            run_id, what_changed, why, evidence, next_actions = args[:5]
            paths = log_paths(run_id)
            md: List[str] = [
                f"# Reasoning Summary — {run_id}",
                "",
                "## What changed", _redact_text(what_changed or "-"),
                "",
                "## Why", _redact_text(why or "-"),
                "",
                "## Evidence",
            ]
            md += [f"- { _redact_text(e) }" for e in (evidence or [])]
            md += ["", "## Next actions"]
            md += [f"- { _redact_text(n) }" for n in (next_actions or [])]
            md += [""]
            with open(paths['reasoning_summary'], 'w', encoding='utf-8') as f:
                f.write("\n".join(md))
            # seed taxonomy file
            try:
                if not os.path.exists(paths['taxonomy_tags']):
                    with open(paths['taxonomy_tags'], 'w', encoding='utf-8') as tf:
                        tf.write(json.dumps({"tags": []}, ensure_ascii=False))
            except Exception:
                pass
            return paths['reasoning_summary']
        elif len(args) >= 3 and isinstance(args[0], str) and isinstance(args[2], list):
            # summary_path, title, bullets
            summary_path, title, bullets = args[:3]
            os.makedirs(os.path.dirname(summary_path) or '.', exist_ok=True)
            with open(summary_path, 'a', encoding='utf-8') as f:
                f.write(f"# {title}\n")
                for b in (bullets or []):
                    line = str(b).replace('\r', '').rstrip('\n')
                    f.write(f"- {line}\n")
                f.write("\n")
            return summary_path
    except Exception:
        pass
    return ''

# Support both signatures; default safe gating when config absent

def policy_gate_info(mode: Optional[str] = None, external: Optional[bool] = None) -> Dict[str, Any]:
    pol = _load_yaml(CONF_POL) or {}
    auto = (pol.get('autonomy') or {})
    # defaults
    m = mode or 'plan'
    ext = bool(external) if external is not None else False
    if m != 'execute':
        tier = 0; name = 'AUTO'
    else:
        tier = 2 if ext else 0
        name = 'APPROVE' if ext else 'AUTO'
    return { 'tier': tier, 'name': name, 'rules': auto.get('gating_rules', []) }
