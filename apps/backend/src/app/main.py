"""Compatibility module.

Canonical backend entrypoint: ``apps.backend.src.main:app``.
This proxy preserves legacy imports like ``apps.backend.src.app.main:app``.
"""

from apps.backend.src.main import app

__all__ = ["app"]
