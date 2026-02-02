from __future__ import annotations

from typing import List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from ..core.auth import get_current_user, User
from ..core.models import Persona

router = APIRouter(prefix='/personas', tags=['personas'])

now = datetime.now(timezone.utc)
SAMPLE: List[Persona] = [
    Persona(id='p-recon', role='Reconnaissance Lead', knowledge_count=182, last_training_update=now - timedelta(days=2), confidence_trend=[62,65,67,69,70,72,74], maturity='mature', rentable=True, plan='subscription'),
    Persona(id='p-scanner', role='Dual-Path Scanner', knowledge_count=134, last_training_update=now - timedelta(days=5), confidence_trend=[45,47,49,52,55,57,59], maturity='growing', rentable=True, plan='rental'),
    Persona(id='p-validator', role='Safe Validator', knowledge_count=96, last_training_update=now - timedelta(days=10), confidence_trend=[50,50,51,52,52,53,54], maturity='growing', rentable=False, plan='internal'),
    Persona(id='p-impact', role='Impact/CVSS Analyst', knowledge_count=210, last_training_update=now - timedelta(days=1), confidence_trend=[70,72,73,74,76,78,80], maturity='mature', rentable=True, plan='subscription'),
]

@router.get('/', response_model=List[Persona])
def list_personas(user: User = Depends(get_current_user)):
    return SAMPLE
