from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class WordlistManager:
    """
    K1 Dynamic Wordlist Manager.
    Maps service metadata (Tech Stack) to optimized SecLists wordlists.
    """

    def __init__(self, base_path: str = "/usr/share/wordlists"):
        self.base_path = Path(base_path)
        self.registry: Dict[str, List[str]] = {
            "php": ["discovery/web-content/php.txt", "discovery/web-content/cms/wordpress.txt"],
            "laravel": ["discovery/web-content/laravel.txt", "discovery/web-content/cms/laravel.txt"],
            "nginx": ["discovery/web-content/nginx.txt"],
            "apache": ["discovery/web-content/apache.txt"],
            "default": ["discovery/web-content/common.txt", "discovery/web-content/raft-small-words.txt"]
        }

    def get_wordlists(self, tech_stack: List[str]) -> List[Path]:
        """Prioritizes and returns wordlists based on target technology."""
        selected: List[Path] = []
        seen: Set[str] = set()

        # Prioritize tech-specific lists
        for tech in tech_stack:
            tech = tech.lower()
            if tech in self.registry:
                for path_str in self.registry[tech]:
                    if path_str not in seen:
                        full_path = self.base_path / path_str
                        if full_path.exists():
                            selected.append(full_path)
                            seen.add(path_str)

        # Default fallback
        for path_str in self.registry["default"]:
            if path_str not in seen:
                full_path = self.base_path / path_str
                if full_path.exists():
                    selected.append(full_path)
                    seen.add(path_str)
                    
        return selected
