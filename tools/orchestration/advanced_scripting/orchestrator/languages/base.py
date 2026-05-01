"""
Base class for language handlers.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List


@dataclass
class ExecutionResult:
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    resource_stats: Dict[str, Any]


@dataclass
class LanguageContext:
    script_path: Path
    working_dir: Path
    environment: Dict[str, str]
    arguments: List[str]
    timeout: int
    memory_limit_mb: int
    cpu_limit_percent: float


class BaseLanguageHandler(ABC):
    """Abstract base class for language-specific execution handlers."""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        pass
    
    @abstractmethod
    def prepare(self, context: LanguageContext) -> bool:
        """Prepare the environment (install deps, compile, etc.)."""
        pass
    
    @abstractmethod
    def execute(self, context: LanguageContext) -> ExecutionResult:
        """Execute the script and return results."""
        pass
    
    @abstractmethod
    def validate_syntax(self, content: str) -> tuple[bool, Optional[str]]:
        """Validate script syntax without executing."""
        pass
    
    def get_interpreter(self) -> Optional[str]:
        """Return interpreter command if applicable."""
        return None
    
    def cleanup(self, context: LanguageContext):
        """Cleanup temporary files."""
        pass
