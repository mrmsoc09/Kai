from __future__ import annotations

import os
from pathlib import Path


class KiterunnerWordlistManager:
    """Selects the best .kite wordlist for scan intent and detected technologies."""

    WORDLIST_DIRS = (
        "/usr/share/kiterunner/wordlists",
        "/opt/kiterunner/wordlists",
        "/usr/local/share/kiterunner/wordlists",
    )
    DEFAULT_SCAN_WORDLIST = "routes-large.kite"
    DEFAULT_BRUTE_WORDLIST = "routes-large.kite"
    SWAGGER_WORDLIST = "swagger-list.kite"
    GRAPHQL_WORDLIST = "graphql.kite"

    def select_wordlist(
        self,
        *,
        tech_stack: list[str] | None = None,
        mode: str = "scan",
        requested_wordlist: str | None = None,
    ) -> str:
        if requested_wordlist:
            candidate = Path(str(requested_wordlist)).expanduser()
            return str(candidate)

        selected_name = self._select_default_name(tech_stack=tech_stack or [], mode=mode)
        for directory in self._iter_wordlist_dirs():
            candidate = directory / selected_name
            if candidate.exists():
                return str(candidate)
        return str(Path(self.WORDLIST_DIRS[0]) / selected_name)

    def _select_default_name(self, *, tech_stack: list[str], mode: str) -> str:
        tokens = {token.strip().lower() for token in tech_stack if token and token.strip()}
        if any(token in {"swagger", "openapi", "swagger-ui"} for token in tokens):
            return self.SWAGGER_WORDLIST
        if any(token in {"graphql", "apollo"} for token in tokens):
            return self.GRAPHQL_WORDLIST
        if mode == "brute":
            return self.DEFAULT_BRUTE_WORDLIST
        return self.DEFAULT_SCAN_WORDLIST

    @classmethod
    def _iter_wordlist_dirs(cls) -> list[Path]:
        custom = os.getenv("K1_KITERUNNER_WORDLIST_DIR", "").strip()
        dirs = []
        if custom:
            dirs.append(Path(custom).expanduser())
        dirs.extend(Path(item) for item in cls.WORDLIST_DIRS)
        return dirs
