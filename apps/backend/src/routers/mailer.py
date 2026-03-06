from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from pathlib import Path
import os
import smtplib, ssl, email
from email.parser import BytesParser
from email.policy import default
from ..core.auth import require_roles, ROLE_OPERATOR
from ..core.logs import log_decision
from ..core.comms_store import append_message
from ..core.hil_approval_system import ApprovalStatus
from .hil_approval import get_hil_system

router = APIRouter(prefix='/mailer', tags=['mailer'], dependencies=[Depends(require_roles(ROLE_OPERATOR))])

ROOT = Path(__file__).resolve().parents[4]
ENV_ARTIFACTS = os.getenv('K1_ARTIFACTS_ROOT')
if ENV_ARTIFACTS and Path(ENV_ARTIFACTS).exists():
    ARTIFACTS_ROOT = Path(ENV_ARTIFACTS)
else:
    ARTIFACTS_ROOT = ROOT / 'artifacts'

SUBMITS = ARTIFACTS_ROOT / 'submissions'
OUTBOX = SUBMITS / 'outbox'
SENT = OUTBOX / 'sent'
FOLLOWUPS = OUTBOX / 'followups'
for d in (OUTBOX, SENT, FOLLOWUPS):
    d.mkdir(parents=True, exist_ok=True)


def _send_via_smtp(raw_eml: bytes, smtp_cfg: Dict[str, Any]) -> Dict[str, Any]:
    msg = BytesParser(policy=default).parsebytes(raw_eml)
    host = smtp_cfg.get('host') or 'localhost'
    port = int(smtp_cfg.get('port') or 25)
    user = smtp_cfg.get('user')
    pw = smtp_cfg.get('pass') or smtp_cfg.get('password')
    use_tls = bool(smtp_cfg.get('tls') or smtp_cfg.get('starttls'))
    use_ssl = bool(smtp_cfg.get('ssl'))
    to_addrs = [a.strip() for a in (smtp_cfg.get('to') or msg.get('To') or '').split(',') if a.strip()]
    from_addr = smtp_cfg.get('from') or (msg.get('From') or 'agent-zero@k1.local')
    if not to_addrs:
        raise HTTPException(400, 'No recipients provided or in EML')
    if use_ssl:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            if user and pw:
                server.login(user, pw)
            server.sendmail(from_addr, to_addrs, raw_eml)
    else:
        with smtplib.SMTP(host, port) as server:
            if use_tls:
                server.starttls(context=ssl.create_default_context())
            if user and pw:
                server.login(user, pw)
            server.sendmail(from_addr, to_addrs, raw_eml)
    return {'sent': True, 'to': to_addrs, 'from': from_addr, 'host': host, 'port': port}


def _ensure_approval_granted(approval_id: str | None, expected_type: str) -> None:
    if not approval_id:
        raise HTTPException(409, 'approval_id_required_for_outbound_send')
    hil = get_hil_system()
    # Approved requests are moved to history.
    for item in hil.approval_history:
        if item.approval_id == approval_id:
            if item.status != ApprovalStatus.APPROVED:
                raise HTTPException(409, f'approval_not_granted:{approval_id}')
            if item.approval_type.value != expected_type:
                raise HTTPException(409, f'approval_type_mismatch:{item.approval_type.value}')
            return
    raise HTTPException(409, f'approval_not_found:{approval_id}')


@router.post('/send')
async def send(payload: Dict[str, Any]) -> Dict[str, Any]:
    run_id = payload.get('run_id')
    stakeholder = payload.get('stakeholder') or 'google_vrp'
    if not run_id:
        raise HTTPException(400, 'run_id required')
    eml = OUTBOX / f'{run_id}_{stakeholder}.eml'
    if not eml.exists():
        # try from ZIP if not dispatched yet
        import zipfile
        pkg = SUBMITS / f'{run_id}_{stakeholder}.zip'
        if not pkg.exists():
            raise HTTPException(404, 'No package/eml found; run /reports/package and /submissions/dispatch first')
        with zipfile.ZipFile(pkg, 'r') as z:
            if 'email.eml' not in z.namelist():
                raise HTTPException(500, 'email.eml missing in package')
            eml.write_bytes(z.read('email.eml'))
    raw = eml.read_bytes()
    # dev mode: if no SMTP config provided, archive to /sent and return
    smtp_cfg = payload.get('smtp') or {}
    if not smtp_cfg:
        sent_path = SENT / f'{run_id}_{stakeholder}.eml'
        sent_path.write_bytes(raw)
        log_decision(run_id, 'report_email_archived', {'stakeholder': stakeholder, 'eml': str(sent_path)})
        append_message(
            run_id=run_id,
            stakeholder=stakeholder,
            channel="email",
            direction="outbound",
            subject=f"Submission delivery ({stakeholder})",
            body="Submission email archived in local sent mailbox.",
            artifact_path=str(sent_path),
            metadata={"mode": "archive"},
        )
        return {'status': 'archived', 'eml': str(sent_path)}
    # attempt SMTP send
    _ensure_approval_granted(payload.get("approval_id"), "report_submission")
    info = _send_via_smtp(raw, smtp_cfg)
    log_decision(run_id, 'report_email_sent', {'stakeholder': stakeholder, **info})
    append_message(
        run_id=run_id,
        stakeholder=stakeholder,
        channel="email",
        direction="outbound",
        subject=f"Submission delivery ({stakeholder})",
        body="Submission email sent via SMTP.",
        artifact_path=str(eml),
        metadata=info,
    )
    return {'status': 'sent', **info}


@router.post('/followup')
async def followup(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Render a simple follow-up email referencing the original run/package
    run_id = payload.get('run_id')
    stakeholder = payload.get('stakeholder') or 'google_vrp'
    if not run_id:
        raise HTTPException(400, 'run_id required')
    subj = payload.get('subject') or f"Follow-up: {run_id} — vulnerability report status"
    body = payload.get('body') or (
        "Hello program team,\n\nThis is a friendly follow-up on report {run_id}. "
        "We have provided a full reproduction, mitigation plan, and a compliance-formatted report package. "
        "Please let us know if additional details are needed.\n\nRegards,\nAgent Zero" 
    ).format(run_id=run_id)
    # Build minimal EML
    from email.message import EmailMessage
    msg = EmailMessage()
    msg['Subject'] = subj
    msg['From'] = payload.get('from') or 'agent-zero@k1.local'
    msg['To'] = payload.get('to') or 'stakeholder@program.local'
    msg.set_content(body)
    raw = msg.as_bytes()
    # store to followups dir
    fpath = FOLLOWUPS / f'{run_id}_{stakeholder}_followup.eml'
    fpath.write_bytes(raw)
    log_decision(run_id, 'report_followup_prepared', {'stakeholder': stakeholder, 'eml': str(fpath)})
    append_message(
        run_id=run_id,
        stakeholder=stakeholder,
        channel="email",
        direction="outbound",
        subject=subj,
        body=body,
        artifact_path=str(fpath),
        metadata={"kind": "followup", "status": "prepared"},
    )
    # Optionally send via SMTP if provided
    smtp_cfg = payload.get('smtp') or {}
    if smtp_cfg:
        _ensure_approval_granted(payload.get("approval_id"), "email_reply")
        info = _send_via_smtp(raw, smtp_cfg)
        log_decision(run_id, 'report_followup_sent', {'stakeholder': stakeholder, **info})
        return {'status': 'sent', **info, 'eml': str(fpath)}
    return {'status': 'prepared', 'eml': str(fpath)}


@router.post('/reply_draft')
async def reply_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create approval-gated draft reply for stakeholder communication.
    Does not send email.
    """
    run_id = payload.get("run_id")
    program_id = payload.get("program_id") or payload.get("stakeholder") or "unknown"
    program_name = payload.get("program_name") or payload.get("stakeholder") or "unknown"
    incoming = payload.get("incoming_email") or {}
    if not run_id:
        raise HTTPException(400, "run_id required")

    draft = {
        "subject": payload.get("subject") or f"Re: {incoming.get('subject', 'Security report')}",
        "body": payload.get("body")
        or (
            "Thanks for the update. We reviewed your request and attached additional "
            "defensive evidence required for triage."
        ),
    }
    hil = get_hil_system()
    approval = await hil.request_email_reply_approval(
        scan_id=str(run_id),
        program_id=str(program_id),
        program_name=str(program_name),
        incoming_email=dict(incoming),
        draft_reply=draft,
    )
    append_message(
        run_id=str(run_id),
        stakeholder=str(program_name),
        channel="email",
        direction="draft",
        subject=draft["subject"],
        body=draft["body"],
        metadata={"approval_id": approval.approval_id, "status": approval.status.value},
    )
    return {
        "status": "approval_required",
        "approval_id": approval.approval_id,
        "draft": draft,
    }
