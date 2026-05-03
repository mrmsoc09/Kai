"""
Burp + CAI Integration Wrapper

Enables CAI autonomous agent to navigate through Burp Suite proxy,
capturing traffic for analysis and allowing CAI to suggest actions
based on observed requests/responses.

This creates a feedback loop:
1. CAI navigates target via Playwright with Burp as upstream proxy
2. Burp captures all traffic
3. Bridge extracts findings from Burp exports
4. CAI analyzes traffic and suggests next testing steps
5. Repeat until vulnerability found or coverage complete
"""

import asyncio
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class BurpCAIResult:
    """Result from Burp + CAI collaborative scanning session."""
    session_id: str
    target: str
    status: str = "pending"
    burp_findings: List[Dict] = field(default_factory=list)
    cai_suggestions: List[Dict] = field(default_factory=list)
    navigation_path: List[str] = field(default_factory=list)
    requests_captured: int = 0
    execution_time: float = 0.0
    error: Optional[str] = None


class BurpCAIBridge:
    """
    Bridges CAI autonomous agent with Burp Suite traffic capture.
    
    Usage:
        bridge = BurpCAIBridge(burp_proxy="127.0.0.1:8080")
        result = await bridge.run_collaborative_scan("https://target.com")
    """
    
    def __init__(
        self,
        burp_proxy: str = "127.0.0.1:8080",
        export_dir: str = "output/burp_exports",
        cai_agent=None
    ):
        self.burp_proxy = burp_proxy
        self.export_dir = Path(export_dir)
        self.cai_agent = cai_agent
        self.session_id = f"burp_cai_{int(datetime.utcnow().timestamp())}"
        
    async def run_collaborative_scan(
        self,
        target: str,
        task: str = "systematic_security_assessment",
        max_iterations: int = 20,
        timeout: int = 600
    ) -> BurpCAIResult:
        """
        Run collaborative scan: CAI navigates, Burp captures, CAI analyzes.
        
        Args:
            target: Target URL to scan
            task: High-level task description
            max_iterations: Maximum navigation + analysis cycles
            timeout: Maximum total execution time
            
        Returns:
            BurpCAIResult with findings and suggestions
        """
        from tools.wrappers.cai_autonomous_agent import CAIAutonomousAgent
        from modules.ingest.burp_community_bridge import BurpCommunityBridge
        
        start_time = asyncio.get_event_loop().time()
        result = BurpCAIResult(session_id=self.session_id, target=target)
        
        # Initialize CAI if not provided
        if not self.cai_agent:
            self.cai_agent = CAIAutonomousAgent()
        
        # Initialize Burp bridge
        burp_bridge = BurpCommunityBridge(
            watch_dir=str(self.export_dir),
            callback=lambda findings: self._on_new_findings(findings, result)
        )
        
        print(f"[BurpCAI] Starting collaborative scan of {target}")
        print(f"[BurpCAI] Burp proxy: {self.burp_proxy}")
        
        try:
            # Start watching for Burp exports
            burp_bridge.start()
            
            # Phase 1: Initial reconnaissance
            print("[BurpCAI] Phase 1: Initial reconnaissance")
            
            nav_result = await self._cai_navigate(
                target=target,
                task="Perform initial reconnaissance: discover all forms, links, and API endpoints. Document the application structure.",
                proxy=self.burp_proxy
            )
            
            result.navigation_path.extend(nav_result.get("visited_urls", []))
            
            # Phase 2: Analyze captured traffic, iterate
            for iteration in range(max_iterations):
                print(f"[BurpCAI] Phase 2: Analysis iteration {iteration + 1}/{max_iterations}")
                
                # Get current findings from Burp
                current_findings = burp_bridge.get_processed_findings()
                
                # Ask CAI for next steps
                analysis = await self._cai_analyze_traffic(
                    target=target,
                    findings=current_findings,
                    navigation_path=result.navigation_path
                )
                
                # Store suggestions
                result.cai_suggestions.extend(analysis.get("suggestions", []))
                
                # Check if vulnerability found
                if analysis.get("vulnerability_found"):
                    print("[BurpCAI] Vulnerability identified!")
                    result.status = "vulnerability_found"
                    break
                
                # Get next action from CAI
                next_action = analysis.get("next_action")
                if not next_action:
                    print("[BurpCAI] No further actions suggested")
                    break
                
                # Execute next navigation step
                nav_result = await self._cai_navigate(
                    target=target,
                    task=next_action.get("description", "Continue exploration"),
                    starting_url=next_action.get("url"),
                    proxy=self.burp_proxy
                )
                
                result.navigation_path.extend(nav_result.get("visited_urls", []))
                
                # Check timeout
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    print(f"[BurpCAI] Timeout reached ({timeout}s)")
                    result.status = "timeout"
                    break
                
                # Small delay to allow Burp to process
                await asyncio.sleep(2)
            
            # Collect final findings
            result.burp_findings = [
                f.to_dict() for f in burp_bridge.get_processed_findings()
            ]
            result.requests_captured = len(result.burp_findings)
            
            if result.status == "pending":
                result.status = "completed"
                
        except Exception as e:
            result.status = "error"
            result.error = str(e)
            print(f"[BurpCAI] Error: {e}")
            
        finally:
            burp_bridge.stop()
            result.execution_time = asyncio.get_event_loop().time() - start_time
            
        print(f"[BurpCAI] Scan complete: {result.status}")
        print(f"[BurpCAI] Requests captured: {result.requests_captured}")
        print(f"[BurpCAI] Suggestions generated: {len(result.cai_suggestions)}")
        
        return result
    
    async def _cai_navigate(
        self,
        target: str,
        task: str,
        starting_url: Optional[str] = None,
        proxy: str = "127.0.0.1:8080"
    ) -> Dict:
        """
        Use CAI to navigate target with Burp as proxy.
        
        Returns:
            Dict with visited_urls, forms_found, etc.
        """
        # In production, this would use Playwright with proxy settings
        # For MVP, CAI uses its WebSearch/LinuxCmd tools with proxy env
        
        context = {
            "proxy": proxy,
            "starting_url": starting_url,
            "browser_automation": True
        }
        
        result = await self.cai_agent.execute(
            target=target,
            task=task,
            context=context,
            scope_config={"target_domains": [target]},
            enable_hil=True,
            timeout=120
        )
        
        # Extract navigation info from CAI result
        visited = []
        for entry in result.reasoning_chain:
            if entry.get("type") == "tool_call":
                args = entry.get("arguments", {})
                if "url" in args:
                    visited.append(args["url"])
        
        return {
            "visited_urls": visited,
            "raw_result": result
        }
    
    async def _cai_analyze_traffic(
        self,
        target: str,
        findings: List,
        navigation_path: List[str]
    ) -> Dict:
        """
        Ask CAI to analyze captured traffic and suggest next steps.
        """
        # Build traffic summary
        traffic_summary = {
            "findings_count": len(findings),
            "high_severity": len([f for f in findings if f.severity in ["high", "critical"]]),
            "endpoints_observed": list(set(f.url for f in findings))[:20],  # Limit
            "navigation_so_far": navigation_path[-10:]  # Last 10
        }
        
        analysis_prompt = f"""
        Analyze this security testing progress:
        
        Target: {target}
        Traffic captured: {traffic_summary['findings_count']} items
        High severity findings: {traffic_summary['high_severity']}
        
        Recent navigation: {traffic_summary['navigation_so_far']}
        
        Based on the captured traffic, suggest:
        1. What vulnerability might exist here?
        2. What should be tested next (specific URL/action)?
        3. If confident a vulnerability exists, explain how to confirm it.
        
        Return structured response with:
        - vulnerability_hypothesis
        - confidence (0-1)
        - next_action (specific testing step)
        - vulnerability_found (true/false)
        """
        
        result = await self.cai_agent.execute(
            target=target,
            task=analysis_prompt,
            context={"traffic_summary": traffic_summary},
            scope_config={"target_domains": [target]},
            enable_hil=True,
            timeout=60
        )
        
        # Parse CAI output for structured response
        suggestions = []
        vulnerability_found = False
        next_action = None
        
        for finding in result.findings:
            if finding.get("type") == "suggested_action":
                suggestions.append(finding)
            elif "vulnerability" in finding.get("type", "").lower():
                vulnerability_found = True
        
        # Extract next action from reasoning
        for entry in result.reasoning_chain:
            if "next" in str(entry.get("arguments", {})).lower():
                next_action = entry.get("arguments", {})
                break
        
        return {
            "suggestions": suggestions,
            "vulnerability_found": vulnerability_found,
            "next_action": next_action,
            "raw_analysis": result
        }
    
    def _on_new_findings(self, findings: List, result: BurpCAIBridge):
        """Callback when Burp bridge detects new findings."""
        print(f"[BurpCAI] {len(findings)} new findings from Burp")


# PentAGI Deep Reasoner (Week 2, Day 8-9)
class PentAGIDeepReasoner:
    """
    PentAGI integration for complex vulnerability reasoning and exploit chains.
    
    PentAGI specializes in:
    - Multi-step exploit chain construction
    - Novel vulnerability detection
    - Report generation for bug bounty submissions
    """
    
    TOOL_NAME = "pentagi_deep_reasoner"
    RISK_BAND = 3  # Always requires HIL
    
    def __init__(self):
        self.pentagi_path = Path("vendor/pentagi")
        self.api_port = 8080  # Default PentAGI API port
        self._ensure_running()
    
    def _ensure_running(self):
        """Start PentAGI services if not already running."""
        import subprocess
        
        compose_file = self.pentagi_path / "docker-compose.yml"
        if not compose_file.exists():
            raise RuntimeError("PentAGI not found in vendor/pentagi")
        
        # Check if already running
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "ps"],
            capture_output=True,
            text=True
        )
        
        if "Up" not in result.stdout:
            print("[PentAGI] Starting services...")
            subprocess.run(
                ["docker-compose", "-f", str(compose_file), "up", "-d"],
                check=True,
                cwd=self.pentagi_path
            )
            # Wait for startup
            import time
            time.sleep(10)
    
    async def analyze_finding_chain(
        self,
        findings: List[Dict],
        target: str
    ) -> Dict:
        """
        Analyze multiple findings to discover exploit chains.
        
        Example chain: XSS → CSRF → Account Takeover
        """
        import httpx
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"http://localhost:{self.api_port}/api/analyze",
                    json={
                        "type": "chain_analysis",
                        "target": target,
                        "findings": findings,
                        "depth": 3  # Up to 3-step chains
                    },
                    timeout=60.0
                )
                
                data = response.json()
                
                return {
                    "status": "success",
                    "chains": data.get("chains", []),
                    "highest_impact": self._get_highest_impact(data.get("chains", [])),
                    "reasoning": data.get("reasoning", "")
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e),
                    "chains": []
                }
    
    async def generate_submission_report(
        self,
        chain: Dict,
        format: str = "hackerone"
    ) -> Dict:
        """
        Generate professional bug bounty submission report.
        """
        import httpx
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"http://localhost:{self.api_port}/api/report",
                    json={
                        "chain": chain,
                        "format": format,
                        "include_remediation": True
                    },
                    timeout=60.0
                )
                
                data = response.json()
                
                return {
                    "status": "success",
                    "report_markdown": data.get("report"),
                    "severity": data.get("severity"),
                    "cvss_score": data.get("cvss"),
                    "bounty_estimate": data.get("bounty_range"),
                    "repro_steps": data.get("reproduction_steps", [])
                }
                
            except Exception as e:
                return {
                    "status": "error",
                    "error": str(e)
                }
    
    def _get_highest_impact(self, chains: List[Dict]) -> Optional[Dict]:
        """Get highest impact chain from analysis."""
        if not chains:
            return None
        
        return max(
            chains,
            key=lambda x: x.get("estimated_impact", 0) * x.get("confidence", 0.5)
        )


# Simplified usage
async def main():
    """Example usage of Burp + CAI integration."""
    bridge = BurpCAIBridge(burp_proxy="127.0.0.1:8080")
    
    result = await bridge.run_collaborative_scan(
        target="https://juice-shop.herokuapp.com",
        task="systematic_security_assessment",
        max_iterations=5
    )
    
    print(f"Status: {result.status}")
    print(f"Burp findings: {len(result.burp_findings)}")
    print(f"CAI suggestions: {len(result.cai_suggestions)}")


if __name__ == "__main__":
    asyncio.run(main())
