from __future__ import annotations
from pathlib import Path
import yaml

BASE = Path(__file__).resolve().parents[4]
FMT_DIR = BASE / 'configs' / 'report_formats'
FMT_DIR.mkdir(parents=True, exist_ok=True)


def list_formats():
    fmts = []
    for p in sorted(FMT_DIR.glob('*.yaml')):
        try:
            data = yaml.safe_load(p.read_text()) or {}
            fmts.append({'id': p.stem, 'name': data.get('name', p.stem), 'stakeholder': data.get('stakeholder')})
        except Exception:
            pass
    return fmts


def get_format(fid: str) -> dict:
    p = FMT_DIR / f'{fid}.yaml'
    data = yaml.safe_load(p.read_text()) if p.exists() else None
    if not data:
        raise FileNotFoundError(fid)
    return data


def render_report(fmt: dict, finding: dict, evidence: dict, mitigation: dict) -> str:
    # Very basic Jinja-less rendering (placeholder). Real system: jinja2 templates per stakeholder.
    lines = []
    lines.append(f"# {fmt.get('name','Bug Report')} — {finding.get('title','Untitled')}")
    lines.append("")
    lines.append(f"Stakeholder: {fmt.get('stakeholder')}")
    lines.append(f"Severity: {finding.get('severity','unknown')}  | CWE: {finding.get('cwe','n/a')}  | CVSS: {finding.get('cvss','n/a')}")
    lines.append("")
    lines.append("## Summary\n" + finding.get('summary',''))
    lines.append("## Impact\n" + finding.get('impact',''))
    lines.append("## Affected Scope\n" + finding.get('scope',''))
    lines.append("## Steps to Reproduce\n" + evidence.get('repro',''))
    lines.append("## Evidence\n" + '\n'.join(f"- {k}: {v}" for k,v in evidence.get('artifacts',{}).items()))
    lines.append("## Mitigation\n" + mitigation.get('plan',''))
    lines.append("## Timeline\n" + mitigation.get('timeline',''))
    lines.append("## References\n" + '\n'.join(f"- {r}" for r in (finding.get('references') or [])))
    lines.append("")
    return '\n'.join(lines)

from typing import Dict, Any

def validate_rendered(stakeholder: str, content: str, run_id: str | None = None, has_recording: bool = False) -> Dict[str, Any]:
    """Lightweight rendered-report validation.
    Ensures stakeholder-required sections are present and a recording exists.
    """
    import yaml, re
    from pathlib import Path
    BASE = Path(__file__).resolve().parents[4]
    fmt_dir = BASE / 'configs' / 'report_formats'
    required = []
    # Load required sections from stakeholder format
    for y in fmt_dir.glob('*.yaml'):
        try:
            data = yaml.safe_load(y.read_text()) or {}
            if str(data.get('stakeholder','')).lower() == str(stakeholder).lower():
                required = data.get('required_sections') or []
                break
        except Exception:
            continue
    missing = []
    if required:
        for sec in required:
            pattern = re.compile(r'^#+\s*' + re.escape(str(sec)) + r'\b', re.IGNORECASE | re.MULTILINE)
            if not pattern.search(content or ''):
                missing.append(sec)
    ok = bool(has_recording) and not missing and bool(content and content.strip())
    issues = []
    if not bool(has_recording):
        issues.append('screen_recording_missing')
    if missing:
        # include a generic code for missing sections; future can enumerate per section
        issues.append('missing_sections')
    return {'ok': ok, 'missing_sections': missing, 'has_recording': bool(has_recording), 'stakeholder': stakeholder, 'issues': issues}