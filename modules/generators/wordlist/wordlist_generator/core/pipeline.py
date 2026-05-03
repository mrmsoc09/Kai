"""Processing pipeline for wordlist generation."""

import asyncio
from typing import List, Set, AsyncIterator, Optional
from dataclasses import dataclass, field
import logging

from wordlist_generator.core.config import WordlistConfig
from wordlist_generator.scrapers.web_scraper import WebScraper
from wordlist_generator.ai.kimi_logic import KimiK25Logic
from wordlist_generator.permutators.engine import PermutationEngine
from wordlist_generator.filters.base import FilterChain
from wordlist_generator.mutators.base import MutatorChain

logger = logging.getLogger(__name__)


@dataclass
class PipelineContext:
    """Context object passed through pipeline stages."""
    target: str
    raw_keywords: Set[str] = field(default_factory=set)
    expanded_keywords: Set[str] = field(default_factory=set)
    permutations: Set[str] = field(default_factory=set)
    final_wordlist: Set[str] = field(default_factory=set)
    metadata: dict = field(default_factory=dict)


class WordlistPipeline:
    """Orchestrates the wordlist generation workflow."""
    
    def __init__(self, config: WordlistConfig):
        self.config = config
        self.scraper = WebScraper(config.scraper)
        self.ai_expander = KimiK25Logic(config.ai) if config.ai.enabled else None
        self.permutator = PermutationEngine(config.permutation)
        self.filter_chain = FilterChain(config.filter)
        self.mutator_chain = MutatorChain()
        
    async def execute(self) -> PipelineContext:
        """Execute the full pipeline."""
        context = PipelineContext(target=self.config.target)
        
        # Stage 1: Web Scraping
        logger.info("Stage 1: Scraping target for keywords...")
        context.raw_keywords = await self._scrape_keywords()
        logger.info(f"Collected {len(context.raw_keywords)} raw keywords")
        
        # Stage 2: AI Expansion
        if self.ai_expander:
            logger.info("Stage 2: Expanding keywords with AI logic...")
            context.expanded_keywords = await self._expand_keywords(context.raw_keywords)
            logger.info(f"Expanded to {len(context.expanded_keywords)} keywords")
        else:
            context.expanded_keywords = context.raw_keywords
            
        # Stage 3: Permutation
        logger.info("Stage 3: Generating permutations...")
        context.permutations = await self._generate_permutations(context.expanded_keywords)
        logger.info(f"Generated {len(context.permutations)} permutations")
        
        # Stage 4: Filtering and Mutation
        logger.info("Stage 4: Applying filters and mutations...")
        context.final_wordlist = await self._filter_and_mutate(context.permutations)
        logger.info(f"Final wordlist contains {len(context.final_wordlist)} entries")
        
        return context
    
    async def _scrape_keywords(self) -> Set[str]:
        """Scrape target for initial keywords."""
        return await self.scraper.scrape(self.config.target)
    
    async def _expand_keywords(self, keywords: Set[str]) -> Set[str]:
        """Expand keywords using AI-driven logic."""
        if not self.ai_expander:
            return keywords
            
        expanded = set(keywords)
        for keyword in keywords:
            try:
                variations = await self.ai_expander.expand(keyword, self.config.target)
                expanded.update(variations)
            except Exception as e:
                logger.warning(f"Failed to expand keyword '{keyword}': {e}")
        return expanded
    
    async def _generate_permutations(self, keywords: Set[str]) -> Set[str]:
        """Generate permutations for all keywords."""
        return await self.permutator.generate(keywords)
    
    async def _filter_and_mutate(self, candidates: Set[str]) -> Set[str]:
        """Apply filters and mutations."""
        # First pass: filtering
        filtered = self.filter_chain.apply(candidates)
        
        # Second pass: mutations
        mutated = await self.mutator_chain.apply(filtered)
        
        # Final filter
        return self.filter_chain.apply(mutated)
    
    async def stream_wordlist(self) -> AsyncIterator[str]:
        """Stream wordlist entries for memory-efficient processing."""
        context = await self.execute()
        for entry in context.final_wordlist:
            yield entry
