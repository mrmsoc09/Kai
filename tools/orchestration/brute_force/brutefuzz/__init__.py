"""
BruteFuzz - High-Performance Brute Forcing and Fuzzing Suite
Advanced security testing framework with AI-driven feedback loops
"""

__version__ = "1.0.0"
__author__ = "Security Research Team"

from .core.engine import FuzzingEngine
from .core.config import Config

__all__ = ["FuzzingEngine", "Config"]
