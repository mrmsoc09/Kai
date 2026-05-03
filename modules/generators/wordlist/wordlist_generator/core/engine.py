"""Core engine coordinating all components."""

import asyncio
from pathlib import Path
from typing import Optional
import logging

from wordlist_generator.core.config import WordlistConfig
from wordlist_generator.core.pipeline import WordlistPipeline

logger = logging.getLogger(__name__)


class WordlistEngine:
    """Main entry point for wordlist generation."""
    
    def __init__(self, config: WordlistConfig):
        self.config = config
        self.pipeline = WordlistPipeline(config)
        
    async def generate(self) -> Path:
        """Generate wordlist and save to file."""
        context = await self.pipeline.execute()
        
        # Write to file
        output_path = self.config.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for word in sorted(context.final_wordlist):
                f.write(f"{word}\n")
                
        logger.info(f"Wordlist saved to {output_path}")
        return output_path
    
    async def generate_streaming(self, callback=None):
        """Generate wordlist with streaming output."""
        async for word in self.pipeline.stream_wordlist():
            if callback:
                await callback(word)
            yield word
