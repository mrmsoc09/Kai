from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends
from ..core.auth import get_current_user, User
from ..core.models import MCPServer

router = APIRouter(prefix='/mcp', tags=['mcp'])

@router.get('/servers', response_model=List[MCPServer])
def servers(user: User = Depends(get_current_user)):
    return [
        MCPServer(id='mcp-graph', name='Graph Builder', status='online', uptime_seconds=86400*3+4200, purpose='feeds graph'),
        MCPServer(id='mcp-validate', name='Validator', status='degraded', uptime_seconds=3600*5+33, purpose='validates findings'),
        MCPServer(id='mcp-osint', name='OSINT Feeds', status='online', uptime_seconds=86400*1+120, purpose='collects signals'),
        MCPServer(id='mcp-export', name='Export Bridge', status='offline', uptime_seconds=0, purpose='reports and export'),
    ]
