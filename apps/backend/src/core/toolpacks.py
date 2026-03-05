from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
from typing import Dict, Iterable, List, Optional, Set

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator


class ToolpackValidationError(RuntimeError):
    """Raised when toolpack configuration is invalid or unsafe."""


class PlatformConfig(BaseModel):
    primary_os: List[str] = Field(default_factory=list)
    compatible_os: List[str] = Field(default_factory=list)
    tools_root: str = "/opt/kai/tools"
    artifacts_root: str = "/opt/kai/artifacts"
    cache_root: str = "/opt/kai/cache"


class ToolSafetyConfig(BaseModel):
    requires_scope: bool = True
    rate_limit_class: str = "medium"
    forbidden_flags: List[str] = Field(default_factory=list)


class ToolAdapterMapping(BaseModel):
    id: str
    adapter_id: str
    enabled: bool = True
    method: str
    evidence_type: str
    integration_mode: str = "local_cli"
    binary: Optional[str] = None
    allowed_targets: List[str] = Field(default_factory=list)
    safety: ToolSafetyConfig = Field(default_factory=ToolSafetyConfig)

    @field_validator("id", "adapter_id", "method", "evidence_type")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("must be non-empty")
        return value.strip()


class ToolpackDefinition(BaseModel):
    description: str
    enabled: bool = True
    opsec_profile: str = "medium"
    allowed_methods: List[str] = Field(default_factory=list)
    tools: List[ToolAdapterMapping] = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("description must be non-empty")
        return value.strip()


class ToolpackConfig(BaseModel):
    schema_version: str
    platform: PlatformConfig
    toolpacks: Dict[str, ToolpackDefinition] = Field(default_factory=dict)

    @field_validator("schema_version")
    @classmethod
    def _validate_version(cls, value: str) -> str:
        if value != "1.0":
            raise ValueError("unsupported schema_version")
        return value


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


DEFAULT_TOOLPACKS_PATH = _repo_root() / "ops" / "toolpacks.yaml"
FALLBACK_TOOLPACKS_PATH = _repo_root() / "configs" / "toolpacks.yaml"


def _toolpacks_path_from_env_or_default() -> Path:
    env_path = os.getenv("K1_TOOLPACKS_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()
    return DEFAULT_TOOLPACKS_PATH


def _split_csv_env(name: str) -> Set[str]:
    raw = os.getenv(name, "").strip()
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


class ToolpackManager:
    """
    Loads, validates, and resolves toolpack->adapter mappings.

    Resolution is fail-closed for enabled toolpacks: every enabled tool mapping
    must resolve to a registered adapter ID at startup.
    """

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or _toolpacks_path_from_env_or_default()
        self.config: Optional[ToolpackConfig] = None
        self._enabled_overrides: Dict[str, bool] = {}
        self._resolved_mapping: Dict[str, str] = {}
        self._enabled_adapter_ids: Set[str] = set()
        self._managed_adapter_ids: Set[str] = set()
        self._adapter_methods: Dict[str, str] = {}

    def load(self) -> ToolpackConfig:
        target = self.config_path
        if not target.exists() and target == DEFAULT_TOOLPACKS_PATH and FALLBACK_TOOLPACKS_PATH.exists():
            target = FALLBACK_TOOLPACKS_PATH
        if not target.exists():
            raise ToolpackValidationError(f"toolpack config not found: {target}")

        try:
            self.config = self._load_config_path(target)
            self.config_path = target
        except ValidationError as exc:
            if target == DEFAULT_TOOLPACKS_PATH and FALLBACK_TOOLPACKS_PATH.exists():
                self.config = self._load_config_path(FALLBACK_TOOLPACKS_PATH)
                self.config_path = FALLBACK_TOOLPACKS_PATH
            else:
                raise ToolpackValidationError(f"toolpack schema validation failed: {exc}") from exc
        except yaml.YAMLError as exc:
            if target == DEFAULT_TOOLPACKS_PATH and FALLBACK_TOOLPACKS_PATH.exists():
                self.config = self._load_config_path(FALLBACK_TOOLPACKS_PATH)
                self.config_path = FALLBACK_TOOLPACKS_PATH
            else:
                raise ToolpackValidationError(f"toolpack YAML parse failed: {exc}") from exc

        self._apply_env_overrides()
        return self.config

    def _load_config_path(self, path: Path) -> ToolpackConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ToolpackConfig.model_validate(raw)

    def _apply_env_overrides(self) -> None:
        if not self.config:
            return

        for name in _split_csv_env("K1_TOOLPACKS_ENABLE"):
            self._enabled_overrides[name] = True
        for name in _split_csv_env("K1_TOOLPACKS_DISABLE"):
            self._enabled_overrides[name] = False

    def set_toolpack_enabled(self, toolpack_name: str, enabled: bool) -> None:
        self._enabled_overrides[toolpack_name] = enabled

    def is_toolpack_enabled(self, toolpack_name: str) -> bool:
        if not self.config:
            raise ToolpackValidationError("toolpack config not loaded")
        base = self.config.toolpacks.get(toolpack_name)
        if not base:
            raise ToolpackValidationError(f"unknown toolpack: {toolpack_name}")
        return self._enabled_overrides.get(toolpack_name, base.enabled)

    def enabled_toolpacks(self) -> Dict[str, ToolpackDefinition]:
        if not self.config:
            raise ToolpackValidationError("toolpack config not loaded")
        return {
            name: definition
            for name, definition in self.config.toolpacks.items()
            if self.is_toolpack_enabled(name)
        }

    def resolve_mappings(self, registered_adapter_ids: Iterable[str]) -> Dict[str, str]:
        if not self.config:
            raise ToolpackValidationError("toolpack config not loaded")

        known_adapters = set(registered_adapter_ids)
        resolved: Dict[str, str] = {}
        enabled_adapters: Set[str] = set()
        managed_adapters: Set[str] = set()
        adapter_methods: Dict[str, str] = {}
        unresolved: List[str] = []

        for toolpack_name, toolpack in self.enabled_toolpacks().items():
            for tool in toolpack.tools:
                managed_adapters.add(tool.adapter_id)
                if tool.enabled:
                    adapter_methods[tool.adapter_id] = tool.method
                if not tool.enabled:
                    continue
                if tool.adapter_id not in known_adapters:
                    unresolved.append(f"{toolpack_name}.{tool.id}->{tool.adapter_id}")
                    continue
                if tool.id in resolved and resolved[tool.id] != tool.adapter_id:
                    raise ToolpackValidationError(
                        f"conflicting adapter mapping for '{tool.id}': "
                        f"{resolved[tool.id]} vs {tool.adapter_id}"
                    )
                resolved[tool.id] = tool.adapter_id
                enabled_adapters.add(tool.adapter_id)

        if unresolved:
            raise ToolpackValidationError(
                "unresolved toolpack adapter mappings: " + ", ".join(sorted(unresolved))
            )

        self._resolved_mapping = resolved
        self._enabled_adapter_ids = enabled_adapters
        self._managed_adapter_ids = managed_adapters
        self._adapter_methods = adapter_methods
        return dict(self._resolved_mapping)

    def enabled_adapter_ids(self) -> Set[str]:
        return set(self._enabled_adapter_ids)

    def is_adapter_enabled(self, adapter_id: str) -> bool:
        """
        Return True for unmanaged adapters; managed adapters must be enabled.
        """
        if adapter_id not in self._managed_adapter_ids:
            return True
        return adapter_id in self._enabled_adapter_ids

    def get_method_for_adapter(self, adapter_id: str) -> Optional[str]:
        return self._adapter_methods.get(adapter_id)


_MANAGER: Optional[ToolpackManager] = None
_MANAGER_LOCK = Lock()


def get_toolpack_manager() -> ToolpackManager:
    global _MANAGER
    with _MANAGER_LOCK:
        if _MANAGER is None:
            _MANAGER = ToolpackManager()
        return _MANAGER


def validate_toolpacks_or_raise(registered_adapter_ids: Iterable[str]) -> Dict[str, str]:
    manager = get_toolpack_manager()
    manager.load()
    return manager.resolve_mappings(registered_adapter_ids)
