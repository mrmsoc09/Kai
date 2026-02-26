from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import yaml
from jinja2 import Template

ROOT = Path(__file__).resolve().parents[4]
CFG = ROOT / 'configs' / 'email_formats'
CFG.mkdir(parents=True, exist_ok=True)

_DEFAULT = {
    'subject': 'Vulnerability report: {{ finding.title }} ({{ finding.severity|default("n/a") }})',
    'body': (
        'Hello {{ stakeholder|capitalize }},\n\n'
        'Please find attached a vulnerability report for your program.\n\n'
        'Summary: {{ finding.summary }}\n'
        'Impact: {{ finding.impact }}\n'
        'Severity: {{ finding.severity|default("n/a") }}\n'
        'Scope: {{ finding.scope|default("n/a") }}\n\n'
        'A mitigation plan is included below and in the attached report.\n\n'
        'Mitigation Plan:\n{{ mitigation.plan }}\n\n'
        'Timeline: {{ mitigation.timeline|default("n/a") }}\n\n'
        'Reproduction steps and a safe screen recording are included.\n\n'
        'Best regards,\nK1/Agent Zero\n'
    ),
    'headers': { 'X-K1-Report': '{{ run_id }}' }
}


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text()) or {}
    except Exception:
        return {}


def available() -> list[str]:
    return sorted([p.stem for p in CFG.glob('*.yaml')])


def load_format(stakeholder: str) -> Dict[str, Any]:
    p = CFG / f'{stakeholder}.yaml'
    if p.exists():
        return _load_yaml(p)
    return _DEFAULT


def render_email(stakeholder: str, ctx: Dict[str, Any]) -> Dict[str, Any]:
    spec = load_format(stakeholder)
    subject_tpl = Template(spec.get('subject', _DEFAULT['subject']))
    body_tpl = Template(spec.get('body', _DEFAULT['body']))
    headers = spec.get('headers', _DEFAULT['headers'])
    subject = subject_tpl.render(**ctx)
    body = body_tpl.render(**ctx)
    rendered_headers = {k: Template(str(v)).render(**ctx) for k, v in headers.items()}
    return { 'subject': subject, 'body': body, 'headers': rendered_headers }
