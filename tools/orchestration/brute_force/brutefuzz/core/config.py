"""Configuration management for BruteFuzz"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
import json


@dataclass
class Config:
    """Global configuration container"""
    
    # Performance settings
    max_workers: int = 100
    connection_timeout: float = 10.0
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    # Rate limiting
    requests_per_second: float = 10.0
    adaptive_rate_limiting: bool = True
    jitter_range: tuple = (0.1, 0.5)
    
    # Evasion settings
    waf_evasion_enabled: bool = True
    user_agent_rotation: bool = True
    header_randomization: bool = True
    payload_encoding: List[str] = field(default_factory=lambda: ["url", "base64", "hex"])
    
    # AI Feedback settings
    ai_mutation_enabled: bool = True
    feedback_loop_interval: int = 50
    success_threshold: float = 0.01
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    real_time_stats: bool = True
    
    # Wordlist settings
    wordlist_paths: Dict[str, Path] = field(default_factory=dict)
    mutation_depth: int = 3
    
    @classmethod
    def from_json(cls, path: Path) -> "Config":
        with open(path, 'r') as f:
            data = json.load(f)
        return cls(**data)
    
    def to_json(self, path: Path) -> None:
        with open(path, 'w') as f:
            json.dump(self.__dict__, f, indent=2, default=str)
