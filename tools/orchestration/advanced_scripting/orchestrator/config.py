"""
Configuration management for the Advanced Scripting Orchestrator.
"""
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecutionConfig:
    max_memory_mb: int = 512
    max_cpu_percent: float = 50.0
    max_execution_time: int = 300  # seconds
    sandbox_enabled: bool = True
    allowed_network: bool = False
    temp_dir: str = "/tmp/orchestrator_sandbox"


@dataclass
class DatabaseConfig:
    url: str = "sqlite:///orchestrator.db"
    echo: bool = False
    pool_size: int = 5


@dataclass
class AIConfig:
    model_endpoint: str = "https://api.moonshot.cn/v1/chat/completions"
    api_key: Optional[str] = None
    model_name: str = "kimi-k2.5"
    max_tokens: int = 4096
    temperature: float = 0.2


@dataclass
class OrchestratorConfig:
    db: DatabaseConfig = None
    execution: ExecutionConfig = None
    ai: AIConfig = None
    log_level: str = "INFO"
    
    def __post_init__(self):
        if self.db is None:
            self.db = DatabaseConfig()
        if self.execution is None:
            self.execution = ExecutionConfig()
        if self.ai is None:
            self.ai = AIConfig(api_key=os.getenv("KIMI_API_KEY"))


# Global config instance
config = OrchestratorConfig()
