
from fastapi import APIRouter
from typing import Dict, Any
from ..core.obsidian import ObsidianConnector

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

@router.get('/status')
def status() -> Dict[str, Any]:
    return ObsidianConnector().status()

@router.post('/refresh')
def refresh() -> Dict[str, Any]:
    return ObsidianConnector().refresh()

@router.get('/notes')
def notes() -> Dict[str, Any]:
    return ObsidianConnector().list_notes()
