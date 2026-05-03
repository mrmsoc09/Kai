"""Configuration management for the wordlist generator."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pathlib import Path


class ScraperConfig(BaseModel):
    """Configuration for web scraping module."""
    max_depth: int = Field(default=2, ge=1, le=5)
    max_pages: int = Field(default=50, ge=1, le=1000)
    respect_robots_txt: bool = True
    delay: float = Field(default=1.0, ge=0.1)
    timeout: int = Field(default=30, ge=5)
    user_agent: str = "WordlistGenerator/1.0 (Security Research Tool)"
    headers: Dict[str, str] = Field(default_factory=dict)


class AIConfig(BaseModel):
    """Configuration for AI-driven expansion."""
    enabled: bool = True
    context_window_size: int = Field(default=4096, ge=1024)
    temperature: float = Field(default=0.7, ge=0.0, le=1.0)
    max_expansions_per_keyword: int = Field(default=10, ge=1, le=100)
    semantic_similarity_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    api_endpoint: Optional[str] = None
    api_key: Optional[str] = None
    local_fallback: bool = True


class PermutationConfig(BaseModel):
    """Configuration for permutation engine."""
    enabled: bool = True
    max_length: int = Field(default=32, ge=8, le=128)
    min_length: int = Field(default=4, ge=1, le=16)
    patterns: List[str] = Field(default_factory=lambda: [
        "original",
        "uppercase",
        "lowercase",
        "capitalize",
        "leet",
        "years",
        "special_chars"
    ])
    custom_masks: List[str] = Field(default_factory=list)
    mutation_depth: int = Field(default=2, ge=1, le=5)


class FilterConfig(BaseModel):
    """Configuration for output filters."""
    min_entropy: float = Field(default=2.0, ge=0.0)
    max_duplicate_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    exclude_patterns: List[str] = Field(default_factory=list)
    require_complexity: bool = True


class WordlistConfig(BaseModel):
    """Main configuration container."""
    target: str
    output_path: Path
    scraper: ScraperConfig = Field(default_factory=ScraperConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    permutation: PermutationConfig = Field(default_factory=PermutationConfig)
    filter: FilterConfig = Field(default_factory=FilterConfig)
    verbose: bool = False
    max_workers: int = Field(default=4, ge=1, le=16)
