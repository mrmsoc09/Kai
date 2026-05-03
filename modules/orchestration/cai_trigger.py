"""
CAI Activation Trigger Logic

Determines when to activate the CAI autonomous agent based on Tier 1 recon results.
Triggers are heuristic patterns indicating complex targets that benefit from AI analysis.
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class TriggerPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class CAITriggerResult:
    """Result of trigger evaluation."""
    should_activate: bool
    trigger_name: str
    priority: TriggerPriority
    task: str
    context: Dict[str, Any]
    confidence: float  # 0-1


class CAITrigger:
    """
    Analyzes Tier 1 reconnaissance results to determine CAI activation triggers.
    
    Trigger conditions identify targets where:
    - Complex JS frameworks indicate DOM-based vulnerabilities
    - Authentication flows suggest bypass opportunities
    - Large API surfaces need intelligent exploration
    - Human-like reasoning adds value beyond signature matching
    """
    
    # Signal patterns that indicate CAI value
    TRIGGER_DEFINITIONS = {
        "spa_react": {
            "signals": ["react", "reactjs", "__react", "data-reactroot"],
            "priority": TriggerPriority.MEDIUM,
            "tier": 2,
            "task": "analyze_react_app",
            "description": "React SPA detected - potential for DOM XSS, client-side routing issues"
        },
        "spa_angular": {
            "signals": ["angular", "ng-", "data-ng-", "angular.js"],
            "priority": TriggerPriority.MEDIUM,
            "tier": 2,
            "task": "analyze_angular_app",
            "description": "Angular SPA detected - check for template injection, CSP bypass"
        },
        "spa_vue": {
            "signals": ["vue", "vue.js", "v-", "__vue__"],
            "priority": TriggerPriority.MEDIUM,
            "tier": 2,
            "task": "analyze_vue_app",
            "description": "Vue.js SPA detected - analyze for XSS, component vulnerabilities"
        },
        "auth_detected": {
            "signals": [
                "login", "signin", "auth", "oauth", "sso", "token",
                "session", "jwt", "bearer", "password"
            ],
            "priority": TriggerPriority.HIGH,
            "tier": 2,
            "task": "test_authentication",
            "description": "Authentication mechanism present - test for bypass, weak tokens"
        },
        "api_surface": {
            "signals": ["/api/", "graphql", "swagger", "openapi", "/v1/", "/v2/"],
            "priority": TriggerPriority.HIGH,
            "tier": 2,
            "task": "analyze_api_surface",
            "description": "API endpoints detected - test for BOLA, IDOR, weak authorization"
        },
        "graphql_endpoint": {
            "signals": ["/graphql", "query:", "mutation:", "subscription:"],
            "priority": TriggerPriority.HIGH,
            "tier": 2,
            "task": "test_graphql",
            "description": "GraphQL endpoint found - test for introspection, query injection"
        },
        "admin_panel": {
            "signals": ["admin", "dashboard", "manage", "panel", "/admin", "/manage"],
            "priority": TriggerPriority.CRITICAL,
            "tier": 3,
            "task": "deep_admin_assessment",
            "description": "Admin interface detected - high-value target for privilege escalation"
        },
        "payment_flow": {
            "signals": ["checkout", "payment", "billing", "cart", "stripe", "paypal"],
            "priority": TriggerPriority.CRITICAL,
            "tier": 3,
            "task": "test_business_logic",
            "description": "Payment flow detected - test for price manipulation, logic flaws"
        },
        "complex_forms": {
            "signals": ["multipart/form-data", "file upload", "drag and drop"],
            "priority": TriggerPriority.MEDIUM,
            "tier": 2,
            "task": "test_file_upload",
            "description": "File upload capability - test for malicious file handling"
        },
        "websocket": {
            "signals": ["websocket", "ws://", "wss://", "socket.io"],
            "priority": TriggerPriority.HIGH,
            "tier": 2,
            "task": "test_websocket",
            "description": "WebSocket detected - test for auth bypass, message injection"
        },
        "serialization": {
            "signals": ["json", "xml", "yaml", "pickle", "serialization"],
            "priority": TriggerPriority.HIGH,
            "tier": 2,
            "task": "test_deserialization",
            "description": "Serialization format found - test for injection vulnerabilities"
        }
    }
    
    @classmethod
    def evaluate(cls, tier1_results: Dict[str, Any]) -> Optional[CAITriggerResult]:
        """
        Analyze Tier 1 results and determine if CAI should activate.
        
        Args:
            tier1_results: Output from Tier 1 tools (HTTPX, Katana, etc.)
            
        Returns:
            CAITriggerResult if activation warranted, None otherwise
        """
        # Build content corpus from all tool outputs
        content_corpus = cls._extract_content_corpus(tier1_results)
        
        # Score each trigger
        trigger_scores = []
        
        for trigger_name, definition in cls.TRIGGER_DEFINITIONS.items():
            score = cls._score_trigger(content_corpus, definition)
            if score > 0:
                trigger_scores.append((trigger_name, score, definition))
        
        if not trigger_scores:
            return None
        
        # Select highest priority trigger
        # Sort by priority desc, then score desc
        trigger_scores.sort(
            key=lambda x: (x[1]["priority"].value, x[1]),
            reverse=True
        )
        
        best_trigger = trigger_scores[0]
        trigger_name = best_trigger[0]
        definition = best_trigger[2]
        confidence = best_trigger[1] / len(definition["signals"])
        
        return CAITriggerResult(
            should_activate=True,
            trigger_name=trigger_name,
            priority=definition["priority"],
            task=definition["task"],
            context={
                "description": definition["description"],
                "tier": definition["tier"],
                "matched_signals": cls._get_matched_signals(content_corpus, definition["signals"])
            },
            confidence=min(confidence, 1.0)
        )
    
    @classmethod
    def _extract_content_corpus(cls, results: Dict) -> str:
        """Extract searchable content from Tier 1 results."""
        corpus_parts = []
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    corpus_parts.append(str(k).lower())
                    extract_recursive(v)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
            elif isinstance(obj, str):
                corpus_parts.append(obj.lower())
        
        extract_recursive(results)
        return " ".join(corpus_parts)
    
    @classmethod
    def _score_trigger(cls, corpus: str, definition: Dict) -> int:
        """Count how many trigger signals match in corpus."""
        score = 0
        for signal in definition["signals"]:
            if signal.lower() in corpus:
                score += 1
        return score
    
    @classmethod
    def _get_matched_signals(cls, corpus: str, signals: List[str]) -> List[str]:
        """Return list of signals that matched."""
        return [s for s in signals if s.lower() in corpus]
    
    @classmethod
    def get_all_trigger_names(cls) -> List[str]:
        """Return list of available trigger names."""
        return list(cls.TRIGGER_DEFINITIONS.keys())
    
    @classmethod
    def should_activate_for_target(cls, target: str, tool_outputs: List[Dict]) -> bool:
        """
        Convenience method for quick check.
        
        Example:
            if CAITrigger.should_activate_for_target(url, outputs):
                cai_results = await cai_agent.execute(...)
        """
        results = {"target": target, "tools": tool_outputs}
        trigger = cls.evaluate(results)
        return trigger is not None and trigger.confidence > 0.3


# Integration helper for orchestrator
class CAITriggerIntegration:
    """Helper for integrating triggers into the orchestration workflow."""
    
    @staticmethod
    def check_and_activate(tier1_results: Dict, orchestrator) -> Optional[Dict]:
        """
        Check triggers and optionally activate CAI.
        Returns CAI results if activated, None otherwise.
        """
        trigger = CAITrigger.evaluate(tier1_results)
        
        if not trigger or trigger.confidence < 0.3:
            return None
        
        # Import CAI wrapper
        from tools.wrappers.cai_autonomous_agent import CAIAutonomousAgent
        
        # Initialize agent
        agent = CAIAutonomousAgent()
        
        # Build task from trigger
        target = tier1_results.get("target", "")
        task = trigger.task.replace("_", " ")
        
        # Async execution would go here
        # For now, return trigger info for manual activation
        return {
            "trigger": trigger,
            "suggested_task": task,
            "target": target,
            "agent_ready": True,
            "reasoning": trigger.context.get("description")
        }


# Simple test
if __name__ == "__main__":
    # Test trigger detection
    test_results = {
        "target": "https://example.com",
        "tools": [
            {"tool": "httpx", "output": "React SPA - /api/v1/users found"},
            {"tool": "katana", "output": {"js_files": ["app.js", "react-dom.js"], "endpoints": ["/login", "/api/graphql"]}}
        ]
    }
    
    trigger = CAITrigger.evaluate(test_results)
    
    if trigger:
        print(f"CAI should activate!")
        print(f"  Trigger: {trigger.trigger_name}")
        print(f"  Task: {trigger.task}")
        print(f"  Priority: {trigger.priority.name}")
        print(f"  Confidence: {trigger.confidence:.2f}")
        print(f"  Context: {trigger.context}")
    else:
        print("No CAI activation triggers found")
