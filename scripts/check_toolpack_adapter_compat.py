#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLPACKS_PATH = ROOT / "ops" / "toolpacks.yaml"
ADAPTER_GLOB = "apps/backend/src/core/tool_adapters_*.py"
ADAPTER_ID_RE = re.compile(r'id="([a-zA-Z0-9_\-]+)"')


def _load_enabled_adapter_ids() -> set[str]:
    ids: set[str] = set()
    for file_path in ROOT.glob(ADAPTER_GLOB):
        text = file_path.read_text(encoding="utf-8")
        for match in ADAPTER_ID_RE.finditer(text):
            ids.add(match.group(1))
    return ids


def _load_enabled_toolpack_mappings() -> list[tuple[str, str]]:
    payload = yaml.safe_load(TOOLPACKS_PATH.read_text(encoding="utf-8")) or {}
    toolpacks = payload.get("toolpacks") or {}
    pairs: list[tuple[str, str]] = []
    for toolpack_name, cfg in toolpacks.items():
        if not cfg.get("enabled", True):
            continue
        for tool in cfg.get("tools") or []:
            if not tool.get("enabled", True):
                continue
            tool_id = str(tool.get("id") or "").strip()
            adapter_id = str(tool.get("adapter_id") or "").strip()
            if tool_id and adapter_id:
                pairs.append((f"{toolpack_name}.{tool_id}", adapter_id))
    return pairs


def main() -> int:
    if not TOOLPACKS_PATH.exists():
        print(f"toolpack compatibility check failed: missing {TOOLPACKS_PATH}")
        return 1

    known_adapters = _load_enabled_adapter_ids()
    mappings = _load_enabled_toolpack_mappings()
    unresolved = [f"{mapping}->{adapter}" for mapping, adapter in mappings if adapter not in known_adapters]
    if unresolved:
        print("toolpack compatibility check failed:")
        for row in sorted(unresolved):
            print(row)
        return 1

    print(f"toolpack compatibility check passed ({len(mappings)} enabled mappings resolved)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
