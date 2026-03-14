from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import yaml

from .helpers import as_list_of_str, repo_root


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1
    backoff_seconds: float = 0.0


@dataclass(frozen=True)
class ToolCatalogEntry:
    name: str
    category: str
    execution_mode: str
    binary_path: str | None
    container_image: str | None
    install_verification_cmd: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    timeout_seconds: int
    retry_policy: RetryPolicy
    safety_classification: str
    tags: list[str]
    dependencies: list[str]
    api_keys_required: list[str]
    enabled_by_default: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "execution_mode": self.execution_mode,
            "binary_path": self.binary_path,
            "container_image": self.container_image,
            "install_verification_cmd": self.install_verification_cmd,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "timeout_seconds": self.timeout_seconds,
            "retry_policy": {
                "max_attempts": self.retry_policy.max_attempts,
                "backoff_seconds": self.retry_policy.backoff_seconds,
            },
            "safety_classification": self.safety_classification,
            "tags": self.tags,
            "dependencies": self.dependencies,
            "api_keys_required": self.api_keys_required,
            "enabled_by_default": self.enabled_by_default,
        }


def default_catalog_path() -> Path:
    env_value = os.getenv("K1_TOOL_REGISTRY_PATH", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return repo_root() / "tools" / "registry" / "tool_registry.yaml"


def _load_from_payload(payload: dict[str, Any]) -> dict[str, ToolCatalogEntry]:
    entries: dict[str, ToolCatalogEntry] = {}
    raw_tools = payload.get("tools") or []
    for item in raw_tools:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip().lower()
        if not name:
            continue
        if name in entries:
            raise ValueError(f"Duplicate tool entry in catalog: {name}")

        retry = item.get("retry_policy") if isinstance(item.get("retry_policy"), dict) else {}
        entry = ToolCatalogEntry(
            name=name,
            category=str(item.get("category") or "uncategorized").strip().lower(),
            execution_mode=str(item.get("execution_mode") or "native").strip().lower(),
            binary_path=(str(item.get("binary_path")).strip() if item.get("binary_path") else None),
            container_image=(
                str(item.get("container_image")).strip() if item.get("container_image") else None
            ),
            install_verification_cmd=as_list_of_str(item.get("install_verification_cmd")),
            input_schema=item.get("input_schema")
            if isinstance(item.get("input_schema"), dict)
            else {},
            output_schema=item.get("output_schema")
            if isinstance(item.get("output_schema"), dict)
            else {},
            timeout_seconds=max(10, int(item.get("timeout_seconds") or 180)),
            retry_policy=RetryPolicy(
                max_attempts=max(1, int(retry.get("max_attempts") or 1)),
                backoff_seconds=max(0.0, float(retry.get("backoff_seconds") or 0.0)),
            ),
            safety_classification=str(item.get("safety_classification") or "safe").strip().lower(),
            tags=as_list_of_str(item.get("tags")),
            dependencies=as_list_of_str(item.get("dependencies")),
            api_keys_required=as_list_of_str(item.get("api_keys_required")),
            enabled_by_default=bool(item.get("enabled_by_default", True)),
        )
        entries[name] = entry
    return entries


class ToolCatalog:
    def __init__(self, path: Path | None = None):
        self.path = path or default_catalog_path()
        self._entries: dict[str, ToolCatalogEntry] = {}
        self._loaded = False
        self._lock = Lock()

    def load(self) -> None:
        if not self.path.exists():
            raise FileNotFoundError(f"Tool catalog not found: {self.path}")
        payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError("Tool catalog payload must be a mapping")
        entries = _load_from_payload(payload)
        with self._lock:
            self._entries = entries
            self._loaded = True

    def _ensure_loaded(self) -> None:
        with self._lock:
            loaded = self._loaded
        if not loaded:
            self.load()

    def entries(self) -> dict[str, ToolCatalogEntry]:
        self._ensure_loaded()
        with self._lock:
            return dict(self._entries)

    def get(self, name: str) -> ToolCatalogEntry | None:
        self._ensure_loaded()
        with self._lock:
            return self._entries.get(name.strip().lower())

    def list_enabled(self) -> list[ToolCatalogEntry]:
        return [entry for entry in self.entries().values() if entry.enabled_by_default]


_CATALOG: ToolCatalog | None = None
_CATALOG_LOCK = Lock()


def get_tool_catalog() -> ToolCatalog:
    global _CATALOG
    with _CATALOG_LOCK:
        if _CATALOG is None:
            _CATALOG = ToolCatalog()
        return _CATALOG


def reset_tool_catalog() -> None:
    """Reset the global catalog singleton. Intended for test isolation only."""
    global _CATALOG
    with _CATALOG_LOCK:
        _CATALOG = None


def list_catalog_entries(*, enabled_only: bool = False) -> list[ToolCatalogEntry]:
    catalog = get_tool_catalog()
    entries = catalog.list_enabled() if enabled_only else list(catalog.entries().values())
    return sorted(entries, key=lambda entry: entry.name)


def get_catalog_entry(name: str) -> ToolCatalogEntry | None:
    return get_tool_catalog().get(name)
