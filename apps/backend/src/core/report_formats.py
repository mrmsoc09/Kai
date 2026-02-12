from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import yaml
from jinja2 import Template, TemplateError, TemplateNotFound

BASE = Path(__file__).resolve().parents[4]
FMT_DIR = BASE / 'configs' / 'report_formats'
FMT_DIR.mkdir(parents=True, exist_ok=True)


def list_formats():
    """List all available report formats."""
    fmts = []
    for p in sorted(FMT_DIR.glob('*.yaml')):
        try:
            data = yaml.safe_load(p.read_text()) or {}
            fmts.append({
                'id': p.stem,
                'name': data.get('name', p.stem),
                'stakeholder': data.get('stakeholder'),
                'required_sections': data.get('required_sections', [])
            })
        except Exception:
            pass
    return fmts


def get_format(fid: str) -> dict:
    """Get report format by ID."""
    p = FMT_DIR / f'{fid}.yaml'
    data = yaml.safe_load(p.read_text()) if p.exists() else None
    if not data:
        raise FileNotFoundError(fid)
    return data


def build_template_context(finding: dict, evidence: dict, mitigation: dict, report_id: str = None) -> Dict[str, Any]:
    """Build template context from finding, evidence, and mitigation data."""
    return {
        'finding': finding,
        'evidence': evidence,
        'mitigation': mitigation,
        'report_id': report_id or 'REPORT_' + datetime.utcnow().strftime('%Y%m%d_%H%M%S'),
        'submission_date': finding.get('submission_date', datetime.utcnow().isoformat()),
        'report_generated_at': datetime.utcnow().isoformat(),
    }


def render_report(fmt: dict, finding: dict, evidence: dict, mitigation: dict, report_id: str = None) -> str:
    """
    Render a report using Jinja2 template from format definition.

    Args:
        fmt: Format dictionary (from YAML config)
        finding: Finding data
        evidence: Evidence data
        mitigation: Mitigation data
        report_id: Optional report ID

    Returns:
        Rendered report as markdown string
    """
    try:
        # Get template from format
        template_str = fmt.get('template')
        if not template_str:
            # Fallback to basic rendering if no template defined
            return _render_basic_report(fmt, finding, evidence, mitigation)

        # Build template context
        context = build_template_context(finding, evidence, mitigation, report_id)

        # Add custom filters
        template = Template(template_str)

        # Render template
        rendered = template.render(**context)
        return rendered

    except TemplateError as e:
        raise ValueError(f"Template rendering error: {str(e)}")
    except Exception as e:
        raise ValueError(f"Report rendering failed: {str(e)}")


def _render_basic_report(fmt: dict, finding: dict, evidence: dict, mitigation: dict) -> str:
    """Fallback basic report rendering when no template is defined."""
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

import re


def validate_rendered(stakeholder: str, content: str, run_id: str | None = None, has_recording: bool = False) -> Dict[str, Any]:
    """
    Validate rendered report against stakeholder requirements.

    Ensures stakeholder-required sections are present and a recording exists.

    Args:
        stakeholder: Stakeholder identifier
        content: Rendered report content (markdown)
        run_id: Optional run ID for additional context
        has_recording: Whether screen recording is attached

    Returns:
        Validation result dictionary with status and issues
    """
    required = []

    # Load required sections from stakeholder format
    for y in FMT_DIR.glob('*.yaml'):
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
        issues.append({
            'code': 'screen_recording_missing',
            'level': 'error',
            'message': 'Screen recording is required for submission'
        })
    if missing:
        issues.append({
            'code': 'missing_sections',
            'level': 'error',
            'message': f"Missing required sections: {', '.join(missing)}",
            'sections': missing
        })

    return {
        'ok': ok,
        'missing_sections': missing,
        'has_recording': bool(has_recording),
        'stakeholder': stakeholder,
        'issues': issues,
        'run_id': run_id
    }


def get_template_stats() -> Dict[str, Any]:
    """Get statistics about available templates."""
    formats = list_formats()
    stats = {
        'total_formats': len(formats),
        'formats': formats,
        'template_coverage': {
            fmt['stakeholder']: {
                'name': fmt['name'],
                'required_sections': fmt['required_sections'],
                'has_template': bool(get_format(fmt['id']).get('template'))
            }
            for fmt in formats
        }
    }
    return stats
