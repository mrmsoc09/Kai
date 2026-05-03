"""
K1 Platform Settings — Centralized configuration management using Pydantic Settings.

Provides type-safe, validated configuration with environment variable support
and sensible defaults for development and production.
"""
from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Set, Union

from pydantic import Field, PostgresDsn, RedisDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    url: PostgresDsn = Field(
        default="postgresql+asyncpg://k1:k1password@localhost:5432/k1",
        description="PostgreSQL connection URL",
    )
    pool_size: int = Field(default=20, ge=1, le=100)
    max_overflow: int = Field(default=10, ge=0, le=50)
    pool_timeout: int = Field(default=30, ge=1)
    echo: bool = Field(default=False, description="Log SQL queries")
    
    @field_validator("url", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure async driver is used."""
        if v.startswith("postgresql://") and "asyncpg" not in v:
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    url: RedisDsn = Field(
        default="redis://localhost:6379