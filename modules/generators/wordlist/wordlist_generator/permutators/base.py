"""Abstract base for permutators."""

from abc import ABC, abstractmethod
from typing import Set


class BasePermutator(ABC):
    """Abstract base for permutation engines."""
    
    @abstractmethod
    async def generate(self, keywords: Set[str]) -> Set[str]:
        """Generate permutations for given keywords."""
        pass
