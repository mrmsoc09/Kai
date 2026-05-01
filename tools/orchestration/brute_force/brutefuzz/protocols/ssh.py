"""SSH protocol handler for brute forcing"""
import asyncio
import asyncssh
from typing import Optional

from .base import BaseProtocolHandler, ProtocolResult


class SSHProtocolHandler(BaseProtocolHandler):
    """SSH brute force handler with key and password support"""
    
    def __init__(self, target: str, port: int = 22, username: str = "root",
                 auth_type: str = "password", **kwargs):
        super().__init__(target, port, False, **kwargs)
        self.username = username
        self.auth_type = auth_type
        self.known_hosts = None  # Disable host key verification for testing
        
    async def connect(self) -> bool:
        return True  # Connection per attempt
        
    async def execute(self, payload: str) -> ProtocolResult:
        """Attempt SSH authentication"""
        try:
            if self.auth_type == "password":
                async with asyncssh.connect(
                    self.target,
                    port=self.port,
                    username=self.username,
                    password=payload,
                    known_hosts=None,
                    connect_timeout=self.options.get("timeout", 10)
                ) as conn:
                    # If we get here, auth succeeded
                    return ProtocolResult(
                        success=True,
                        data=f"Authenticated with password: {payload[:2]}***"
                    )
            elif self.auth_type == "key":
                # Key-based auth logic would go here
                pass
                
        except asyncssh.PermissionDenied:
            return ProtocolResult(success=False, data="Authentication failed")
        except asyncssh.ConnectionRefused:
            return ProtocolResult(success=False, blocked=True, data="Connection refused")
        except asyncio.TimeoutError:
            return ProtocolResult(success=False, blocked=True, data="Timeout")
        except Exception as e:
            return ProtocolResult(success=False, data=str(e))
            
    async def disconnect(self):
        pass
