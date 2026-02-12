"""
MCP Server: K1 Graph
Exposes attack graph and chain building tools
"""

from src.core.mcp_base import BaseMCPServer, ToolType
import uuid


class GraphMCPServer(BaseMCPServer):
    """MCP server for graph and chain building tools"""

    def __init__(self):
        super().__init__(
            server_id="mcp-graph",
            name="K1 Graph Server",
            port=9004
        )

    def _initialize_tools(self):
        """Register graph tools"""

        # Tool 1: Attack Graph Builder
        self.register_tool(
            name="attack_graph_builder",
            description="Build and visualize attack graphs",
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "findings": {
                        "type": "array",
                        "items": {"type": "object"}
                    },
                    "include_chains": {"type": "boolean", "default": True}
                },
                "required": ["target", "findings"]
            },
            handler=self.build_attack_graph,
            tool_type=ToolType.PLANNER
        )

        # Tool 2: Chain Builder
        self.register_tool(
            name="chain_builder",
            description="Build multi-step attack chains from findings",
            input_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "type": {"type": "string"},
                                "severity": {"type": "string"}
                            }
                        }
                    },
                    "max_steps": {"type": "integer", "default": 5}
                },
                "required": ["findings"]
            },
            handler=self.build_chains,
            tool_type=ToolType.PLANNER
        )

        # Tool 3: Scope Mapper
        self.register_tool(
            name="scope_mapper",
            description="Map and visualize attack surface scope",
            input_schema={
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "include_subdomains": {"type": "boolean", "default": True},
                    "include_ip_ranges": {"type": "boolean", "default": True}
                },
                "required": ["target"]
            },
            handler=self.map_scope,
            tool_type=ToolType.PLANNER
        )

    async def build_attack_graph(
        self,
        target: str,
        findings: list,
        include_chains: bool = True
    ) -> dict:
        """Build attack graph"""

        graph = {
            "target": target,
            "graph_id": str(uuid.uuid4()),
            "nodes": [
                {
                    "id": "entry",
                    "label": "Entry Point",
                    "type": "entry",
                    "description": "Initial access vector"
                },
                {
                    "id": "sql_injection",
                    "label": "SQL Injection",
                    "type": "vulnerability",
                    "severity": "critical",
                    "finding_id": findings[0]["id"] if findings else "unknown"
                },
                {
                    "id": "auth_bypass",
                    "label": "Authentication Bypass",
                    "type": "vulnerability",
                    "severity": "critical"
                },
                {
                    "id": "privesc",
                    "label": "Privilege Escalation",
                    "type": "vulnerability",
                    "severity": "high"
                },
                {
                    "id": "rce",
                    "label": "Remote Code Execution",
                    "type": "vulnerability",
                    "severity": "critical"
                },
                {
                    "id": "complete_compromise",
                    "label": "System Compromise",
                    "type": "goal",
                    "description": "Full system access achieved"
                }
            ],
            "edges": [
                {
                    "source": "entry",
                    "target": "sql_injection",
                    "label": "Exploits"
                },
                {
                    "source": "sql_injection",
                    "target": "auth_bypass",
                    "label": "Leads to"
                },
                {
                    "source": "auth_bypass",
                    "target": "privesc",
                    "label": "Enables"
                },
                {
                    "source": "privesc",
                    "target": "rce",
                    "label": "Allows"
                },
                {
                    "source": "rce",
                    "target": "complete_compromise",
                    "label": "Results in"
                }
            ],
            "paths": [
                {
                    "id": "path_1",
                    "name": "Complete Compromise Path",
                    "nodes": ["entry", "sql_injection", "auth_bypass", "privesc", "rce", "complete_compromise"],
                    "severity": "Critical",
                    "exploitability": 0.92,
                    "impact": "Complete system compromise"
                }
            ],
            "statistics": {
                "total_nodes": 6,
                "critical_vulnerabilities": 3,
                "high_vulnerabilities": 1,
                "attack_paths": 1,
                "max_path_length": 6
            }
        }

        return graph

    async def build_chains(self, findings: list, max_steps: int = 5) -> dict:
        """Build attack chains"""

        chains = {
            "chains_id": str(uuid.uuid4()),
            "findings_analyzed": len(findings),
            "chains_discovered": 3,
            "chains": [
                {
                    "chain_id": str(uuid.uuid4()),
                    "name": "Multi-Step Web RCE Chain",
                    "description": "Complete attack chain leading to remote code execution",
                    "steps": [
                        {
                            "step": 1,
                            "finding": "Cross-Site Request Forgery",
                            "impact": "Trick admin into performing actions",
                            "importance": "High"
                        },
                        {
                            "step": 2,
                            "finding": "File Upload Vulnerability",
                            "impact": "Upload malicious file",
                            "importance": "Critical"
                        },
                        {
                            "step": 3,
                            "finding": "Path Traversal",
                            "impact": "Navigate to uploaded file location",
                            "importance": "High"
                        },
                        {
                            "step": 4,
                            "finding": "Code Execution",
                            "impact": "Execute uploaded code",
                            "importance": "Critical"
                        }
                    ],
                    "total_steps": 4,
                    "chain_severity": "Critical",
                    "success_probability": 0.89,
                    "estimated_time_to_exploit": "15 minutes"
                },
                {
                    "chain_id": str(uuid.uuid4()),
                    "name": "Database Exfiltration Chain",
                    "description": "Chain to extract sensitive data",
                    "steps": [
                        {
                            "step": 1,
                            "finding": "SQL Injection",
                            "impact": "Query database",
                            "importance": "Critical"
                        },
                        {
                            "step": 2,
                            "finding": "Information Disclosure",
                            "impact": "Extract schema information",
                            "importance": "High"
                        },
                        {
                            "step": 3,
                            "finding": "Data Exfiltration",
                            "impact": "Extract sensitive data",
                            "importance": "Critical"
                        }
                    ],
                    "total_steps": 3,
                    "chain_severity": "Critical",
                    "success_probability": 0.95,
                    "estimated_time_to_exploit": "10 minutes"
                }
            ],
            "recommendation": {
                "highest_priority_chain": "Multi-Step Web RCE Chain",
                "estimated_business_impact": "Very High",
                "urgent_action_required": True
            }
        }

        return chains

    async def map_scope(
        self,
        target: str,
        include_subdomains: bool = True,
        include_ip_ranges: bool = True
    ) -> dict:
        """Map target scope"""

        scope = {
            "target": target,
            "scope_id": str(uuid.uuid4()),
            "in_scope": {
                "domains": [
                    "example.com",
                    "api.example.com",
                    "admin.example.com",
                    "cdn.example.com"
                ] if include_subdomains else ["example.com"],
                "ip_ranges": [
                    "93.184.216.0/24",
                    "93.184.217.0/24"
                ] if include_ip_ranges else [],
                "wildcard_domains": [
                    "*.example.com"
                ],
                "specific_ips": [
                    "93.184.216.34",
                    "93.184.216.50",
                    "93.184.216.51"
                ]
            },
            "out_of_scope": {
                "domains": [
                    "partner.example.com",
                    "affiliate.example.com"
                ],
                "services": [
                    "Third-party payment processors",
                    "External analytics providers"
                ]
            },
            "scope_statistics": {
                "total_domains": 4 if include_subdomains else 1,
                "total_ip_ranges": 2 if include_ip_ranges else 0,
                "total_ips": 3 if include_ip_ranges else 0,
                "attack_surface_area": "Large"
            },
            "scope_visualization": {
                "type": "network_diagram",
                "layers": [
                    {
                        "layer": "Public Web",
                        "assets": ["example.com", "api.example.com"]
                    },
                    {
                        "layer": "Admin Panel",
                        "assets": ["admin.example.com"]
                    },
                    {
                        "layer": "Infrastructure",
                        "assets": ["cdn.example.com", "Mail Server"]
                    }
                ]
            }
        }

        return scope


# Server initialization
graph_server = GraphMCPServer()
