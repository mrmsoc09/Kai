"""
CAI Integration Extension for TieredWorkflowOrchestrator

This module extends the orchestrator with CAI autonomous agent capabilities.
Import and use in the main orchestrator to enable AI-driven Tier 2/3 scanning.
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime


class CAIOrchestratorMixin:
    """Mixin to add CAI integration to TieredWorkflowOrchestrator."""
    
    async def execute_with_cai(
        self,
        target: str,
        bbp_mode: str = 'public_bbp',
        enable_cai: bool = True,
        cai_timeout: int = 600
    ) -> Dict[str, Any]:
        """
        Execute tiered scan with optional CAI autonomous agent enhancement.
        
        This method extends the standard scan workflow by:
        1. Running Tier 1 reconnaissance
        2. Checking CAI activation triggers
        3. If triggered, executing CAI agent for deep analysis
        4. Merging AI findings with traditional tool results
        
        Args:
            target: Target URL, domain, or IP
            bbp_mode: Bug bounty program mode
            enable_cai: Whether to enable CAI autonomous agent
            cai_timeout: Maximum CAI execution time (seconds)
            
        Returns:
            Complete scan results including AI findings
        """
        from modules.orchestration.cai_trigger import CAITrigger
        
        start_time = datetime.now()
        
        print(f"[*] Starting AI-enhanced scan of {target}")
        print(f"[*] CAI Enhancement: {enable_cai}")
        
        # Step 1: Run Tier 1 (always runs)
        print("[*] Phase 1: Tier 1 Reconnaissance")
        tier1_results = await self._execute_tier(target, 1, bbp_mode, True)
        
        results = {
            'target': target,
            'bbp_mode': bbp_mode,
            'start_time': start_time.isoformat(),
            'cai_enabled': enable_cai,
            'tiers': {'tier_1': tier1_results},
            'ai_analysis': None
        }
        
        # Step 2: Check CAI triggers
        if enable_cai and tier1_results:
            trigger = CAITrigger.evaluate({
                'target': target,
                'tier_1_findings': tier1_results.get('findings', []),
                'tools': tier1_results.get('tools', [])
            })
            
            if trigger and trigger.confidence > 0.3:
                print(f"[+] CAI Triggered: {trigger.trigger_name}")
                print(f"[+] Task: {trigger.task}")
                print(f"[+] Confidence: {trigger.confidence:.2f}")
                
                # Step 3: Execute CAI agent
                try:
                    from tools.wrappers.cai_autonomous_agent import CAIAutonomousAgent
                    
                    cai_agent = CAIAutonomousAgent()
                    ai_results = await cai_agent.execute(
                        target=target,
                        task=trigger.task,
                        context={
                            'tier_1_findings': tier1_results.get('findings', []),
                            'trigger': trigger.trigger_name,
                            'trigger_confidence': trigger.confidence
                        },
                        scope_config={'target_domains': [target]},
                        enable_hil=True,
                        timeout=cai_timeout
                    )
                    
                    results['ai_analysis'] = {
                        'trigger': trigger.__dict__,
                        'agent_results': ai_results.__dict__,
                        'execution_time': ai_results.execution_time,
                        'findings_count': len(ai_results.findings)
                    }
                    
                    # Step 4: Run Tier 2/3 conditionally
                    print("[*] Phase 2: Tier 2 Targeted Analysis")
                    tier2_results = await self._execute_tier(target, 2, bbp_mode, True)
                    results['tiers']['tier_2'] = tier2_results
                    
                    if trigger.priority.value >= 3:  # HIGH or CRITICAL
                        print("[*] Phase 3: Tier 3 Deep Inspection")
                        tier3_results = await self._execute_tier(target, 3, bbp_mode, False)
                        results['tiers']['tier_3'] = tier3_results
                    
                except Exception as e:
                    print(f"[!] CAI execution failed: {e}")
                    results['ai_analysis'] = {'error': str(e), 'status': 'failed'}
            else:
                print(f"[-] No CAI triggers met (confidence threshold: 0.3)")
                # Still run Tier 2 for standard tools
                tier2_results = await self._execute_tier(target, 2, bbp_mode, True)
                results['tiers']['tier_2'] = tier2_results
        else:
            # Standard Tier 2/3 without CAI
            print("[*] Phase 2: Tier 2 Targeted Analysis")
            tier2_results = await self._execute_tier(target, 2, bbp_mode, True)
            results['tiers']['tier_2'] = tier2_results
            
            print("[*] Phase 3: Tier 3 Deep Inspection")
            tier3_results = await self._execute_tier(target, 3, bbp_mode, False)
            results['tiers']['tier_3'] = tier3_results
        
        # Aggregate all findings
        all_findings = self._aggregate_findings(results)
        results['all_findings'] = all_findings
        results['end_time'] = datetime.now().isoformat()
        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()
        
        # Print summary
        ai_findings_count = 0
        if results.get('ai_analysis') and 'agent_results' in results['ai_analysis']:
            ai_findings_count = results['ai_analysis'].get('findings_count', 0)
        
        print(f"\n[*] Scan Complete")
        print(f"[*] Total Findings: {len(all_findings)}")
        print(f"[*] AI-Generated Findings: {ai_findings_count}")
        print(f"[*] Duration: {results['duration_seconds']:.1f}s")
        
        return results
    
    async def _run_cai_with_fallback(self, target: str, task: str) -> Dict[str, Any]:
        """
        Execute CAI with fallback to standard tools if CAI fails.
        
        Returns:
            Dict with 'success', 'results', and 'fallback_used' keys
        """
        try:
            from tools.wrappers.cai_autonomous_agent import CAIAutonomousAgent
            
            agent = CAIAutonomousAgent()
            result = await agent.execute(
                target=target,
                task=task,
                scope_config={'target_domains': [target]},
                enable_hil=True
            )
            
            if result.status == 'completed':
                return {
                    'success': True,
                    'results': result,
                    'fallback_used': False,
                    'findings': result.findings
                }
            else:
                return {
                    'success': False,
                    'results': result,
                    'fallback_used': True,
                    'error': result.error,
                    'findings': []
                }
                
        except Exception as e:
            print(f"[!] CAI unavailable, falling back to standard tools: {e}")
            return {
                'success': False,
                'results': None,
                'fallback_used': True,
                'error': str(e),
                'findings': []
            }


def extend_orchestrator(orchestrator_class):
    """
    Monkey-patch CAI capabilities into existing orchestrator.
    
    Usage:
        from modules.orchestration.tiered_orchestrator import TieredWorkflowOrchestrator
        from modules.orchestration.tiered_orchestrator_cai_integration import extend_orchestrator
        
        TieredWorkflowOrchestrator = extend_orchestrator(TieredWorkflowOrchestrator)
        orchestrator = TieredWorkflowOrchestrator()
        results = await orchestrator.execute_with_cai("target.com")
    """
    orchestrator_class.execute_with_cai = CAIOrchestratorMixin.execute_with_cai
    orchestrator_class._run_cai_with_fallback = CAIOrchestratorMixin._run_cai_with_fallback
    return orchestrator_class


# Export for direct usage
__all__ = ['CAIOrchestratorMixin', 'extend_orchestrator']
