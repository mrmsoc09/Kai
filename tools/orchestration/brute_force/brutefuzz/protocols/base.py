"""Base protocol handler interface"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class ProtocolResult:
    success: bool
    data: Optional[str] = None
    blocked: bool = False
    status_code: Optional[int] = None
    headers: Optional[Dict[str, str]] = None
    response_time: float = 0.0


class BaseProtocolHandler(ABC):
    """Abstract base class for protocol handlers"""
    
    def __init__(self, target: str, port: Optional[int] = None, 
                 use_ssl: bool = False, **kwargs):
        self.target = target
        self.port = port
        self.use_ssl = use_ssl
        self.options = kwargs
        self.session_data: Dict[str, Any] = {}
        
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to target"""
        pass
    
    @abstractmethod
    async def execute(self, payload: str) -> ProtocolResult:
        """Execute payload against target"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Clean up connections"""
        pass
    
    async def pre_flight(self) -> bool:
        """Pre-flight checks before campaign"""
        return True
