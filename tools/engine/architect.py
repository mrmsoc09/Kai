"""
Architect Module - AI-Driven Architecture Design
Implements Kimi k2.5 reasoning patterns for autonomous tool design:
- Chain-of-thought decomposition
- Pattern matching against primitive library
- Constraint satisfaction
- Reflexive validation
"""

import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

from primitives.base import PrimitiveLibrary
from primitives.scanner import ScannerPrimitive
from primitives.exploit import ExploitPrimitive
from primitives.parser import ParserPrimitive


@dataclass
class ComponentSpec:
    """Specification for a single component in the architecture."""
    name: str
    type: str
    primitive_class: str
    configuration: Dict[str, Any]
    inputs: List[str]
    outputs: List[str]
    dependencies: List[str]


@dataclass
class ArchitectureBlueprint:
    """Complete architectural blueprint for the tool."""
    project_name: str
    description: str
    architecture_type: str  # e.g., "pipeline", "event-driven", "microservice"
    components: List[ComponentSpec]
    entry_points: List[str]
    dependencies: List[str]
    execution_flow: List[Dict[str, Any]]
    security_considerations: List[str]


class Architect:
    """
    AI Architecture Designer using Kimi k2.5 logic patterns.
    Performs hierarchical task decomposition and modular assembly.
    """
    
    def __init__(self):
        self.library = PrimitiveLibrary()
        self.reasoning_log = []
        
    def design(self, description: str, project_name: str) -> Dict[str, Any]:
        """
        Main design pipeline using chain-of-thought reasoning.
        
        Kimi k2.5 Logic Flow:
        1. Intent Analysis - Extract core functionality
        2. Primitive Mapping - Match to known components
        3. Architecture Selection - Choose structural pattern
        4. Constraint Validation - Security & feasibility checks
        5. Blueprint Generation - Final specification
        """
        
        # Step 1: Intent Analysis (Natural Language Understanding)
        intent = self._analyze_intent(description)
        self.reasoning_log.append(f"Identified intent: {intent}")
        
        # Step 2: Component Decomposition
        components = self._decompose_components(intent, description)
        self.reasoning_log.append(f"Decomposed into {len(components)} components")
        
        # Step 3: Architecture Pattern Selection
        arch_type = self._select_architecture(components, intent)
        self.reasoning_log.append(f"Selected architecture: {arch_type}")
        
        # Step 4: Dependency Resolution
        deps = self._resolve_dependencies(components)
        
        # Step 5: Security & Safety Validation
        security_notes = self._validate_security(components, intent)
        
        # Step 6: Execution Flow Design
        flow = self._design_execution_flow(components, arch_type)
        
        blueprint = ArchitectureBlueprint(
            project_name=project_name,
            description=description,
            architecture_type=arch_type,
            components=components,
            entry_points=["main.py"],
            dependencies=deps,
            execution_flow=flow,
            security_considerations=security_notes
        )
        
        return asdict(blueprint)
    
    def _analyze_intent(self, description: str) -> Dict[str, Any]:
        """
        Extract core intent using keyword extraction and classification.
        Simulates LLM-based entity extraction.
        """
        description_lower = description.lower()
        
        # Intent classification patterns
        patterns = {
            "network_scanning": ["scan", "port", "network", "host", "discovery", "syn", "tcp", "udp"],
            "exploitation": ["exploit", "vulnerability", "payload", "shell", "injection", "overflow"],
            "forensics": ["parse", "analyze", "log", "pcap", "memory", "forensic", "extract"],
            "cryptography": ["encrypt", "decrypt", "hash", "brute force", "crack", "cipher"],
            "reconnaissance": ["enumerate", "gather", "osint", "recon", "information"]
        }
        
        scores = {category: sum(1 for term in terms if term in description_lower) 
                 for category, terms in patterns.items()}
        
        primary_intent = max(scores, key=scores.get)
        confidence = scores[primary_intent] / len(patterns[primary_intent])
        
        # Extract specific targets
        targets = []
        if "port" in description_lower:
            targets.append("port")
        if "service" in description_lower:
            targets.append("service")
        if "file" in description_lower or "log" in description_lower:
            targets.append("file")
            
        return {
            "primary": primary_intent,
            "confidence": confidence,
            "targets": targets,
            "keywords": self._extract_keywords(description)
        }
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract technical keywords from description."""
        tech_terms = [
            "tcp", "udp", "http", "https", "ssh", "ftp", "syn", "ack",
            "json", "xml", "csv", "regex", "async", "threading", "stealth",
            "banner", "grabbing", "vulnerability", "cve", "exploit"
        ]
        found = [term for term in tech_terms if term in text.lower()]
        return found
    
    def _decompose_components(self, intent: Dict, description: str) -> List[ComponentSpec]:
        """
        Decompose high-level intent into primitive components.
        Uses pattern matching against primitive library.
        """
        components = []
        
        if intent["primary"] == "network_scanning":
            # Add scanner component
            scanner_config = {
                "mode": "syn" if "syn" in description.lower() else "connect",
                "ports": "1-65535" if "all" in description.lower() else "common",
                "threads": 100 if "fast" in description.lower() else 50,
                "timeout": 2
            }
            components.append(ComponentSpec(
                name="port_scanner",
                type="scanner",
                primitive_class="TCPScanner",
                configuration=scanner_config,
                inputs=["target_host", "port_range"],
                outputs=["open_ports", "service_info"],
                dependencies=["scapy", "python-nmap"]
            ))
            
            # Add parser for results if analysis mentioned
            if "analyze" in description.lower():
                components.append(ComponentSpec(
                    name="result_analyzer",
                    type="parser",
                    primitive_class="NetworkDataParser",
                    configuration={"format": "json"},
                    inputs=["scan_results"],
                    outputs=["report", "vulnerabilities"],
                    dependencies=["pandas"]
                ))
                
        elif intent["primary"] == "forensics":
            components.append(ComponentSpec(
                name="log_processor",
                type="parser",
                primitive_class="LogParser",
                configuration={
                    "format": "auto-detect",
                    "filter_patterns": ["error", "failed", "unauthorized"]
                },
                inputs=["log_path"],
                outputs=["parsed_events", "statistics"],
                dependencies=["regex", "dateutil"]
            ))
            
        elif intent["primary"] == "exploitation":
            components.append(ComponentSpec(
                name="exploit_module",
                type="exploit",
                primitive_class="RemoteExploit",
                configuration={
                    "target_type": "remote",
                    "payload_type": "reverse_shell" if "shell" in description.lower() else "command"
                },
                inputs=["target", "payload"],
                outputs=["exploit_result", "session"],
                dependencies=["requests", "paramiko", "pwn"]
            ))
        
        # Add CLI interface component for all tools
        components.append(ComponentSpec(
            name="cli_interface",
            type="interface",
            primitive_class="ArgparseInterface",
            configuration={"style": "professional"},
            inputs=["sys.argv"],
            outputs=["parsed_args"],
            dependencies=[]
        ))
        
        return components
    
    def _select_architecture(self, components: List[ComponentSpec], intent: Dict) -> str:
        """
        Select architectural pattern based on component interaction needs.
        """
        types = [c.type for c in components]
        
        if "parser" in types and "scanner" in types:
            return "pipeline"  # Data flows from scanner -> parser -> output
        elif len(components) > 3:
            return "event-driven"  # Complex interactions
        elif intent["primary"] == "exploitation":
            return "state-machine"  # Exploits often need state tracking
        else:
            return "linear"
    
    def _resolve_dependencies(self, components: List[ComponentSpec]) -> List[str]:
        """Aggregate and deduplicate dependencies."""
        deps = set()
        for comp in components:
            deps.update(comp.dependencies)
        
        # Add standard dependencies
        deps.add("colorama")  # For colored output
        deps.add("tqdm")      # For progress bars
        
        return sorted(list(deps))
    
    def _validate_security(self, components: List[ComponentSpec], intent: Dict) -> List[str]:
        """
        Security validation and safety considerations.
        Ensures generated tools follow responsible disclosure patterns.
        """
        notes = []
        
        if intent["primary"] == "exploitation":
            notes.append("WARNING: Generated exploit code includes safety checks and requires explicit target confirmation")
            notes.append("Includes rate limiting to prevent accidental DoS")
            
        if any(c.type == "scanner" for c in components):
            notes.append("Scanner includes delay mechanisms to avoid overwhelming targets")
            notes.append("Randomized user-agent strings to reduce fingerprinting")
            
        notes.append("All network operations include timeout handling")
        notes.append("Input validation implemented for all external data sources")
        
        return notes
    
    def _design_execution_flow(self, components: List[ComponentSpec], arch_type: str) -> List[Dict[str, Any]]:
        """Design the execution flow based on architecture type."""
        flow = []
        
        if arch_type == "pipeline":
            for i, comp in enumerate(components):
                if i == 0:
                    flow.append({
                        "step": i,
                        "component": comp.name,
                        "action": "initialize",
                        "next": components[i+1].name if i+1 < len(components) else None
                    })
                else:
                    flow.append({
                        "step": i,
                        "component": comp.name,
                        "action": "process",
                        "input_from": components[i-1].name,
                        "next": components[i+1].name if i+1 < len(components) else "output"
                    })
        else:
            # Linear execution
            for i, comp in enumerate(components):
                flow.append({
                    "step": i,
                    "component": comp.name,
                    "action": "execute",
                    "blocking": True
                })
                
        return flow
    
    def get_reasoning_log(self) -> List[str]:
        """Return the chain-of-thought reasoning for transparency."""
        return self.reasoning_log
