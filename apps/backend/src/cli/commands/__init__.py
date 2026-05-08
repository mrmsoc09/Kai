"""
CLI Commands for Kaison K1.

Each module provides a Click command group.
"""

from importlib import import_module

__all__ = [
    "hunt",
    "scan",
    "agent",
    "workflow",
    "findings",
    "orchestrator",
    "tools",
    "bug_bounty",
    "training",
]


def __getattr__(name: str):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{name}")
    return getattr(module, name)
