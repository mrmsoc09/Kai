"""Filter chain implementation."""

from abc import ABC, abstractmethod
from typing import Set, List
import re
import math


class BaseFilter(ABC):
    """Abstract base for filters."""
    
    @abstractmethod
    def apply(self, wordlist: Set[str]) -> Set[str]:
        """Filter wordlist and return filtered set."""
        pass


class FilterChain:
    """Chain of responsibility for filtering."""
    
    def __init__(self, config):
        self.config = config
        self.filters: List[BaseFilter] = []
        self._build_chain()
        
    def _build_chain(self):
        """Initialize filter chain based on config."""
        self.filters.append(LengthFilter(self.config))
        self.filters.append(EntropyFilter(self.config))
        self.filters.append(PatternFilter(self.config))
        self.filters.append(DuplicateFilter(self.config))
        
    def apply(self, wordlist: Set[str]) -> Set[str]:
        """Apply all filters in chain."""
        result = wordlist
        for filter_obj in self.filters:
            result = filter_obj.apply(result)
        return result


class LengthFilter(BaseFilter):
    """Filter by length constraints."""
    
    def __init__(self, config):
        self.min_length = getattr(config, 'min_length', 4)
        self.max_length = getattr(config, 'max_length', 32)
        
    def apply(self, wordlist: Set[str]) -> Set[str]:
        return {
            w for w in wordlist 
            if self.min_length <= len(w) <= self.max_length
        }


class EntropyFilter(BaseFilter):
    """Filter by entropy/complexity."""
    
    def __init__(self, config):
        self.min_entropy = getattr(config, 'min_entropy', 2.0)
        
    def apply(self, wordlist: Set[str]) -> Set[str]:
        return {w for w in wordlist if self._calculate_entropy(w) >= self.min_entropy}
    
    def _calculate_entropy(self, word: str) -> float:
        """Calculate Shannon entropy."""
        if not word:
            return 0.0
        prob = [float(word.count(c)) / len(word) for c in dict.fromkeys(list(word))]
        entropy = - sum([p * math.log2(p) for p in prob])
        return entropy


class PatternFilter(BaseFilter):
    """Filter out excluded patterns."""
    
    def __init__(self, config):
        self.exclude_patterns = [
            re.compile(pattern) 
            for pattern in getattr(config, 'exclude_patterns', [])
        ]
        
    def apply(self, wordlist: Set[str]) -> Set[str]:
        if not self.exclude_patterns:
            return wordlist
            
        filtered = set()
        for word in wordlist:
            if not any(pattern.match(word) for pattern in self.exclude_patterns):
                filtered.add(word)
        return filtered


class DuplicateFilter(BaseFilter):
    """Filter near-duplicates."""
    
    def __init__(self, config):
        self.max_duplicate_ratio = getattr(config, 'max_duplicate_ratio', 0.8)
        
    def apply(self, wordlist: Set[str]) -> Set[str]:
        # Simple implementation: remove obvious duplicates (already a set)
        # Advanced: fuzzy matching (omitted for performance)
        return wordlist
