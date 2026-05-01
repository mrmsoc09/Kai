"""
Generator for Mermaid.js format mindmaps and diagrams.
Supports mindmap syntax, flowcharts, and graphs.
"""

from typing import List, Dict
from ..core.models import MindMap, Node, NodeType, EdgeType


class MermaidGenerator:
    """
    Generates Mermaid.js compatible syntax.
    """
    
    def generate(self, mindmap: MindMap) -> str:
        """
        Generate Mermaid diagram based on mindmap structure.
        Chooses appropriate diagram type based on content.
        """
        # Use mindmap syntax for hierarchical data, flowchart for complex graphs
        if self._is_hierarchical(mindmap):
            return self._generate_mindmap(mindmap)
        else:
            return self._generate_flowchart(mindmap)
    
    def _is_hierarchical(self, mindmap: MindMap) -> bool:
        """Check if structure is primarily hierarchical."""
        if not mindmap.edges:
            return True
        
        # If most edges are tree-like (no cycles), use mindmap
        return len(mindmap.edges) < len(mindmap.nodes) * 1.5
    
    def _generate_mindmap(self, mindmap: MindMap) -> str:
        """Generate Mermaid mindmap syntax."""
        lines = ["mindmap"]
        lines.append(f"  root({mindmap.title})")
        
        # Build tree structure
        root = mindmap.get_root()
        if not root:
            return "\n".join(lines)
        
        self._add_children_mindmap(lines, mindmap, root.id, 2)
        
        return "\n".join(lines)
    
    def _add_children_mindmap(self, lines: List[str], mindmap: MindMap, 
                              parent_id: str, indent: int):
        """Recursively add children in mindmap format."""
        children = mindmap.get_children(parent_id)
        
        for child in children:
            prefix = "  " * indent
            icon = self._get_icon(child.type)
            
            # Escape parentheses in labels
            label = child.label.replace("(", "[").replace(")", "]")
            
            if child.children_ids:
                lines.append(f"{prefix}{icon} {label}")
                self._add_children_mindmap(lines, mindmap, child.id, indent + 1)
            else:
                lines.append(f"{prefix}{icon} {label}")
    
    def _generate_flowchart(self, mindmap: MindMap) -> str:
        """Generate Mermaid flowchart for complex relationships."""
        lines = ["flowchart TD"]
        
        # Add node definitions with styling
        for node_id, node in mindmap.nodes.items():
            safe_id = self._safe_id(node_id)
            label = node.label.replace('"', "'")
            
            # Style based on type
            if node.type == NodeType.ROOT:
                lines.append(f'    {safe_id}["{label}"]:::root')
            elif node.type == NodeType.SECURITY_RISK:
                lines.append(f'    {safe_id}["{label}"]:::risk')
            elif node.type == NodeType.COMPONENT:
                lines.append(f'    {safe_id}["{label}"]:::component')
            else:
                lines.append(f'    {safe_id}["{label}"]')
        
        # Add edges
        for edge in mindmap.edges:
            src = self._safe_id(edge.source)
            tgt = self._safe_id(edge.target)
            
            if edge.label:
                lines.append(f'    {src} -->|"{edge.label}"| {tgt}')
            else:
                lines.append(f'    {src} --> {tgt}')
        
        # Add styling classes
        lines.append("    classDef root fill:#f9f,stroke:#333,stroke-width:4px")
        lines.append("    classDef risk fill:#f96,stroke:#333,stroke-width:2px")
        lines.append("    classDef component fill:#69f,stroke:#333,stroke-width:2px")
        
        return "\n".join(lines)
    
    def _get_icon(self, node_type: NodeType) -> str:
        """Get appropriate icon for node type."""
        icons = {
            NodeType.ROOT: "",
            NodeType.BRANCH: "",
            NodeType.LEAF: "",
            NodeType.SECURITY_RISK: "🚨",
            NodeType.COMPONENT: "📦",
            NodeType.DATA_FLOW: "🔄",
            NodeType.IDEA: "💡",
            NodeType.QUESTION: "❓"
        }
        return icons.get(node_type, "")
    
    def _safe_id(self, node_id: str) -> str:
        """Create Mermaid-safe node ID."""
        # Replace invalid characters
        safe = node_id.replace("-", "_").replace(".", "_").replace(" ", "_")
        if safe[0].isdigit():
            safe = "n" + safe
        return safe
