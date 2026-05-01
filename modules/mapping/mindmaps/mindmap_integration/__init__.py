"""
Mindmap Integration System
Autonomous generation and management of architectural mindmaps.
Supports Mermaid.js, PlantUML, and Markdown formats.
"""

__version__ = "1.0.0"
__author__ = "Mindmap Integration Team"

from .core.mapper import MindmapMapper
from .core.models import MindMap, Node, Edge

__all__ = ["MindmapMapper", "MindMap", "Node", "Edge"]
