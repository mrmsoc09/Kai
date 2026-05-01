"""
Parser for extracting architectural information from codebases.
Supports Python AST analysis and generic file structure mapping.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Any

from ..core.models import MindMap, Node, NodeType, Edge, EdgeType


class CodebaseParser:
    """
    Parses codebase to extract structural and dependency information.
    """
    
    def __init__(self):
        self.file_patterns = {
            'python': r'\.py$',
            'javascript': r'\.(js|ts|jsx|tsx)$',
            'java': r'\.java$',
            'go': r'\.go$',
            'rust': r'\.rs$'
        }
    
    def parse(self, source_path: str) -> MindMap:
        """
        Parse codebase at given path and return MindMap.
        """
        path = Path(source_path)
        
        if path.is_file():
            return self._parse_file(path)
        elif path.is_dir():
            return self._parse_directory(path)
        else:
            raise ValueError(f"Invalid path: {source_path}")
    
    def _parse_directory(self, dir_path: Path) -> MindMap:
        """Parse entire directory structure."""
        mindmap = MindMap(
            title=f"Architecture: {dir_path.name}",
            metadata={"source": str(dir_path), "type": "codebase"}
        )
        
        # Create root node
        root = Node(
            id="root",
            label=dir_path.name,
            type=NodeType.ROOT
        )
        mindmap.add_node(root)
        
        # Track modules and their relationships
        modules: Dict[str, Node] = {}
        imports: List[tuple] = []  # (source, target)
        
        for file_path in self._get_source_files(dir_path):
            rel_path = file_path.relative_to(dir_path)
            module_name = str(rel_path.with_suffix('')).replace(os.sep, '.')
            
            # Create module node
            module_node = Node(
                id=f"mod_{module_name}",
                label=file_path.name,
                type=NodeType.COMPONENT,
                metadata={
                    "path": str(rel_path),
                    "language": self._detect_language(file_path)
                }
            )
            mindmap.add_node(module_node)
            modules[module_name] = module_node
            
            # Link to root or parent directory
            parent_path = rel_path.parent
            if str(parent_path) == '.':
                mindmap.add_edge(Edge(
                    source=root.id,
                    target=module_node.id,
                    type=EdgeType.DEPENDS
                ))
            else:
                parent_name = str(parent_path).replace(os.sep, '.')
                if parent_name in modules:
                    mindmap.add_edge(Edge(
                        source=modules[parent_name].id,
                        target=module_node.id,
                        type=EdgeType.DEPENDS
                    ))
            
            # Parse file internals if Python
            if file_path.suffix == '.py':
                file_nodes, file_imports = self._parse_python_file(file_path, module_node.id)
                for node in file_nodes:
                    mindmap.add_node(node)
                    mindmap.add_edge(Edge(
                        source=module_node.id,
                        target=node.id,
                        type=EdgeType.CONTAINS if hasattr(EdgeType, 'CONTAINS') else EdgeType.DEPENDS
                    ))
                imports.extend(file_imports)
        
        # Add import relationships
        for src, tgt in imports:
            if src in modules and tgt in modules:
                mindmap.add_edge(Edge(
                    source=modules[src].id,
                    target=modules[tgt].id,
                    type=EdgeType.IMPORTS,
                    label="imports"
                ))
        
        return mindmap
    
    def _parse_file(self, file_path: Path) -> MindMap:
        """Parse single file."""
        mindmap = MindMap(
            title=f"File: {file_path.name}",
            metadata={"source": str(file_path)}
        )
        
        root = Node(
            id="root",
            label=file_path.name,
            type=NodeType.ROOT
        )
        mindmap.add_node(root)
        
        if file_path.suffix == '.py':
            nodes, _ = self._parse_python_file(file_path, root.id)
            for node in nodes:
                mindmap.add_node(node)
                mindmap.add_edge(Edge(
                    source=root.id,
                    target=node.id,
                    type=EdgeType.CONTAINS if hasattr(EdgeType, 'CONTAINS') else EdgeType.DEPENDS
                ))
        
        return mindmap
    
    def _parse_python_file(self, file_path: Path, parent_id: str) -> tuple:
        """
        Parse Python file using AST.
        Returns: (list of Nodes, list of import tuples)
        """
        nodes = []
        imports = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read())
            
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef):
                    class_node = Node(
                        id=f"cls_{node.name}_{id(node)}",
                        label=node.name,
                        type=NodeType.COMPONENT,
                        parent_id=parent_id,
                        metadata={
                            "line": node.lineno,
                            "type": "class",
                            "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                        }
                    )
                    nodes.append(class_node)
                    
                    # Add methods as children
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            method_node = Node(
                                id=f"func_{item.name}_{id(item)}",
                                label=item.name,
                                type=NodeType.LEAF,
                                parent_id=class_node.id,
                                metadata={
                                    "line": item.lineno,
                                    "type": "method"
                                }
                            )
                            nodes.append(method_node)
                            
                elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    # Module-level function
                    func_node = Node(
                        id=f"func_{node.name}_{id(node)}",
                        label=node.name,
                        type=NodeType.LEAF,
                        parent_id=parent_id,
                        metadata={
                            "line": node.lineno,
                            "type": "function"
                        }
                    )
                    nodes.append(func_node)
                    
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    # Track imports for dependency mapping
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.append((parent_id, alias.name))
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imports.append((parent_id, node.module))
                        
        except SyntaxError as e:
            # Handle malformed files gracefully
            error_node = Node(
                id=f"error_{id(e)}",
                label=f"Parse Error: {e.msg}",
                type=NodeType.LEAF,
                parent_id=parent_id,
                metadata={"error": str(e)}
            )
            nodes.append(error_node)
        
        return nodes, imports
    
    def _get_source_files(self, dir_path: Path) -> List[Path]:
        """Get all source files recursively."""
        files = []
        for pattern in self.file_patterns.values():
            files.extend(dir_path.rglob('*'))
        
        # Filter by patterns and exclude common non-source directories
        exclude_dirs = {'.git', '__pycache__', 'node_modules', 'venv', '.env', 'dist', 'build'}
        source_files = []
        
        for f in files:
            if f.is_file():
                if any(excluded in f.parts for excluded in exclude_dirs):
                    continue
                if any(re.search(pattern, f.name) for pattern in self.file_patterns.values()):
                    source_files.append(f)
        
        return source_files
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        ext = file_path.suffix
        mapping = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c'
        }
        return mapping.get(ext, 'unknown')
