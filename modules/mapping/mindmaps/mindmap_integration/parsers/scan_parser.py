"""
Parser for security scan results (SARIF, JSON).
Maps vulnerabilities to architectural components.
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any, List

from ..core.models import MindMap, Node, NodeType, Edge, EdgeType


class ScanParser:
    """
    Parses security scan outputs to create attack surface visualizations.
    """
    
    def parse(self, scan_path: str, codebase_path: Optional[str] = None) -> MindMap:
        """
        Parse scan results file.
        
        Args:
            scan_path: Path to SARIF or JSON scan results
            codebase_path: Optional path to codebase for context
        """
        path = Path(scan_path)
        
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Detect format
        if self._is_sarif(data):
            return self._parse_sarif(data, codebase_path)
        else:
            return self._parse_generic_json(data, codebase_path)
    
    def _is_sarif(self, data: Dict) -> bool:
        """Check if data follows SARIF format."""
        return "$schema" in data and "sarif" in data.get("$schema", "").lower()
    
    def _parse_sarif(self, data: Dict, codebase_path: Optional[str]) -> MindMap:
        """Parse SARIF format (Static Analysis Results Interchange Format)."""
        mindmap = MindMap(
            title="Attack Surface Analysis",
            metadata={"format": "SARIF", "version": data.get("version", "unknown")}
        )
        
        # Create root
        root = Node(
            id="root",
            label="Attack Surface",
            type=NodeType.ROOT
        )
        mindmap.add_node(root)
        
        # Group findings by rule/title
        findings_by_rule: Dict[str, List[Dict]] = {}
        
        for run in data.get("runs", []):
            for result in run.get("results", []):
                rule_id = result.get("ruleId", "Unknown")
                if rule_id not in findings_by_rule:
                    findings_by_rule[rule_id] = []
                findings_by_rule[rule_id].append(result)
        
        # Create nodes for each vulnerability type
        for rule_id, findings in findings_by_rule.items():
            severity = self._extract_severity(findings[0])
            
            vuln_node = Node(
                id=f"vuln_{rule_id}",
                label=f"{rule_id} ({len(findings)} instances)",
                type=NodeType.SECURITY_RISK,
                metadata={
                    "severity": severity,
                    "count": len(findings),
                    "rule_id": rule_id
                }
            )
            mindmap.add_node(vuln_node)
            mindmap.add_edge(Edge(
                source=root.id,
                target=vuln_node.id,
                type=EdgeType.VULNERABLE,
                label=severity
            ))
            
            # Add specific instances as children
            for i, finding in enumerate(findings[:5]):  # Limit to first 5 for readability
                location = finding.get("locations", [{}])[0]
                physical_loc = location.get("physicalLocation", {})
                artifact = physical_loc.get("artifactLocation", {})
                region = physical_loc.get("region", {})
                
                file_path = artifact.get("uri", "unknown")
                line = region.get("startLine", 0)
                
                instance_node = Node(
                    id=f"inst_{rule_id}_{i}",
                    label=f"{file_path}:{line}",
                    type=NodeType.LEAF,
                    parent_id=vuln_node.id,
                    metadata={
                        "file": file_path,
                        "line": line,
                        "message": finding.get("message", {}).get("text", "")
                    }
                )
                mindmap.add_node(instance_node)
                mindmap.add_edge(Edge(
                    source=vuln_node.id,
                    target=instance_node.id,
                    type=EdgeType.RELATES
                ))
        
        return mindmap
    
    def _parse_generic_json(self, data: Dict, codebase_path: Optional[str]) -> MindMap:
        """Parse generic JSON scan format."""
        mindmap = MindMap(
            title="Security Scan Results",
            metadata={"format": "Generic JSON"}
        )
        
        root = Node(
            id="root",
            label="Vulnerabilities",
            type=NodeType.ROOT
        )
        mindmap.add_node(root)
        
        # Handle common formats (OWASP Dependency Check, etc.)
        if "dependencies" in data:  # OWASP Dependency Check style
            for dep in data.get("dependencies", []):
                for vuln in dep.get("vulnerabilities", []):
                    name = vuln.get("name", "Unknown")
                    
                    vuln_node = Node(
                        id=f"vuln_{name}",
                        label=name,
                        type=NodeType.SECURITY_RISK,
                        metadata={
                            "severity": vuln.get("severity", "Unknown"),
                            "cvss": vuln.get("cvssScore", 0)
                        }
                    )
                    mindmap.add_node(vuln_node)
                    mindmap.add_edge(Edge(
                        source=root.id,
                        target=vuln_node.id,
                        type=EdgeType.VULNERABLE
                    ))
        else:
            # Generic handling - look for arrays of findings
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    category_node = Node(
                        id=f"cat_{key}",
                        label=key,
                        type=NodeType.BRANCH
                    )
                    mindmap.add_node(category_node)
                    mindmap.add_edge(Edge(
                        source=root.id,
                        target=category_node.id
                    ))
                    
                    for i, item in enumerate(value[:10]):  # Limit items
                        if isinstance(item, dict):
                            label = item.get("title") or item.get("name") or item.get("id") or f"Item {i}"
                            item_node = Node(
                                id=f"item_{key}_{i}",
                                label=str(label),
                                type=NodeType.LEAF,
                                metadata=item
                            )
                            mindmap.add_node(item_node)
                            mindmap.add_edge(Edge(
                                source=category_node.id,
                                target=item_node.id
                            ))
        
        return mindmap
    
    def _extract_severity(self, finding: Dict) -> str:
        """Extract severity from SARIF finding."""
        level = finding.get("level", "warning")
        # Map SARIF levels to severity
        mapping = {
            "error": "High",
            "warning": "Medium",
            "note": "Low"
        }
        return mapping.get(level, "Unknown")
