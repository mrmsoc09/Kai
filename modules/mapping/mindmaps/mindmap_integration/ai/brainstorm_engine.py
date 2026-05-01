"""
AI-driven brainstorming and architectural enhancement engine.
Implements logic patterns inspired by Kimi k2.5 for:
- Pattern recognition in architecture
- Security threat modeling expansion
- Creative brainstorming facilitation
"""

import random
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass

from ..core.models import MindMap, Node, NodeType, Edge, EdgeType


@dataclass
class Pattern:
    """Recognized architectural or security pattern."""
    name: str
    indicators: List[str]
    suggestions: List[str]
    category: str  # 'architecture', 'security', 'performance'


class BrainstormEngine:
    """
    AI engine for expanding mindmaps with intelligent suggestions.
    Uses pattern matching, graph analysis, and domain knowledge.
    """
    
    def __init__(self):
        self.architectural_patterns = self._load_architectural_patterns()
        self.security_patterns = self._load_security_patterns()
        self.brainstorm_templates = self._load_brainstorm_templates()
    
    def enhance_architecture(self, mindmap: MindMap) -> MindMap:
        """
        Analyze codebase architecture and suggest improvements.
        Adds nodes for missing layers, patterns, and concerns.
        """
        # Analyze existing structure
        components = [n for n in mindmap.nodes.values() 
                     if n.type == NodeType.COMPONENT]
        
        # Detect missing architectural layers
        layers = self._detect_layers(components)
        
        if not any(l in layers for l in ['api', 'controller', 'route']):
            self._add_suggestion_node(mindmap, "Consider adding API Gateway layer", 
                                    "architecture")
        
        if not any(l in layers for l in ['db', 'database', 'repository', 'model']):
            self._add_suggestion_node(mindmap, "Data persistence layer not detected", 
                                    "architecture")
        
        # Check for security considerations
        if not any(n.type == NodeType.SECURITY_RISK for n in mindmap.nodes.values()):
            security_node = Node(
                id="ai_security_review",
                label="🔒 Security Considerations",
                type=NodeType.SECURITY_RISK,
                metadata={"ai_generated": True, "category": "security_review"}
            )
            mindmap.add_node(security_node)
            
            # Link to root or main components
            root = mindmap.get_root()
            if root:
                mindmap.add_edge(Edge(
                    source=root.id,
                    target=security_node.id,
                    type=EdgeType.SUGGESTS,
                    label="AI Suggestion"
                ))
            
            # Add specific security concerns
            concerns = ["Authentication", "Authorization", "Input Validation", 
                       "Secrets Management"]
            for concern in concerns:
                child = Node(
                    id=f"sec_{concern.lower().replace(' ', '_')}",
                    label=concern,
                    type=NodeType.LEAF,
                    parent_id=security_node.id
                )
                mindmap.add_node(child)
                mindmap.add_edge(Edge(
                    source=security_node.id,
                    target=child.id,
                    type=EdgeType.RELATES
                ))
        
        return mindmap
    
    def enhance_security(self, mindmap: MindMap) -> MindMap:
        """
        Expand attack surface analysis with AI-driven threat modeling.
        Applies STRIDE methodology and common attack patterns.
        """
        vulnerabilities = [n for n in mindmap.nodes.values() 
                          if n.type == NodeType.SECURITY_RISK]
        
        if not vulnerabilities:
            return mindmap
        
        # Add threat modeling categories
        stride_categories = [
            ("Spoofing", "Authentication threats"),
            ("Tampering", "Integrity threats"),
            ("Repudiation", "Non-repudiation threats"),
            ("Information Disclosure", "Confidentiality threats"),
            ("Denial of Service", "Availability threats"),
            ("Elevation of Privilege", "Authorization threats")
        ]
        
        root = mindmap.get_root()
        if not root:
            return mindmap
        
        for category, description in stride_categories:
            # Check if already present
            if not any(category in n.label for n in mindmap.nodes.values()):
                cat_node = Node(
                    id=f"stride_{category.lower().replace(' ', '_')}",
                    label=f"⚠️ {category}",
                    type=NodeType.BRANCH,
                    metadata={"stride_category": category, "description": description}
                )
                mindmap.add_node(cat_node)
                mindmap.add_edge(Edge(
                    source=root.id,
                    target=cat_node.id,
                    type=EdgeType.RELATES,
                    label="threat model"
                ))
                
                # Add common attack vectors for each category
                vectors = self._get_attack_vectors(category)
                for vector in vectors:
                    vec_node = Node(
                        id=f"vec_{category}_{vector}",
                        label=vector,
                        type=NodeType.LEAF,
                        parent_id=cat_node.id
                    )
                    mindmap.add_node(vec_node)
                    mindmap.add_edge(Edge(
                        source=cat_node.id,
                        target=vec_node.id,
                        type=EdgeType.RELATES
                    ))
        
        return mindmap
    
    def expand_ideas(self, mindmap: MindMap, root_id: str, 
                    context: Optional[str], depth: int) -> MindMap:
        """
        AI-driven brainstorming expansion.
        Generates creative associations and structured thinking paths.
        """
        if depth <= 0:
            return mindmap
        
        root = mindmap.nodes.get(root_id)
        if not root:
            return mindmap
        
        # Determine expansion strategy based on topic
        topic = root.label.lower()
        
        # Select expansion template
        if any(word in topic for word in ["security", "attack", "threat"]):
            templates = self.security_patterns
        elif any(word in topic for word in ["architecture", "system", "design"]):
            templates = self.architectural_patterns
        else:
            templates = self.brainstorm_templates
        
        # Generate branches (3-5 per level for optimal brainstorming)
        num_branches = min(5, max(3, 6 - depth))
        
        for i in range(num_branches):
            if templates:
                template = random.choice(templates)
                label = template.suggestions[i % len(template.suggestions)]
                category = template.category
            else:
                label = f"Aspect {i+1}"
                category = "general"
            
            branch = Node(
                id=f"brain_{root_id}_{i}",
                label=label,
                type=NodeType.IDEA,
                parent_id=root_id,
                depth=root.depth + 1,
                metadata={"ai_generated": True, "category": category}
            )
            mindmap.add_node(branch)
            mindmap.add_edge(Edge(
                source=root_id,
                target=branch.id,
                type=EdgeType.SUGGESTS
            ))
            
            # Recursive expansion for next level
            if depth > 1:
                self.expand_ideas(mindmap, branch.id, context, depth - 1)
        
        return mindmap
    
    def _detect_layers(self, components: List[Node]) -> Set[str]:
        """Detect architectural layers from component names."""
        layers = set()
        for comp in components:
            name = comp.label.lower()
            if any(x in name for x in ['api', 'route', 'controller', 'endpoint']):
                layers.add('api')
            elif any(x in name for x in ['service', 'business', 'logic']):
                layers.add('service')
            elif any(x in name for x in ['repo', 'dao', 'model', 'entity', 'db']):
                layers.add('data')
            elif any(x in name for x in ['util', 'helper', 'common']):
                layers.add('utility')
        return layers
    
    def _add_suggestion_node(self, mindmap: MindMap, message: str, 
                            category: str) -> None:
        """Add an AI suggestion node to the mindmap."""
        root = mindmap.get_root()
        if not root:
            return
        
        sugg_id = f"sugg_{len(mindmap.nodes)}"
        node = Node(
            id=sugg_id,
            label=f"💡 {message}",
            type=NodeType.IDEA,
            metadata={"ai_generated": True, "category": category, "suggestion": True}
        )
        mindmap.add_node(node)
        mindmap.add_edge(Edge(
            source=root.id,
            target=sugg_id,
            type=EdgeType.SUGGESTS,
            label="AI Analysis"
        ))
    
    def _get_attack_vectors(self, stride_category: str) -> List[str]:
        """Get common attack vectors for STRIDE category."""
        vectors = {
            "Spoofing": ["Credential stuffing", "Session hijacking", "Phishing"],
            "Tampering": ["SQL injection", "Command injection", "Parameter tampering"],
            "Repudiation": ["Log tampering", "Transaction repudiation"],
            "Information Disclosure": ["Data leakage", "Verbose errors", "IDOR"],
            "Denial of Service": ["Resource exhaustion", "DDoS", "Algorithmic complexity"],
            "Elevation of Privilege": ["Privilege escalation", "Forced browsing", "JWT manipulation"]
        }
        return vectors.get(stride_category, ["Unknown vector"])
    
    def _load_architectural_patterns(self) -> List[Pattern]:
        """Load architectural pattern definitions."""
        return [
            Pattern("Microservices", ["service", "api", "gateway"], 
                   ["Service Discovery", "Circuit Breaker", "Load Balancer"], "architecture"),
            Pattern("Layered", ["controller", "service", "repository"], 
                   ["DTO Layer", "Validation Layer", "Caching Layer"], "architecture"),
            Pattern("Event-Driven", ["event", "queue", "message"], 
                   ["Event Bus", "Saga Pattern", "CQRS"], "architecture")
        ]
    
    def _load_security_patterns(self) -> List[Pattern]:
        """Load security pattern definitions."""
        return [
            Pattern("Defense in Depth", ["auth", "encrypt", "validate"], 
                   ["WAF", "IDS/IPS", "Zero Trust"], "security"),
            Pattern("Secure Communication", ["tls", "ssl", "https"], 
                   ["Certificate Pinning", "mTLS", "Secret Rotation"], "security")
        ]
    
    def _load_brainstorm_templates(self) -> List[Pattern]:
        """Load generic brainstorming templates."""
        return [
            Pattern("5W1H", [], ["Who", "What", "When", "Where", "Why", "How"], "general"),
            Pattern("SWOT", [], ["Strengths", "Weaknesses", "Opportunities", "Threats"], "business"),
            Pattern("Design Thinking", [], ["Empathize", "Define", "Ideate", "Prototype", "Test"], "design")
        ]
