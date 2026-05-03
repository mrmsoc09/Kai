"""
Generator for PlantUML format mindmaps.
"""

from typing import List
from ..core.models import MindMap, Node, NodeType


class PlantUMLGenerator:
    """
    Generates PlantUML mindmap syntax.
    """
    
    def generate(self, mindmap: MindMap) -> str:
        """Generate PlantUML mindmap syntax."""
        lines = ["@startmindmap"]
        lines.append(f"title {mindmap.title}")
        lines.append("")
        
        root = mindmap.get_root()
        if root:
            self._add_node_plantuml(lines, mindmap, root.id, 1)
        
        lines.append("")
        lines.append("@endmindmap")
        
        return "\n".join(lines)
    
    def _add_node_plantuml(self, lines: List[str], mindmap: MindMap, 
                          node_id: str, level: int):
        """Recursively add nodes in PlantUML format."""
        node = mindmap.nodes.get(node_id)
        if not node:
            return
        
        indent = "  " * (level - 1)
        prefix = "*" * level
        
        # Add styling based on type
        style = ""
        if node.type == NodeType.SECURITY_RISK:
            style = "[#Red]"
        elif node.type == NodeType.COMPONENT:
            style = "[#LightBlue]"
        elif node.type == NodeType.IDEA:
            style = "[#LightGreen]"
        
        label = node.label.replace("[", "(").replace("]", ")")
        lines.append(f"{indent}{prefix}{style} {label}")
        
        # Add children
        for child_id in node.children_ids:
            self._add_node_plantuml(lines, mindmap, child_id, level + 1)
