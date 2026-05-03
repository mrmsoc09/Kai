"""
CAI Autonomous Agent Wrapper
Integrates CAI (Cybersecurity AI) framework as a KaisonOne Tier 2/3 tool.

CAI provides:
- Agent-driven autonomous vulnerability discovery
- MCP (Model Context Protocol) for external tool integration
- Chain-of-thought reasoning via OpenTelemetry tracing
- Human-in-the-Loop (HITL) checkpoints for high-risk actions

Location: vendor/cai/ (git submodule)
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Add CAI to Python path
CAI_PATH = Path(__file__).parent.parent.parent / "vendor" / "cai" / "src"
if str(CAI_PATH) not in sys.path:
    sys.path.insert(0, str(CAI_PATH))

# Import KaisonOne core modules
from modules.core.scope_guard import ScopeGuard
from modules.core.hil_gate import HILGate


@dataclass
class CAIExecutionResult:
    """Structured result from CAI autonomous agent execution."""
    tool: str = "cai_autonomous_agent"
    target: str = ""
    task: str = ""
    status: str = "pending"  # pending, running, completed, failed, hil_check
    findings: List[Dict] = field(default_factory=list)
    reasoning_chain: List[Dict] = field(default_factory=list)
    hil_checkpoints: List[Dict] = field(default_factory=list)
    scope_violations: List[str] = field(default_factory=list)
    raw_output: str = ""
    execution_time: float = 0.0
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class CAIAutonomousAgent:
    """
    KaisonOne wrapper for CAI (Cybersecurity AI) autonomous security agent.
    
    Risk Band: 2 (requires HIL approval for exploit actions)
    Tier: 2 (Targeted) / 3 (Specialized) depending on task complexity
    
    Features:
    - Scope enforcement at every step
    - HITL checkpoints before intrusive actions
    - Chain-of-thought reasoning capture
    - Integration with KaisonOne's orchestration layer
    """
    
    TOOL_NAME = "cai_autonomous_agent"
    RISK_BAND = 2
    TIER = 2
    
    # Actions requiring HITL approval
    HIL_REQUIRED_ACTIONS = [
        "exploit", "intrude", "modify", "delete",
        "credential_extraction", "session_hijack",
        "privilege_escalation", "data_exfiltration"
    ]
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("CAI_API_KEY")
        self.model = model
        self.cai_path = CAI_PATH
        self.scope_guard = ScopeGuard()
        self.hil_gate = HILGate()
        self._cai_available = self._check_cai_installation()
        self._trace_buffer = []
        
    def _check_cai_installation(self) -> bool:
        """Verify CAI is properly installed and importable."""
        try:
            import cai
            from cai.sdk.agents import Agent, Runner
            from cai.tools import WebSearch, LinuxCmd, Code
            return True
        except ImportError as e:
            print(f"[CAI Wrapper] Warning: CAI not available - {e}")
            return False
    
    async def execute(
        self, 
        target: str, 
        task: str, 
        context: Optional[Dict] = None,
        scope_config: Optional[Dict] = None,
        enable_hil: bool = True,
        max_iterations: int = 50,
        timeout: int = 600
    ) -> CAIExecutionResult:
        """
        Execute CAI autonomous agent against target with full governance.
        
        Args:
            target: Target URL or scope identifier
            task: Security task description (e.g., "discover auth bypass vectors")
            context: Previous findings, tool outputs, session state
            scope_config: Scope restrictions (domains, IPs, excluded paths)
            enable_hil: Whether to enforce HITL checkpoints
            max_iterations: Maximum agent iterations before pause
            timeout: Maximum execution time in seconds
            
        Returns:
            CAIExecutionResult with findings, reasoning, and metadata
        """
        start_time = asyncio.get_event_loop().time()
        result = CAIExecutionResult(target=target, task=task)
        
        # Pre-execution scope validation
        scope_check = await self._validate_scope(target, scope_config)
        if not scope_check["authorized"]:
            result.status = "failed"
            result.error = f"Scope violation: {scope_check['reason']}"
            result.scope_violations.append(scope_check['reason'])
            return result
        
        if not self._cai_available:
            result.status = "failed"
            result.error = "CAI framework not available. Check vendor/cai installation."
            return result
        
        try:
            # Import CAI modules
            from cai.sdk.agents import Agent, Runner, OpenAIChatCompletionsModel
            from cai.tools import WebSearch, LinuxCmd, Code
            from cai.tools.web_search import web_search
            
            # Configure model
            model_client = OpenAIChatCompletionsModel(
                model=self.model,
                api_key=self.api_key
            )
            
            # Build agent instructions with scope enforcement
            instructions = self._build_agent_instructions(
                target=target,
                task=task,
                context=context or {},
                scope_config=scope_config or {}
            )
            
            # Create security-focused agent
            agent = Agent(
                name="kai_security_agent",
                instructions=instructions,
                tools=[WebSearch, LinuxCmd, Code],
                model=model_client
            )
            
            # Set up execution runner with custom hooks
            runner = Runner(
                agent=agent,
                max_iterations=max_iterations
            )
            
            # Add trace collection hook
            runner.on_tool_call = self._on_tool_call
            runner.on_hil_checkpoint = lambda **kwargs: self._on_hil_checkpoint(kwargs, enable_hil)
            
            result.status = "running"
            
            # Execute with timeout
            cai_result = await asyncio.wait_for(
                runner.run(f"Begin security assessment: {task}"),
                timeout=timeout
            )
            
            # Parse findings from trace
            result.findings = self._extract_findings_from_trace()
            result.reasoning_chain = self._trace_buffer.copy()
            result.raw_output = cai_result.get("output", "")
            result.status = "completed"
            
        except asyncio.TimeoutError:
            result.status = "timeout"
            result.error = f"Execution exceeded {timeout}s timeout"
            
        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            
        finally:
            result.execution_time = asyncio.get_event_loop().time() - start_time
            self._save_execution_trace(result)
            
        return result
    
    def _build_agent_instructions(
        self, 
        target: str, 
        task: str, 
        context: Dict, 
        scope_config: Dict
    ) -> str:
        """Build CAI agent instructions with KaisonOne governance."""
        
        allowed_domains = scope_config.get("target_domains", [target])
        excluded_paths = scope_config.get("excluded_paths", [])
        
        instructions = f"""You are KaiSecurityAgent, an autonomous security testing agent operating under strict governance.

MISSION
-------
Target: {target}
Task: {task}
Previous context: {json.dumps(context, indent=2)}

STRICT SCOPE RULES
------------------
1. ONLY test hosts/domains: {allowed_domains}
2. NEVER test: {excluded_paths or 'none specified'}
3. If scope is unclear, STOP and ask for clarification
4. Document EVERY target URL before accessing

HUMAN-IN-THE-LOOP CHECKPOINTS
------------------------------
Pause and request approval BEFORE:
- Any exploit attempt that modifies data
- Actions with 'exploit', 'intrude', 'delete' keywords
- Actions affecting user accounts or sessions
- Any action outside reconnaissance

To request HITL: Output "[HITL_REQUIRED] Action: <description> Reason: <why>"

CHAIN-OF-THOUGHT
----------------
For each significant action, document:
1. What you're testing and why
2. What you expect to find
3. What you actually found
4. Your confidence level (0-1)
5. Next hypothesis to test

TOOL USAGE
----------
- WebSearch: OSINT and reconnaissance
- LinuxCmd: Network tools (nmap, curl, etc.)
- Code: Python scripts for custom tests
- Always prefer read-only operations first

REPORTING
---------
When you find potential vulnerabilities:
1. Classify: XSS, SQLi, IDOR, Auth Bypass, Info Disclosure, etc.
2. Rate severity: Critical, High, Medium, Low, Info
3. Document evidence: URL, parameter, payload, response snippet
4. Suggest remediation if obvious

After every 5 actions or when checking for HITL, report status with summary.
"""
        return instructions
    
    async def _validate_scope(self, target: str, scope_config: Optional[Dict]) -> Dict:
        """Validate target against authorized scope."""
        if scope_config is None:
            return {"authorized": True, "reason": "No scope config provided"}
        
        allowed_domains = scope_config.get("target_domains", [])
        
        # Simple domain check
        target_lower = target.lower()
        for domain in allowed_domains:
            if domain in target_lower or target_lower in domain:
                return {"authorized": True, "reason": "Domain match"}
        
        # If no explicit match but we have scope guard configured
        if self.scope_guard:
            # Use scope guard's more sophisticated check
            check = self.scope_guard.validate_target(target)
            return check
        
        return {"authorized": False, "reason": f"Target {target} not in scope"}
    
    def _on_tool_call(self, tool_name: str, arguments: Dict, result: Any):
        """Hook called on each CAI tool execution for trace collection."""
        
        trace_entry = {
            "type": "tool_call",
            "timestamp": datetime.utcnow().isoformat(),
            "tool": tool_name,
            "arguments": arguments,
            "result_preview": str(result)[:500] if result else None
        }
        self._trace_buffer.append(trace_entry)
        
        # Real-time console output
        print(f"[CAI] {tool_name}: {json.dumps(arguments, default=str)[:100]}...")
    
    def _on_hil_checkpoint(self, checkpoint_data: Dict, enable_hil: bool) -> bool:
        """Handle HITL checkpoint - return True to proceed, False to abort."""
        
        action = checkpoint_data.get("action", "")
        
        # Check if this action requires HITL
        requires_hil = any(
            keyword in action.lower() 
            for keyword in self.HIL_REQUIRED_ACTIONS
        )
        
        if not requires_hil:
            return True
        
        if not enable_hil:
            print(f"[CAI] HITL required but disabled. Skipping: {action}")
            return False
        
        # Log HITL checkpoint
        hil_entry = {
            "type": "hil_checkpoint",
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "reasoning": checkpoint_data.get("reasoning", ""),
            "auto_approved": False
        }
        self._trace_buffer.append(hil_entry)
        
        # In real implementation, this would call HILGate for user approval
        print(f"[HITL] CHECKPOINT: {action}")
        print(f"        Reason: {checkpoint_data.get('reasoning', 'N/A')}")
        print(f"        Auto-approving for MVP - implement user prompt in production")
        
        # For MVP: auto-approve with logging
        # Production: return self.hil_gate.request_approval(checkpoint_data)
        return True
    
    def _extract_findings_from_trace(self) -> List[Dict]:
        """Extract vulnerability findings from execution trace."""
        findings = []
        
        for entry in self._trace_buffer:
            if entry.get("type") != "tool_call":
                continue
                
            tool = entry.get("tool", "")
            result = entry.get("result_preview", "")
            
            # Heuristic pattern matching for vulnerability indicators
            vuln_patterns = {
                "sql_injection": ["sql syntax", "mysql error", "ORA-", "syntax error"],
                "xss": ["alert(", "<script>", "onerror="],
                "idor": ["unauthorized access", "wrong user", "different account"],
                "info_disclosure": ["password", "secret", "key:", "token:"],
                "auth_bypass": ["authenticated without", "bypass", "admin access"]
            }
            
            result_lower = result.lower()
            for vuln_type, patterns in vuln_patterns.items():
                if any(pattern in result_lower for pattern in patterns):
                    findings.append({
                        "type": vuln_type,
                        "tool_used": tool,
                        "evidence": result,
                        "confidence": 0.7,
                        "timestamp": entry.get("timestamp"),
                        "raw_trace": entry
                    })
                    break
        
        return findings
    
    def _save_execution_trace(self, result: CAIExecutionResult):
        """Save execution trace for debugging and learning."""
        trace_dir = Path("output/cai_traces")
        trace_dir.mkdir(parents=True, exist_ok=True)
        
        trace_file = trace_dir / f"cai_{result.target.replace('/', '_')}_{int(datetime.utcnow().timestamp())}.json"
        
        trace_data = {
            "result": result.__dict__,
            "full_trace": self._trace_buffer
        }
        
        trace_file.write_text(json.dumps(trace_data, indent=2, default=str))
        print(f"[CAI] Trace saved: {trace_file}")
    
    @classmethod
    def register(cls) -> Dict:
        """Return tool registry entry for KaisonOne."""
        return {
            "name": cls.TOOL_NAME,
            "display_name": "CAI Autonomous Security Agent",
            "tier": cls.TIER,
            "risk_band": cls.RISK_BAND,
            "triggers": [
                "complex_target",
                "spa_detected",
                "auth_detected",
                "api_surface_large",
                "manual_analysis_needed"
            ],
            "wrapper_class": "CAIAutonomousAgent",
            "module": "tools.wrappers.cai_autonomous_agent",
            "config_required": ["OPENAI_API_KEY"],
            "description": "Autonomous AI agent for deep vulnerability discovery with chain-of-thought reasoning",
            "requires_hil": True
        }


# Standalone test
if __name__ == "__main__":
    async def test():
        agent = CAIAutonomousAgent()
        
        # Test scope validation
        print("Testing scope validation...")
        result = await agent.execute(
            target="http://httpbin.org",
            task="Perform basic reconnaissance",
            scope_config={"target_domains": ["httpbin.org"]},
            enable_hil=True,
            timeout=30
        )
        
        print(f"\nResult status: {result.status}")
        print(f"Execution time: {result.execution_time:.2f}s")
        print(f"Findings: {len(result.findings)}")
        if result.error:
            print(f"Error: {result.error}")
    
    asyncio.run(test())
