"""Compatibility proxy for legacy ``from src.main import app`` imports."""

from apps.backend.src.main import app

__all__ = ["app"]

