"""
TieredWorkflowOrchestrator
Manages tiered execution of 35-tool stack based on asset type and triggers.
"""
import asyncio
import yaml
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

class TieredWorkflowOrchestrator:
    """
    Orchestrates scan workflows across Tier 1/2/3 tools.
    Implements double redundancy for enterprise-grade coverage.
    """

    def __init__(self, config_path: str = '/a0/usr/projects/kaisonone/config/bbp_modes.yaml'):
        self.config = self._load_config(config_path)
        self.registry = self._load_tool_registry()
        self.executor = ThreadPoolExecutor(max_workers=20)
        self.workflow_history = []

    def _load_config(self, path: str) -> Dict:
        """Load BBP configuration."""
        with open(path) as f:
            return yaml.safe_load(f)

    def _load_tool_registry(self) -> Dict:
        """Load tool registry."""
        with open('/a0/usr/projects/kaisonone/tools/registry/tool_registry.yaml') as f:
            return yaml.safe_load(f)

    async def execute_scan(
        self,
        target: str,
        bbp_mode: str = 'public_bbp',
        tier_override: Optional[List[int]] = None,
        enable_redundancy: bool = True
    ) -> Dict[str, Any]:
        """
        Execute tiered scan against target.

        Args:
            target: Scan target (domain, URL, IP)
            bbp_mode: public_bbp, private_contract, or enterprise_audit
            tier_override: Override which tiers to run [1, 2, 3]
            enable_redundancy: Run secondary tools for double coverage

        Returns:
            Complete scan results with findings from all applicable tools
        """
        start_time = datetime.now()
        tiers_to_run = tier_override or [1, 2, 3]

        print(f"[*] Starting tiered scan of {target}")
        print(f"[*] BBP Mode: {bbp_mode}")
        print(f"[*] Tiers: {tiers_to_run}")
        print(f"[*] Redundancy: {enable_redundancy}")

        results = {
            'target': target,
            'bbp_mode': bbp_mode,
            'start_time': start_time.isoformat(),
            'tiers': {}
        }

        # Execute each tier
        for tier in tiers_to_run:
            tier_results = await self._execute_tier(
                target, tier, bbp_mode, enable_redundancy
            )
            results['tiers'][f'tier_{tier}'] = tier_results

        # Aggregate and deduplicate findings
        all_findings = self._aggregate_findings(results)
        results['all_findings'] = all_findings
        results['end_time'] = datetime.now().isoformat()
        results['duration_seconds'] = (datetime.now() - start_time).total_seconds()

        return results

    async def _execute_tier(
        self,
        target: str,
        tier: int,
        bbp_mode: str,
        enable_redundancy: bool
    ) -> Dict[str, Any]:
        """Execute all tools in a tier."""
        tier_tools = self._get_tools_by_tier(tier)
        print(f"[*] Tier {tier}: {len(tier_tools)} tools")

        findings = []
        executed_tools = []

        # Check trigger conditions for Tier 2/3 tools
        applicable_tools = []
        for tool in tier_tools:
            if tier == 1:
                applicable_tools.append(tool)
            elif self._should_run_tool(tool, target):
                applicable_tools.append(tool)

        # Run tools in parallel
        tasks = []
        for tool in applicable_tools:
            task = self._run_tool_with_wrapper(tool, target)
            tasks.append(task)

            # Secondary tool for redundancy
            if enable_redundancy and tool.get('redundancy_for'):
                secondary = self._get_secondary_tool(tool)
                if secondary:
                    tasks.append(self._run_tool_with_wrapper(secondary, target))

        # Execute all tasks
        if tasks:
            tool_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in tool_results:
                if isinstance(result, Exception):
                    print(f"[!] Tool error: {result}")
                elif result and result.get('findings'):
                    findings.extend(result['findings'])
                    executed_tools.append(result.get('tool'))

        return {
            'tier': tier,
            'tools_executed': len(executed_tools),
            'tool_names': executed_tools,
            'findings_count': len(findings),
            'findings': findings
        }

    def _get_tools_by_tier(self, tier: int) -> List[Dict]:
        """Get all tools for a specific tier."""
        return [
            t for t in self.registry.get('tools', [])
            if t.get('tier') == tier
        ]

    def _should_run_tool(self, tool: Dict, target: str) -> bool:
        """Check if tool should run based on triggers."""
        # For now, run all Tier 2/3 tools
        # TODO: Implement intelligent trigger detection
        return True

    def _get_secondary_tool(self, primary_tool: Dict) -> Optional[Dict]:
        """Get secondary tool for redundancy."""
        redundancy_target = primary_tool.get('redundancy_for')
        if redundancy_target:
            for tool in self.registry.get('tools', []):
                if tool.get('name') == redundancy_target:
                    return tool
        return None

    async def _run_tool_with_wrapper(self, tool: Dict, target: str) -> Dict:
        """Run a tool using its wrapper."""
        tool_name = tool.get('name')
        wrapper_path = f'/a0/usr/projects/kaisonone/tools/wrappers/{tool_name}.py'

        try:
            # Dynamically import wrapper
            import importlib.util
            spec = importlib.util.spec_from_file_location(f"{tool_name}_wrapper", wrapper_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Get agent class
            agent_class_name = f"{tool_name.title().replace('_', '')}Agent"
            agent_class = getattr(module, agent_class_name)
            agent = agent_class()

            # Execute scan
            result = agent.scan(target)
            return result
        except Exception as e:
            return {
                'tool': tool_name,
                'target': target,
                'error': str(e),
                'findings': [],
                'success': False
            }

    def _aggregate_findings(self, results: Dict) -> List[Dict]:
        """Aggregate and deduplicate findings across tiers."""
        all_findings = []
        seen_hashes = set()

        for tier_key, tier_data in results.get('tiers', {}).items():
            for finding in tier_data.get('findings', []):
                # Create hash for deduplication
                finding_hash = self._hash_finding(finding)
                if finding_hash not in seen_hashes:
                    seen_hashes.add(finding_hash)
                    all_findings.append(finding)

        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
        all_findings.sort(key=lambda x: severity_order.get(x.get('severity', 'medium'), 99))

        return all_findings

    def _hash_finding(self, finding: Dict) -> str:
        """Create deterministic hash for finding deduplication."""
        import hashlib
        key = f"{finding.get('type', 'unknown')}:{finding.get('title', '')}"
        return hashlib.md5(key.encode()).hexdigest()
