from __future__ import annotations
from pathlib import Path
from .merkle import compute_merkle_tree
from typing import Dict, Any, List
from email.message import EmailMessage
from email.utils import formatdate
import mimetypes, zipfile, json
import logging
import os
import hashlib
from .email_formats import render_email
from .evidence_contract import normalize_report_evidence

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


ROOT = Path(__file__).resolve().parents[4]
ART = Path(os.getenv("K1_ARTIFACTS_DIR", str(ROOT / "artifacts"))).expanduser().resolve()
REPORTS = ART / os.getenv("K1_REPORTS_SUBDIR", "reports")
RECS = ART / os.getenv("K1_RECORDINGS_SUBDIR", "recordings")
SUBMITS = ART / os.getenv("K1_SUBMISSIONS_SUBDIR", "submissions")
SUBMITS.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE_BYTES = _env_int("K1_MAX_ATTACHMENT_FILE_BYTES", 500 * 1024 * 1024)
MAX_TOTAL_ATTACHMENT_BYTES = _env_int("K1_MAX_ATTACHMENT_TOTAL_BYTES", 2 * 1024 * 1024 * 1024)
MAX_RECORDING_ATTACHMENTS = _env_int("K1_MAX_RECORDING_ATTACHMENTS", 2)


def _gather_recordings(run_id: str) -> List[Path]:
    d = RECS / run_id
    return sorted(d.glob('*.mp4')) + sorted(d.glob('*.webm'))


def _read(p: Path) -> bytes:
    return p.read_bytes()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _resolve_artifact_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return (Path(__file__).resolve().parents[4] / path).resolve()


def revalidate_evidence_artifacts(artifacts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Revalidate evidence artifacts before report assembly.
    Rejects missing artifacts and hash mismatches for artifacts with declared sha256.
    """
    failures: List[Dict[str, str]] = []
    checked = 0

    for artifact in artifacts:
        raw_path = str(artifact.get("artifact_path") or "").strip()
        if not raw_path:
            failures.append({"error": "artifact_path_missing"})
            continue

        path = _resolve_artifact_path(raw_path)
        if not path.exists():
            failures.append({"artifact_path": str(path), "error": "artifact_missing"})
            continue

        declared_sha = str(artifact.get("sha256") or "").strip().lower()
        if declared_sha:
            actual_sha = _sha256_file(path)
            if actual_sha != declared_sha:
                failures.append(
                    {
                        "artifact_path": str(path),
                        "error": "artifact_hash_mismatch",
                        "expected_sha256": declared_sha,
                        "actual_sha256": actual_sha,
                    }
                )
                continue
            checked += 1

    return {"ok": not failures, "validated_hash_count": checked, "failures": failures}


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
    artifact_paths: Dict[str, Path] = {}
    total_attachment_bytes = 0

    normalized_evidence = normalize_report_evidence(context.get("evidence") or {})
    artifact_validation = revalidate_evidence_artifacts(
        normalized_evidence.get("artifacts_list") or []
    )
    if not artifact_validation["ok"]:
        raise ValueError(
            f"artifact_integrity_check_failed: {json.dumps(artifact_validation['failures'])}"
        )

    def add_attachment(name: str, path: Path, *, required: bool = False) -> bool:
        nonlocal total_attachment_bytes
        if not path.exists():
            if required:
                raise FileNotFoundError(f'missing required artifact: {path}')
            return False

        size = path.stat().st_size
        if size > MAX_FILE_SIZE_BYTES:
            if required:
                raise ValueError(f'required artifact too large: {path.name} ({size} bytes)')
            logger.warning("Skipping oversized optional attachment: %s (%s bytes)", path.name, size)
            return False

        if total_attachment_bytes + size > MAX_TOTAL_ATTACHMENT_BYTES:
            if required:
                raise ValueError("required artifact would exceed total attachment budget")
            logger.warning("Skipping attachment to enforce total size cap: %s", path.name)
            return False

        artifact_paths[name] = path
        total_attachment_bytes += size
        return True

    add_attachment('report.md', report_md, required=True)
    add_attachment('meta.json', meta_json, required=True)
    if merkle_json.exists():
        add_attachment('merkle.json', merkle_json, required=True)
    else:
        computed_merkle = Path(compute_merkle_tree(rdir)['path'])
        add_attachment('merkle.json', computed_merkle, required=True)

    # Attach chain.json if exists
    chainp = ART / 'graph' / run_id / 'chain.json'
    add_attachment('chain.json', chainp)

    # Attach first recording (or archive if exists)
    arch = (RECS / f'{run_id}.tar.gz')
    if arch.exists():
        add_attachment(f'{run_id}.tar.gz', arch)
    else:
        for recp in recs[:MAX_RECORDING_ATTACHMENTS]:
            add_attachment(recp.name, recp)

    report_md_bytes = _read(artifact_paths['report.md'])
    email_bytes = _build_email(stakeholder, context, attachments={'report.md': report_md_bytes})

    # Package ZIP
    out_zip = SUBMITS / f'{run_id}_{stakeholder}.zip'
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('email.eml', email_bytes)
        for name, path in artifact_paths.items():
            z.write(path, arcname=f'artifacts/{name}')
        # checklist
        checklist = {
            'hil_approved': bool(context.get('hil_approved')),
            'duplicate_status': (context.get('duplicate_check') or {}).get('status'),
            'has_recording': bool(recs),
            'stakeholder': stakeholder,
            'run_id': run_id,
            'attachment_file_count': len(artifact_paths),
            'attachment_total_bytes': total_attachment_bytes,
            'evidence_artifact_validation': artifact_validation,
        }
        z.writestr('SUBMISSION_CHECKLIST.json', json.dumps(checklist, indent=2))
    return {
        'zip': str(out_zip),
        'size': out_zip.stat().st_size,
        'attachment_file_count': len(artifact_paths),
        'attachment_total_bytes': total_attachment_bytes,
    }
