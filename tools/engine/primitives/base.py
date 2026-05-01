"""
Base classes for all tool primitives.
Defines the interface contract for modular components.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class PrimitiveMetadata:
    """Metadata describing a primitive's capabilities and requirements."""
    name: str
    version: str
    category: str  # scanner, exploit, parser, etc.
    description: str
    author: str
    risk_level: str  # low, medium, high, critical
    required_permissions: List[str]
    dependencies: List[str]


class BasePrimitive(ABC):
    """
    Abstract base class for all security tool primitives.
    Enforces consistent interface across all components.
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.metadata = self._define_metadata()
        self.state = {}
        
    @abstractmethod
    def _define_metadata(self) -> PrimitiveMetadata:
        """Define primitive metadata. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Main execution entry point. Must be implemented by subclasses."""
        pass
    
    def validate_config(self) -> bool:
        """Validate configuration parameters."""
        return True
    
    def get_state(self) -> Dict[str, Any]:
        """Return current internal state."""
        return self.state.copy()
    
    def reset(self):
        """Reset primitive to initial state."""
        self.state = {}


class PrimitiveLibrary:
    """
    Registry of available primitives.
    Provides discovery and instantiation capabilities.
    """
    
    def __init__(self):
        self._primitives = {}
        self._register_defaults()
    
    def _register_defaults(self):
        """Register built-in primitives."""
        # Import here to avoid circular dependencies
        from .scanner import TCPScanner, UDPScanner, ServiceDetector
        from .exploit import RemoteExploit, LocalExploit, WebExploit
        from .parser import LogParser, PCAPParser, JSONAnalyzer
        
        primitives = [
            TCPScanner, UDPScanner, ServiceDetector,
            RemoteExploit, LocalExploit, WebExploit,
            LogParser, PCAPParser, JSONAnalyzer
        ]
        
        for primitive in primitives:
            self.register(primitive)
    
    def register(self, primitive_class):
        """Register a primitive class."""
        name = primitive_class.__name__
        self._primitives[name] = primitive_class
    
    def get(self, name: str) -> Optional[type]:
        """Retrieve a primitive class by name."""
        return self._primitives.get(name)
    
    def list_by_category(self, category: str) -> List[type]:
        """List all primitives in a category."""
        return [p for p in self._primitives.values() 
                if hasattr(p, 'CATEGORY') and p.CATEGORY == category]
    
    def get_all(self) -> Dict[str, type]:
        """Get all registered primitives."""
        return self._primitives.copy()
    
    def get_compatible_primitives(self, input_type: str, output_type: str) -> List[type]:
        """
        Find primitives that can transform input_type to output_type.
        Used for automatic pipeline construction.
        """
        compatible = []
        for name, cls in self._primitives.items():
            if hasattr(cls, 'INPUT_TYPES') and hasattr(cls, 'OUTPUT_TYPES'):
                if input_type in cls.INPUT_TYPES and output_type in cls.OUTPUT_TYPES:
                    compatible.append(cls)
        return compatible
