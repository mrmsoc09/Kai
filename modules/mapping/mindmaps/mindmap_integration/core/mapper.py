"""
Core orchestration module for mindmap generation.
Coordinates parsing, AI enhancement, and output generation.
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path

from .models import MindMap, Node, NodeType
from ..parsers.codebase_parser import CodebaseParser
from ..parsers.scan_parser import ScanParser
from ..generators.mermaid_generator import MermaidGenerator
from ..generators.plantuml_generator import PlantUMLGenerator
from ..ai.brainstorm_engine import BrainstormEngine


class MindmapMapper:
    """
    Main orchestrator for mindmap generation from various sources.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.code_parser = CodebaseParser()
        self.scan_parser = ScanParser()
        self.brainstorm = BrainstormEngine()
        self.mermaid_gen = MermaidGenerator()
        self.plantuml_gen = PlantUMLGenerator()
    
    def map_codebase(self, 
                     source_path: str, 
                     output_path: Optional[str] = None,
                     format_type: str = "mermaid",
                     ai_enhance: bool = True) -> MindMap:
        """
        Generate architectural mindmap from codebase.
        
        Args:
            source_path: Path to code directory or file
            output_path: Optional output file path
            format_type: 'mermaid' or 'plantuml'
            ai_enhance: Whether to apply AI brainstorming enhancement
        """
        # Parse codebase structure
        mindmap = self.code_parser.parse(source_path)
        mindmap.format_type = format_type
        
        # AI enhancement for architectural insights
        if ai_enhance:
            mindmap = self.brainstorm.enhance_architecture(mindmap)
        
        # Generate output
        if output_path:
            self._write_output(mindmap, output_path, format_type)
        
        return mindmap
    
    def map_scan_results(self, 
                        scan_path: str,
                        codebase_path: Optional[str] = None,
                        output_path: Optional[str] = None,
                        format_type: str = "mermaid") -> MindMap:
        """
        Generate attack surface mindmap from security scan results.
        
        Args:
            scan_path: Path to SARIF or JSON scan results
            codebase_path: Optional path to map vulnerabilities to code
            output_path: Optional output file path
            format_type: 'mermaid' or 'plantuml'
        """
        # Parse scan results
        mindmap = self.scan_parser.parse(scan_path, codebase_path)
        mindmap.format_type = format_type
        
        # AI enhancement for attack surface analysis
        mindmap = self.brainstorm.enhance_security(mindmap)
        
        if output_path:
            self._write_output(mindmap, output_path, format_type)
        
        return mindmap
    
    def brainstorm_topic(self, 
                        topic: str, 
                        context: Optional[str] = None,
                        depth: int = 3,
                        output_path: Optional[str] = None) -> MindMap:
        """
        AI-driven brainstorming session generating a mindmap.
        
        Args:
            topic: Central topic for brainstorming
            context: Additional context or constraints
            depth: How many levels to expand
            output_path: Optional output file path
        """
        mindmap = MindMap(title=f"Brainstorm: {topic}", format_type="mermaid")
        
        # Create root
        root = Node(
            id="root",
            label=topic,
            type=NodeType.ROOT,
            depth=0
        )
        mindmap.add_node(root)
        
        # AI-driven expansion
        mindmap = self.brainstorm.expand_ideas(mindmap, root.id, context, depth)
        
        if output_path:
            self._write_output(mindmap, output_path, "mermaid")
        
        return mindmap
    
    def convert_format(self, input_path: str, output_path: str, target_format: str) -> None:
        """
        Convert between mindmap formats.
        """
        # Read input (assuming it's a serialized mindmap or parseable structure)
        import json
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        mindmap = MindMap(
            title=data.get("title", "Converted"),
            format_type=target_format
        )
        
        # Reconstruct nodes and edges
        for node_data in data.get("nodes", {}).values():
            node = Node(
                id=node_data["id"],
                label=node_data["label"],
                type=NodeType(node_data["type"]),
                metadata=node_data.get("metadata", {}),
                parent_id=node_data.get("parent_id"),
                depth=node_data.get("depth", 0)
            )
            mindmap.add_node(node)
        
        self._write_output(mindmap, output_path, target_format)
    
    def _write_output(self, mindmap: MindMap, output_path: str, format_type: str) -> None:
        """Write mindmap to file in specified format."""
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        
        if format_type == "mermaid":
            content = self.mermaid_gen.generate(mindmap)
        elif format_type == "plantuml":
            content = self.plantuml_gen.generate(mindmap)
        elif format_type == "markdown":
            content = self._generate_markdown(mindmap)
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _generate_markdown(self, mindmap: MindMap) -> str:
        """Generate Markdown with embedded Mermaid diagram."""
        mermaid_content = self.mermaid_gen.generate(mindmap)
        
        lines = [
            f"# {mindmap.title}",
            "",
            "## Overview",
            mindmap.metadata.get('description', 'Auto-generated mindmap'),
            "",
            "## Diagram",
            "",
            "```mermaid",
            mermaid_content,
            "```",
            "",
            "## Metadata",
            f"- Generated: {mindmap.metadata.get('timestamp', 'Unknown')}",
            f"- Nodes: {len(mindmap.nodes)}",
            f"- Edges: {len(mindmap.edges)}"
        ]
        
        return "\n".join(lines)
