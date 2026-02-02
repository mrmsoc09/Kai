from __future__ import annotations

from fastapi import APIRouter, Depends
from ..core.auth import get_current_user, User
from ..core.models import SystemState, MissionState, AgentState
from ..core.providers import get_provider_config
from ..core.vector_store import VectorStore

router = APIRouter(prefix='/state', tags=['state'])

@router.get('/global', response_model=SystemState)
def global_state(user: User = Depends(get_current_user)):
    return SystemState(comms_status='OPEN', knowledge_delta=0)

@router.get('/mission/{mid}', response_model=MissionState)
def mission_state(mid: str, user: User = Depends(get_current_user)):
    return MissionState(id=mid, name=f'Mission {mid}')

@router.get('/agent/{aid}', response_model=AgentState)
def agent_state(aid: str, user: User = Depends(get_current_user)):
    return AgentState(id=aid, name=f'Agent {aid}', role='analyst')


from typing import List
from ..core.models import AgentState

@router.get('/agents', response_model=List[AgentState])
def agents(user: User = Depends(get_current_user)):
    # Scaffolding only: return a minimal list; business logic populates later
    return [
        AgentState(id='u1', name='Recon-01', role='scanner', status='active'),
        AgentState(id='u2', name='Analyst-01', role='analyst', status='idle'),
        AgentState(id='u3', name='Operator-01', role='operator', status='paused'),
        AgentState(id='u4', name='Validator-01', role='validator', status='inactive'),
    ]


@router.get('/config')
def system_config(user: User = Depends(get_current_user)):
    providers = get_provider_config()
    vector = VectorStore().info()
    return {
        'providers': providers,
        'vector': vector,
        'hil_gate_enforced': True,
        'scope_policy': 'enforced'
    }
