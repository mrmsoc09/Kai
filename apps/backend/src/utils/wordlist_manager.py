"""Legacy shim — delegates to apps.backend.src.core.wordlist_manager."""
from __future__ import annotations

from ..core.wordlist_manager import (  # noqa: F401
    WordlistManager,
    WordlistEntry,
    get_wordlist_manager,
    reset_wordlist_manager,
    CATALOG,
    SECLISTS,
)

__all__ = [
    "WordlistManager",
    "WordlistEntry",
    "get_wordlist_manager",
    "reset_wordlist_manager",
    "CATALOG",
    "SECLISTS",
]
