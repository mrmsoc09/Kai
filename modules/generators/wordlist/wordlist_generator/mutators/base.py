"""Mutator chain for final transformations."""

from abc import ABC, abstractmethod
from typing import Set, List
import asyncio


class BaseMutator(ABC):
    """Abstract base for mutators."""
    
    @abstractmethod
    async def mutate(self, wordlist: Set[str]) -> Set[str]:
        """Apply mutation to wordlist."""
        pass


class MutatorChain:
    """Chain of mutators."""
    
    def __init__(self):
        self.mutators: List[BaseMutator] = []
        self._build_chain()
        
    def _build_chain(self):
        """Initialize mutators."""
        self.mutators.append(CaseMutator())
        self.mutators.append(CommonAppendMutator())
        
    async def apply(self, wordlist: Set[str]) -> Set[str]:
        """Apply all mutators."""
        result = wordlist
        for mutator in self.mutators:
            result = await mutator.mutate(result)
        return result


class CaseMutator(BaseMutator):
    """Mutate case variations."""
    
    async def mutate(self, wordlist: Set[str]) -> Set[str]:
        # Already handled by permutator, but ensure coverage
        return wordlist


class CommonAppendMutator(BaseMutator):
    """Append common suffixes/prefixes."""
    
    async def mutate(self, wordlist: Set[str]) -> Set[str]:
        additions = set()
        common_suffixes = ['1', '123', '!', '.', '?']
        
        for word in wordlist:
            for suffix in common_suffixes:
                additions.add(f"{word}{suffix}")
                
        return wordlist.union(additions)
