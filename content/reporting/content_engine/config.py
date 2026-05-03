"""
Configuration management for the Content Generation Engine.
Supports environment variables and YAML configuration files.
"""

import os
from pathlib import Path
from typing import Optional, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_prefix="CGE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Template directories
    template_dir: Path = Field(default=Path(__file__).parent / "templates")
    output_dir: Path = Field(default=Path("./output"))
    
    # Content generation settings
    default_classification: str = Field(default="UNCLASSIFIED")
    default_author: str = Field(default="Content Engine")
    organization: str = Field(default="Organization")
    
    # Processing
    max_workers: int = Field(default=4)
    enable_markdown_validation: bool = Field(default=True)
    
    # Specific content type settings
    intel_classification_levels: List[str] = Field(
        default=["UNCLASSIFIED", "CONFIDENTIAL", "SECRET", "TOP SECRET"]
    )
    contracting_agencies: List[str] = Field(default=[])
    
    @field_validator("template_dir", "output_dir")
    @classmethod
    def validate_paths(cls, v: Path) -> Path:
        return v.expanduser().resolve()
    
    def ensure_directories(self) -> None:
        """Ensure required directories exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.template_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
