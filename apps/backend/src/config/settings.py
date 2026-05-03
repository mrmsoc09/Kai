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
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )
    password: Optional[str] = Field(default=None, description="Redis password")
    db: int = Field(default=0, ge=0, le=15)
    max_connections: int = Field(default=20, ge=1)
    
    @field_validator("url", mode="before")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        """Ensure redis URL has database number."""
        if v and not v.endswith(("/0", "/1", "/2", "/3", "/4", "/5", "/6", "/7", "/8", "/9")):
            v = f"{v}/0" if not v.endswith("/") else f"{v}0"
        return v


class SecuritySettings(BaseSettings):
    """Security and authentication settings."""
    
    jwt_secret: str = Field(
        default="dev-secret-change-in-production",
        description="JWT signing secret",
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=60, ge=1)
    refresh_token_expire_days: int = Field(default=7, ge=1)
    
    # API Keys
    admin_api_key: Optional[str] = Field(default=None)
    dev_token: Optional[str] = Field(default=None)
    
    # Bootstrap
    bootstrap_admin_enabled: bool = Field(default=True)
    bootstrap_admin_username: str = Field(default="k1-admin")
    bootstrap_tenant_name: str = Field(default="kai-local")
    
    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:8081", "http://localhost:3000"])
    cors_allow_credentials: bool = Field(default=True)
    
    # Security Headers
    force_https: bool = Field(default=False)
    secure_cookies: bool = Field(default=False)
    hsts_max_age: int = Field(default=31536000)


class LLMSettings(BaseSettings):
    """LLM provider configuration."""
    
    primary_provider: str = Field(default="anthropic")
    fallback_providers: List[str] = Field(default=["openai", "gemini", "ollama"])
    
    # API Keys
    anthropic_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    google_api_key: Optional[str] = Field(default=None)
    
    # Ollama
    ollama_base_url: str = Field(default="http://localhost:11434")
    ollama_model: str = Field(default="llama3.1:8b")
    ollama_auto_pull: bool = Field(default=True)
    ollama_managed_externally: bool = Field(default=False)
    max_local_model_b: int = Field(default=9, ge=1)
    
    # Model selection
    patch_llm_model: str = Field(default="claude-opus-4-5")
    validation_llm_model: str = Field(default="claude-3-haiku-20240307")


class VaultSettings(BaseSettings):
    """HashiCorp Vault configuration."""
    
    addr: Optional[str] = Field(default="http://localhost:8200", alias="VAULT_ADDR")
    token: Optional[str] = Field(default=None, alias="VAULT_TOKEN")
    namespace: Optional[str] = Field(default="k1", alias="VAULT_NAMESPACE")
    mount_point: str = Field(default="secret")
    secret_prefix: str = Field(default="kai")


class IntegrationSettings(BaseSettings):
    """External service integrations."""
    
    # TheHive
    thehive_url: Optional[str] = Field(default=None)
    thehive_api_key: Optional[str] = Field(default=None)
    
    # Cortex
    cortex_url: Optional[str] = Field(default=None)
    cortex_api_key: Optional[str] = Field(default=None)
    
    # Wazuh
    wazuh_url: Optional[str] = Field(default=None)
    wazuh_username: Optional[str] = Field(default=None)
    wazuh_password: Optional[str] = Field(default=None)
    
    # Shuffle
    shuffle_url: Optional[str] = Field(default=None)
    shuffle_webhook_token: Optional[str] = Field(default=None)
    
    # External Intel
    shodan_api_key: Optional[str] = Field(default=None)
    virustotal_api_key: Optional[str] = Field(default=None)
    censys_api_id: Optional[str] = Field(default=None)
    censys_api_secret: Optional[str] = Field(default=None)
    
    # Tool-specific keys
    fullhunt_api_key: Optional[str] = Field(default=None)
    leakix_api_key: Optional[str] = Field(default=None)
    dehashed_api_key: Optional[str] = Field(default=None)
    grayhatwarfare_api_key: Optional[str] = Field(default=None)
    nvd_nist_api_key: Optional[str] = Field(default=None)
    ipinfo_api_key: Optional[str] = Field(default=None)


class FeatureFlags(BaseSettings):
    """Feature toggle configuration."""
    
    patch_engine: bool = Field(default=True)
    auto_validation: bool = Field(default=True)
    auto_scheduling: bool = Field(default=False)
    platform_submissions: bool = Field(default=False)
    osint_enabled: bool = Field(default=True)
    external_queries_enabled: bool = Field(default=False)
    nuclei_enabled: bool = Field(default=True)


class Settings(BaseSettings):
    """Main application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Environment
    environment: str = Field(default="development")
    debug_mode: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # Host/Port
    backend_host: str = Field(default="0.0.0.0")
    backend_port: int = Field(default=8080, ge=1, le=65535)
    backend_url: str = Field(default="http://localhost:8080")
    frontend_url: str = Field(default="http://localhost:8081")
    
    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    vault: VaultSettings = Field(default_factory=VaultSettings)
    integrations: IntegrationSettings = Field(default_factory=IntegrationSettings)
    features: FeatureFlags = Field(default_factory=FeatureFlags)
    
    # Paths
    artifacts_root: Path = Field(default=Path("artifacts"))
    tool_registry_path: Path = Field(default=Path("tools/registry/tool_registry.yaml"))
    scope_policy_path: Path = Field(default=Path("config/scope_guardrails.yaml"))
    
    # Celery
    celery_result_key: Optional[str] = Field(default=None)
    celery_security_key: Optional[str] = Field(default=None)
    celery_security_cert: Optional[str] = Field(default=None)
    celery_security_cert_dir: Optional[str] = Field(default=None)
    
    # Startup validation
    startup_validate_dependencies: bool = Field(default=True)
    startup_validate_secrets: bool = Field(default=True)
    startup_validate_toolpacks: bool = Field(default=False)
    bootstrap_require_external_tools: bool = Field(default=True)
    
    # Test mode
    test_mode: bool = Field(default=False)
    relax_auth_gates_for_tests: bool = Field(default=False)
    
    @field_validator("artifacts_root", mode="before")
    @classmethod
    def validate_path(cls, v: Union[str, Path]) -> Path:
        """Ensure path is a Path object."""
        if isinstance(v, str):
            return Path(v)
        return v


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance for import
settings = get_settings()
