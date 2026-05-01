"""Advanced wordlist generation strategies"""
import asyncio
import itertools
import random
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional, Set
from pathlib import Path


class WordlistGenerator(ABC):
    """Base class for wordlist generation strategies"""
    
    @abstractmethod
    async def generate(self) -> AsyncIterator[str]:
        """Yield payloads asynchronously"""
        pass
    
    @abstractmethod
    def estimate_size(self) -> Optional[int]:
        """Estimate total payload count (None if infinite)"""
        pass


class FileWordlistGenerator(WordlistGenerator):
    """Generator from file-based wordlists"""
    
    def __init__(self, filepath: Path, encoding: str = "utf-8", 
                 shuffle: bool = False):
        self.filepath = filepath
        self.encoding = encoding
        self.shuffle = shuffle
        self._cache: Optional[List[str]] = None
        
    async def generate(self) -> AsyncIterator[str]:
        if self.shuffle and self._cache is None:
            self._cache = []
            with open(self.filepath, 'r', encoding=self.encoding) as f:
                self._cache = [line.strip() for line in f if line.strip()]
            random.shuffle(self._cache)
            for item in self._cache:
                yield item
        else:
            with open(self.filepath, 'r', encoding=self.encoding) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield line
                        
    def estimate_size(self) -> Optional[int]:
        try:
            with open(self.filepath, 'r', encoding=self.encoding) as f:
                return sum(1 for _ in f)
        except:
            return None


class CombinationGenerator(WordlistGenerator):
    """Generate combinations from multiple sources"""
    
    def __init__(self, generators: List[WordlistGenerator], 
                 separator: str = "", max_combinations: Optional[int] = None):
        self.generators = generators
        self.separator = separator
        self.max_combinations = max_combinations
        
    async def generate(self) -> AsyncIterator[str]:
        iterators = [g.generate() for g in self.generators]
        # Simplified: Cartesian product of first two generators
        if len(self.generators) == 2:
            cache2 = []
            async for item in iterators[1]:
                cache2.append(item)
                
            count = 0
            async for item1 in iterators[0]:
                for item2 in cache2:
                    if self.max_combinations and count >= self.max_combinations:
                        return
                    yield f"{item1}{self.separator}{item2}"
                    count += 1
        else:
            async for item in iterators[0]:
                yield item
                
    def estimate_size(self) -> Optional[int]:
        sizes = [g.estimate_size() for g in self.generators]
        if None in sizes:
            return None
        result = 1
        for s in sizes:
            result *= s
        return result if self.max_combinations is None else min(result, self.max_combinations)


class MutationGenerator(WordlistGenerator):
    """Apply mutations to base wordlist"""
    
    MUTATIONS = [
        lambda x: x.upper(),
        lambda x: x.lower(),
        lambda x: x.capitalize(),
        lambda x: x + "123",
        lambda x: x + "!",
        lambda x: x.replace('a', '@'),
        lambda x: x.replace('e', '3'),
        lambda x: x.replace('i', '1'),
        lambda x: x.replace('o', '0'),
        lambda x: x[::-1],  # Reverse
    ]
    
    def __init__(self, base_generator: WordlistGenerator, 
                 depth: int = 1, custom_mutations: Optional[List] = None):
        self.base = base_generator
        self.depth = depth
        self.mutations = custom_mutations or self.MUTATIONS
        
    async def generate(self) -> AsyncIterator[str]:
        async for word in self.base.generate():
            yield word  # Original
            
            # Apply mutations
            for mutation in self.mutations:
                try:
                    mutated = mutation(word)
                    if mutated != word:
                        yield mutated
                except:
                    continue
                    
    def estimate_size(self) -> Optional[int]:
        base = self.base.estimate_size()
        if base is None:
            return None
        return base * (len(self.mutations) + 1)
