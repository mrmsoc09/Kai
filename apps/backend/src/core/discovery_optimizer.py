"""
Discovery Optimizer - Optimizes vulnerability discovery rate

Combines EPSS prioritization with parallel tool chaining to maximize
high-value finding discovery.

Target: 2x improvement in payout-worthy findings (200-300/month from 100-150/month)
"""

import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolChain:
    """Represents a sequence of tools to run."""
    name: str
    tools: List[str]
    parallel: bool = False
    description: str = ""
    target_types: List[str] = field(default_factory=list)


@dataclass
class OptimizedHunt:
    """Optimized hunt configuration."""
    hunt_id: str
    target: str
    tool_chains: List[ToolChain]
    epss_prioritized_cves: List[str]
    estimated_findings: int
    estimated_duration: int  # minutes


class DiscoveryOptimizer:
    """Optimizes vulnerability discovery through intelligent tool chaining and EPSS prioritization."""

    # Pre-defined tool chains optimized for different target types
    TOOL_CHAINS = {
        'web_app': ToolChain(
            name='web_app_full',
            tools=['nmap', 'nuclei', 'sqlmap', 'xss_hunter', 'dir_buster'],
            parallel=False,
            description='Full web application security scan',
            target_types=['web', 'api']
        ),
        'web_app_quick': ToolChain(
            name='web_app_quick',
            tools=['nuclei', 'xss_hunter'],
            parallel=True,
            description='Quick web app vulnerability scan',
            target_types=['web']
        ),
        'api': ToolChain(
            name='api_scan',
            tools=['nuclei', 'ffuf', 'api_fuzzer'],
            parallel=False,
            description='API security scan',
            target_types=['api']
        ),
        'infrastructure': ToolChain(
            name='infrastructure_scan',
            tools=['nmap', 'masscan', 'nuclei', 'ssl_scanner'],
            parallel=False,
            description='Infrastructure vulnerability scan',
            target_types=['infrastructure', 'network']
        ),
        'recon': ToolChain(
            name='reconnaissance',
            tools=['subfinder', 'amass', 'httpx', 'waybackurls'],
            parallel=True,
            description='Reconnaissance and asset discovery',
            target_types=['all']
        ),
    }

    def __init__(self):
        self.stats = {
            'hunts_optimized': 0,
            'parallel_executions': 0,
            'epss_prioritizations': 0,
            'avg_findings_per_hunt': 0,
        }

    def create_optimized_hunt(
        self,
        target: str,
        target_type: str = 'web',
        intensity: str = 'normal',
        time_budget: Optional[int] = None  # minutes
    ) -> OptimizedHunt:
        """Create an optimized hunt configuration.

        Args:
            target: Target domain or IP
            target_type: Type of target (web, api, infrastructure)
            intensity: Scan intensity (passive, normal, aggressive)
            time_budget: Optional time constraint in minutes

        Returns:
            Optimized hunt configuration
        """
        hunt_id = f"hunt-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        # Select appropriate tool chains
        selected_chains = self._select_tool_chains(target_type, intensity, time_budget)

        # Estimate findings based on tool chains
        estimated_findings = self._estimate_findings(selected_chains, intensity)

        # Calculate estimated duration
        estimated_duration = self._estimate_duration(selected_chains, intensity)

        hunt = OptimizedHunt(
            hunt_id=hunt_id,
            target=target,
            tool_chains=selected_chains,
            epss_prioritized_cves=[],  # Will be populated by EPSS integration
            estimated_findings=estimated_findings,
            estimated_duration=estimated_duration
        )

        self.stats['hunts_optimized'] += 1

        logger.info(f"Created optimized hunt {hunt_id} for {target} ({target_type})")
        logger.info(f"  Tool chains: {len(selected_chains)}, Estimated findings: {estimated_findings}")

        return hunt

    def _select_tool_chains(
        self,
        target_type: str,
        intensity: str,
        time_budget: Optional[int]
    ) -> List[ToolChain]:
        """Select optimal tool chains based on parameters."""
        chains = []

        if intensity == 'passive':
            # Passive only - just reconnaissance
            chains.append(self.TOOL_CHAINS['recon'])

        elif intensity == 'normal':
            # Recon + targeted scanning
            chains.append(self.TOOL_CHAINS['recon'])

            if target_type == 'web':
                chains.append(self.TOOL_CHAINS['web_app_quick'])
            elif target_type == 'api':
                chains.append(self.TOOL_CHAINS['api'])
            else:
                chains.append(self.TOOL_CHAINS['infrastructure'])

        elif intensity == 'aggressive':
            # Full scan suite
            chains.append(self.TOOL_CHAINS['recon'])

            if target_type in ['web', 'all']:
                chains.append(self.TOOL_CHAINS['web_app'])
            if target_type in ['api', 'all']:
                chains.append(self.TOOL_CHAINS['api'])
            if target_type in ['infrastructure', 'all']:
                chains.append(self.TOOL_CHAINS['infrastructure'])

        # Filter by time budget if specified
        if time_budget:
            total_time = sum(self._estimate_chain_duration(c) for c in chains)
            if total_time > time_budget:
                # Prioritize chains and trim to fit budget
                chains = self._prioritize_chains_by_time(chains, time_budget)

        return chains

    def _estimate_chain_duration(self, chain: ToolChain) -> int:
        """Estimate duration for a tool chain in minutes."""
        base_time_per_tool = 5  # minutes
        total_time = len(chain.tools) * base_time_per_tool

        if chain.parallel:
            # Parallel execution reduces time
            total_time = max(base_time_per_tool, total_time // len(chain.tools))

        return total_time

    def _prioritize_chains_by_time(
        self,
        chains: List[ToolChain],
        time_budget: int
    ) -> List[ToolChain]:
        """Prioritize chains to fit within time budget."""
        # Sort by estimated value (more tools = more findings)
        sorted_chains = sorted(chains, key=lambda c: len(c.tools), reverse=True)

        selected = []
        total_time = 0

        for chain in sorted_chains:
            chain_time = self._estimate_chain_duration(chain)
            if total_time + chain_time <= time_budget:
                selected.append(chain)
                total_time += chain_time
            else:
                break

        return selected

    def _estimate_findings(self, chains: List[ToolChain], intensity: str) -> int:
        """Estimate number of findings based on tool chains."""
        base_findings = {
            'passive': 5,
            'normal': 15,
            'aggressive': 30
        }

        base = base_findings.get(intensity, 15)

        # Increase estimate based on number of tools
        total_tools = sum(len(c.tools) for c in chains)
        multiplier = 1 + (total_tools * 0.1)

        return int(base * multiplier)

    def _estimate_duration(self, chains: List[ToolChain], intensity: str) -> int:
        """Estimate total hunt duration in minutes."""
        return sum(self._estimate_chain_duration(c) for c in chains)

    async def execute_parallel_tools(
        self,
        tools: List[str],
        target: str
    ) -> Dict[str, Any]:
        """Execute multiple tools in parallel.

        Args:
            tools: List of tool names to execute
            target: Target to scan

        Returns:
            Combined results from all tools
        """
        logger.info(f"Executing {len(tools)} tools in parallel on {target}")

        async def run_tool(tool_name: str) -> Tuple[str, Dict]:
            # Simulated tool execution
            await asyncio.sleep(1)  # Simulate work
            return tool_name, {
                'tool': tool_name,
                'target': target,
                'findings': [],
                'status': 'completed'
            }

        # Execute all tools concurrently
        results = await asyncio.gather(*[run_tool(tool) for tool in tools])

        self.stats['parallel_executions'] += 1

        return {
            'parallel': True,
            'tools_executed': len(tools),
            'results': dict(results)
        }

    def get_tool_chain_templates(self) -> Dict[str, Dict]:
        """Get all available tool chain templates."""
        return {
            name: {
                'name': chain.name,
                'tools': chain.tools,
                'parallel': chain.parallel,
                'description': chain.description,
                'target_types': chain.target_types,
                'estimated_duration': self._estimate_chain_duration(chain)
            }
            for name, chain in self.TOOL_CHAINS.items()
        }

    def prioritize_with_epss(
        self,
        cves: List[str],
        min_epss: float = 0.7
    ) -> Tuple[List[str], List[str]]:
        """Prioritize CVEs using EPSS scores.

        Args:
            cves: List of CVE IDs
            min_epss: Minimum EPSS threshold for high priority

        Returns:
            Tuple of (high_priority, low_priority) CVE lists
        """
        # This would integrate with EPSS client in production
        # For now, simulate prioritization

        high_priority = []
        low_priority = []

        for cve in cves:
            # Simulate EPSS score
            simulated_epss = hash(cve) % 100 / 100.0

            if simulated_epss >= min_epss:
                high_priority.append(cve)
            else:
                low_priority.append(cve)

        self.stats['epss_prioritizations'] += 1

        logger.info(f"Prioritized {len(cves)} CVEs: {len(high_priority)} high, {len(low_priority)} low")

        return high_priority, low_priority

    def get_stats(self) -> Dict:
        """Get optimizer statistics."""
        return {
            **self.stats,
            'available_tool_chains': len(self.TOOL_CHAINS),
            'total_unique_tools': len(set(
                tool for chain in self.TOOL_CHAINS.values() for tool in chain.tools
            ))
        }


# Global instance
_discovery_optimizer: Optional[DiscoveryOptimizer] = None


def get_discovery_optimizer() -> DiscoveryOptimizer:
    """Get the global discovery optimizer instance."""
    global _discovery_optimizer
    if _discovery_optimizer is None:
        _discovery_optimizer = DiscoveryOptimizer()
    return _discovery_optimizer
