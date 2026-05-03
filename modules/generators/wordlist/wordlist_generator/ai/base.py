"""Abstract base for AI expansion providers."""

from abc import ABC, abstractmethod
from typing import Set


class BaseAIProvider(ABC):
    """Abstract base for AI keyword expansion."""
    
    @abstractmethod
    async def expand(self, keyword: str, context: str) -> Set[str]:
        """Expand keyword into related variations."""
        pass
    
    @abstractmethod
    def analyze_context(self, keywords: Set[str], target: str) -> dict:
        """Analyze context and return metadata for expansion."""
        pass
