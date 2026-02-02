from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from ..core.auth import get_current_user, User
from ..core.models import Finding

router = APIRouter(prefix='/intel', tags=['intelligence'])

_SAMPLE: List[Finding] = [
    Finding(id='f-001', title='Missing security headers', severity='low', type='Web/Headers', target_asset='app.example.com', chain_value=20, chain_potential='low', stage='discovered', status='open', evidence_completeness=40),
    Finding(id='f-002', title='Weak JWT validation', severity='medium', type='Auth/JWT', target_asset='api.example.com', chain_value=55, chain_potential='medium', stage='validated', status='in_progress', evidence_completeness=70),
    Finding(id='f-003', title='IDOR read on test tenant', severity='high', type='Access Control/IDOR', target_asset='api.example.com', chain_value=80, chain_potential='high', stage='validated', status='open', evidence_completeness=85),
    Finding(id='f-004', title='Public S3 bucket', severity='critical', type='Cloud/S3', target_asset='assets.example.com', chain_value=90, chain_potential='high', stage='exploited', status='in_progress', evidence_completeness=95),
    Finding(id='f-005', title='Outdated dependency', severity='medium', type='Supply/Dependency', target_asset='worker.example.com', chain_value=35, chain_potential='medium', stage='mitigated', status='closed', evidence_completeness=100),
]

@router.get('/findings', response_model=List[Finding])
def findings(chain_potential: Optional[str] = Query(default=None), stage: Optional[str] = Query(default=None), user: User = Depends(get_current_user)):
    data = _SAMPLE
    if chain_potential:
        data = [f for f in data if f.chain_potential == chain_potential]
    if stage:
        data = [f for f in data if f.stage == stage]
    return data
