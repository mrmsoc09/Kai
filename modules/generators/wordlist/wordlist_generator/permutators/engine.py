"""High-performance permutation engine."""

import asyncio
from typing import Set, List, Optional
from concurrent.futures import ThreadPoolExecutor
import logging

from wordlist_generator.permutators.base import BasePermutator
from wordlist_generator.permutators.patterns import PatternLibrary
from wordlist_generator.core.config import PermutationConfig

logger = logging.getLogger(__name__)


class PermutationEngine(BasePermutator):
    """Advanced permutation engine with rule-based generation."""
    
    def __init__(self, config: PermutationConfig):
        self.config = config
        self.patterns = PatternLibrary()
        self.executor = ThreadPoolExecutor(max_workers=4)
        
    async def generate(self, keywords: Set[str]) -> Set[str]:
        """Generate all permutations based on configuration."""
        all_permutations = set()
        
        # Process in batches to avoid memory explosion
        batch_size = 100
        keyword_list = list(keywords)
        
        for i in range(0, len(keyword_list), batch_size):
            batch = keyword_list[i:i+batch_size]
            batch_results = await self._process_batch(batch)
            all_permutations.update(batch_results)
            
            # Check size limits
            if len(all_permutations) > 100000:  # Safety limit
                logger.warning("Permutation limit reached, truncating...")
                break
                
        return all_permutations
    
    async def _process_batch(self, keywords: List[str]) -> Set[str]:
        """Process a batch of keywords."""
        loop = asyncio.get_event_loop()
        tasks = []
        
        for keyword in keywords:
            task = loop.run_in_executor(
                self.executor, 
                self._permute_word, 
                keyword
            )
            tasks.append(task)
            
        results = await asyncio.gather(*tasks)
        
        combined = set()
        for result in results:
            combined.update(result)
        return combined
    
    def _permute_word(self, word: str) -> Set[str]:
        """Apply all enabled patterns to a single word."""
        results = {word}
        
        if "original" in self.config.patterns:
            results.add(word)
            
        if "lowercase" in self.config.patterns:
            results.add(word.lower())
            
        if "uppercase" in self.config.patterns:
            results.add(word.upper())
            
        if "capitalize" in self.config.patterns:
            results.add(word.capitalize())
            
        if "leet" in self.config.patterns:
            leet_vars = self.patterns.leet_speak(word)
            results.update(leet_vars)
            
        if "years" in self.config.patterns:
            year_vars = self.patterns.year_appendices(word)
            results.update(year_vars)
            
        if "special_chars" in self.config.patterns:
            special_vars = self.patterns.special_characters(word)
            results.update(special_vars)
            
        if "numbers" in self.config.patterns:
            num_vars = self.patterns.number_sequences(word, max_num=50)
            results.update(num_vars)
            
        if "keyboard" in self.config.patterns:
            key_vars = self.patterns.keyboard_patterns(word)
            results.update(key_vars)
            
        # Apply length filters
        filtered = {
            w for w in results 
            if self.config.min_length <= len(w) <= self.config.max_length
        }
        
        return filtered
