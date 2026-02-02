from __future__ import annotations
from pathlib import Path
from .merkle import compute_merkle_tree
from typing import Dict, Any, List
from email.message import EmailMessage
from email.utils import formatdate
import mimetypes, tarfile, zipfile, json
from .email_formats import render_email

ROOT = Path(__file__).resolve().parents[4]
ART = ROOT / 'artifacts'
REPORTS = ART / 'reports'
RECS = ART / 'recordings'
SUBMITS = ART / 'submissions'
SUBMITS.mkdir(parents=True, exist_ok=True)


def _gather_recordings(run_id: str) -> List[Path]:
    d = RECS / run_id
    return sorted(d.glob('*.mp4')) + sorted(d.glob('*.webm'))


def _read(p: Path) -> bytes:
    return p.read_bytes()


def _build_email(stakeholder: str, ctx: Dict[str, Any], attachments: Dict[str, bytes]) -> bytes:
    msg = EmailMessage()
    rendered = render_email(stakeholder, ctx)
    msg['Date'] = formatdate(localtime=False)
    msg['Subject'] = rendered['subject']
    msg['From'] = 'agent-zero@k1.local'
    msg['To'] = 'stakeholder@program.local'
    for k,v in rendered['headers'].items():
        msg[k] = v
    msg.set_content(rendered['body'])
    for name, data in attachments.items():
        ctype, _ = mimetypes.guess_type(name)
        maintype, subtype = (ctype.split('/') if ctype else ('application','octet-stream'))
        msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return msg.as_bytes()


def build_submission_package(run_id: str, stakeholder: str, context: Dict[str, Any]) -> Dict[str, Any]:
    rdir = REPORTS / run_id
    if not rdir.exists():
        raise FileNotFoundError(f'report dir missing: {rdir}')
    report_md = rdir / 'report.md'
    meta_json = rdir / 'meta.json'
    merkle_json = rdir / 'merkle.json'
    recs = _gather_recordings(run_id)
    attachments = {
        'report.md': _read(report_md),
        'meta.json': _read(meta_json),
        'merkle.json': (_read(merkle_json) if merkle_json.exists() else (_read(Path(compute_merkle_tree(report_dir)['path'])))),
    }
    # Attach chain.json if exists
    chainp = (ROOT / 'artifacts' / 'graph' / run_id / 'chain.json')
    if chainp.exists():
        attachments['chain.json'] = _read(chainp)
    # Attach first recording (or archive if exists)
    arch = (RECS / f'{run_id}.tar.gz')
    if arch.exists():
        attachments[f'{run_id}.tar.gz'] = _read(arch)
    else:
        for i, recp in enumerate(recs[:2]):
            attachments[recp.name] = _read(recp)
    email_bytes = _build_email(stakeholder, context, attachments={'report.md': attachments['report.md']})
    # Package ZIP
    out_zip = SUBMITS / f'{run_id}_{stakeholder}.zip'
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('email.eml', email_bytes)
        for name, data in attachments.items():
            z.writestr(f'artifacts/{name}', data)
        # checklist
        checklist = {
            'hil_approved': bool(context.get('hil_approved')),
            'duplicate_status': (context.get('duplicate_check') or {}).get('status'),
            'has_recording': bool(recs),
            'stakeholder': stakeholder,
            'run_id': run_id
        }
        z.writestr('SUBMISSION_CHECKLIST.json', json.dumps(checklist, indent=2))
    return {'zip': str(out_zip), 'size': out_zip.stat().st_size}
